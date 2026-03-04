#!/usr/bin/env python3
"""
UFC Historical Events and Fights - FULL DATASET
Gets ALL events and ALL fights with pagination fix
Milestone reports every 500 fights
"""
import sys
import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('full_history_scrape.log')
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scrapers.ufc_scraper import UFCScraper
from models import Fighter, Event, Fight, FightStat, get_session, init_db

FIGHT_MILESTONE = 500

class FullHistoryScraper:
    def __init__(self):
        self.scraper = UFCScraper(delay=1.5, max_retries=3)
        self.stats = {
            'events_added': 0,
            'fights_added': 0,
            'fight_stats_added': 0,
            'errors': 0
        }
        
    def log_milestone(self, milestone_type, count, extra_info=""):
        """Log milestone progress"""
        logger.info(f"🏁 MILESTONE: {milestone_type} - {count} completed {extra_info}")
        
    def log_progress(self):
        """Log overall progress"""
        db = get_session()
        try:
            fighters = db.query(Fighter).count()
            fighter_with_stats = db.query(Fighter).filter(Fighter.slpm != None).count()
            events = db.query(Event).count()
            fights = db.query(Fight).count()
            fight_stats = db.query(FightStat).count()
            
            logger.info(f"📊 OVERALL PROGRESS:")
            logger.info(f"   Fighters: {fighters} total, {fighter_with_stats} with career stats")
            logger.info(f"   Events: {events}")
            logger.info(f"   Fights: {fights}")
            logger.info(f"   Fight Stats: {fight_stats}")
            return {
                'fighters': fighters,
                'fighters_with_stats': fighter_with_stats,
                'events': events,
                'fights': fights,
                'fight_stats': fight_stats
            }
        finally:
            db.close()

    def phase_1_all_events(self):
        """Phase 1: Collect ALL historical events with pagination fix"""
        logger.info("=" * 60)
        logger.info("PHASE 1: COLLECTING ALL HISTORICAL EVENTS (PAGINATION FIXED)")
        logger.info("=" * 60)
        
        db = get_session()
        try:
            existing = db.query(Event).count()
            logger.info(f"Currently have {existing} events")
            
            # Get all completed events - now with working pagination
            page_num = 1
            total_events = 0
            
            while page_num <= 50:  # Safety limit
                url = f"http://www.ufcstats.com/statistics/events/completed?page={page_num}"
                logger.info(f"Fetching events page {page_num}...")
                
                soup = self.scraper._get(url)
                if not soup:
                    break
                
                table = soup.find('table', class_='b-statistics__table-events')
                if not table:
                    break
                
                rows = table.find_all('tr', class_='b-statistics__table-row')
                if not rows or len(rows) <= 1:
                    break
                
                events_on_page = 0
                for row in rows[1:]:  # Skip header
                    try:
                        link = row.find('a', class_='b-link_style_black')
                        if not link:
                            continue
                        
                        name = link.text.strip()
                        href = link.get('href', '')
                        ufc_id = href.split('/')[-1] if '/' in href else None
                        
                        # Check if already exists
                        existing_event = db.query(Event).filter_by(ufc_id=ufc_id).first()
                        if existing_event:
                            continue
                        
                        # Get date
                        date_elem = row.find('span', class_='b-statistics__date')
                        event_date = None
                        if date_elem:
                            try:
                                from datetime import datetime
                                event_date = datetime.strptime(date_elem.text.strip(), '%B %d, %Y').date()
                            except:
                                pass
                        
                        # Get location
                        location_elem = row.find('td', class_='b-statistics__table-col_l_align_left')
                        location = location_elem.text.strip() if location_elem else None
                        
                        event = Event(
                            name=name,
                            ufc_id=ufc_id,
                            url=href,
                            date=event_date,
                            location=location,
                            status='completed'
                        )
                        db.add(event)
                        events_on_page += 1
                        
                    except Exception as e:
                        logger.debug(f"Error parsing event row: {e}")
                        continue
                
                db.commit()
                total_events += events_on_page
                self.stats['events_added'] += events_on_page
                
                logger.info(f"  Page {page_num}: {events_on_page} new events")
                
                if events_on_page == 0:
                    break
                
                page_num += 1
            
            logger.info(f"✅ Phase 1 Complete - Added {self.stats['events_added']} new events")
            logger.info(f"   Total pages scanned: {page_num - 1}")
            
        finally:
            db.close()
            
        self.log_milestone("PHASE 1 COMPLETE", self.stats['events_added'])
        self.log_progress()

    def phase_2_all_fights_and_stats(self):
        """Phase 2: Collect ALL fights with detailed stats"""
        logger.info("=" * 60)
        logger.info("PHASE 2: COLLECTING ALL FIGHTS & DETAILED STATS")
        logger.info("=" * 60)
        
        db = get_session()
        try:
            # Get all events that have URL but may not have fights scraped
            events = db.query(Event).filter(Event.url != None).all()
            logger.info(f"Processing fights from {len(events)} events")
            
            for i, event in enumerate(events, 1):
                try:
                    # Check if we already have fights for this event
                    existing_fights = db.query(Fight).filter_by(event_id=event.id).count()
                    if existing_fights > 0:
                        logger.debug(f"Skipping {event.name} - already has {existing_fights} fights")
                        continue
                    
                    fights = self.scraper.get_event_fights(event.url)
                    
                    for fight_data in fights:
                        try:
                            # Check if fight exists
                            existing = db.query(Fight).filter_by(ufc_id=fight_data['ufc_id']).first()
                            
                            if not existing:
                                # Get fighter IDs
                                fighter_a = db.query(Fighter).filter_by(ufc_id=fight_data['fighter_a_id']).first()
                                fighter_b = db.query(Fighter).filter_by(ufc_id=fight_data['fighter_b_id']).first()
                                
                                if fighter_a and fighter_b:
                                    winner = None
                                    if fight_data.get('winner_id'):
                                        winner_fighter = db.query(Fighter).filter_by(ufc_id=fight_data['winner_id']).first()
                                        winner = winner_fighter.id if winner_fighter else None
                                    
                                    fight = Fight(
                                        event_id=event.id,
                                        fighter_a_id=fighter_a.id,
                                        fighter_b_id=fighter_b.id,
                                        winner_id=winner,
                                        ufc_id=fight_data['ufc_id'],
                                        method=fight_data.get('method'),
                                        end_round=fight_data.get('end_round'),
                                        end_time=fight_data.get('end_time'),
                                        card_position=fight_data.get('card_position')
                                    )
                                    db.add(fight)
                                    db.commit()
                                    self.stats['fights_added'] += 1
                                    
                                    # Get detailed fight stats
                                    if fight_data.get('fight_url'):
                                        self._save_fight_stats(db, fight, fight_data['fight_url'], fighter_a.id, fighter_b.id)
                                    
                                    # Milestone check
                                    if self.stats['fights_added'] % FIGHT_MILESTONE == 0:
                                        self.log_milestone("FIGHTS ADDED", self.stats['fights_added'])
                                        self.log_progress()
                            
                        except Exception as e:
                            logger.error(f"Error processing fight: {e}")
                            self.stats['errors'] += 1
                            db.rollback()
                            continue
                    
                    if i % 10 == 0:
                        logger.info(f"Processed {i}/{len(events)} events, {self.stats['fights_added']} new fights")
                        
                except Exception as e:
                    logger.error(f"Error processing event {event.name}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            logger.info(f"✅ Phase 2 Complete - Added {self.stats['fights_added']} new fights")
            
        finally:
            db.close()
            
        self.log_milestone("PHASE 2 COMPLETE", self.stats['fights_added'])
        self.log_progress()

    def _save_fight_stats(self, db, fight, fight_url, fighter_a_id, fighter_b_id):
        """Save detailed stats for a fight"""
        try:
            stats_a, stats_b = self.scraper.get_fight_stats(fight_url)
            
            for fighter_id, stats in [(fighter_a_id, stats_a), (fighter_b_id, stats_b)]:
                if stats:
                    existing = db.query(FightStat).filter_by(fight_id=fight.id, fighter_id=fighter_id).first()
                    if not existing:
                        stat_record = FightStat(
                            fight_id=fight.id,
                            fighter_id=fighter_id,
                            sig_strikes_landed=stats.get('sig_strikes_landed', 0),
                            sig_strikes_attempted=stats.get('sig_strikes_attempted', 0),
                            total_strikes_landed=stats.get('total_strikes_landed', 0),
                            total_strikes_attempted=stats.get('total_strikes_attempted', 0),
                            takedowns_landed=stats.get('takedowns_landed', 0),
                            takedowns_attempted=stats.get('takedowns_attempted', 0),
                            submissions_attempted=stats.get('submissions_attempted', 0),
                            knockdowns_scored=stats.get('knockdowns', 0),
                            sig_strikes_head_landed=stats.get('sig_strikes_head_landed', 0),
                            sig_strikes_body_landed=stats.get('sig_strikes_body_landed', 0)
                        )
                        db.add(stat_record)
                        self.stats['fight_stats_added'] += 1
            
            db.commit()
            
        except Exception as e:
            logger.debug(f"Error saving fight stats: {e}")
            db.rollback()

    def run(self):
        """Run full historical collection"""
        logger.info("🚀 STARTING FULL HISTORICAL UFC DATA COLLECTION")
        logger.info(f"Start time: {datetime.now()}")
        
        init_db()
        self.log_progress()
        
        # Phase 1: All Events (with pagination fix)
        self.phase_1_all_events()
        
        # Phase 2: All Fights with Stats
        self.phase_2_all_fights_and_stats()
        
        # Final summary
        logger.info("=" * 60)
        logger.info("FULL HISTORICAL SCRAPE COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"New events added: {self.stats['events_added']}")
        logger.info(f"New fights added: {self.stats['fights_added']}")
        logger.info(f"New fight stats added: {self.stats['fight_stats_added']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"End time: {datetime.now()}")
        
        self.scraper.print_stats()

if __name__ == "__main__":
    scraper = FullHistoryScraper()
    scraper.run()
