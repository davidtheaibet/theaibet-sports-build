#!/usr/bin/env python3
"""
UFC COMPREHENSIVE DATA COLLECTION - Option 3
Collects:
1. Career stats for all fighters (SLpM, accuracy, defense, etc.)
2. All historical fights with detailed round-by-round stats
3. All historical events

Reports after each milestone
"""
import sys
import os
import logging
from datetime import datetime
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('comprehensive_scrape.log')
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scrapers.ufc_scraper import UFCScraper
from models import Fighter, Event, Fight, FightStat, get_session, init_db

# Milestone settings
FIGHTER_MILESTONE = 500
FIGHT_MILESTONE = 500
EVENT_MILESTONE = 50

class ComprehensiveScraper:
    def __init__(self):
        self.scraper = UFCScraper(delay=1.5, max_retries=3)
        self.stats = {
            'fighters_updated': 0,
            'fights_added': 0,
            'fight_stats_added': 0,
            'events_added': 0,
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

    def update_fighter_career_stats(self, fighter):
        """Update a fighter with career statistics"""
        try:
            url = f"http://www.ufcstats.com/fighter-details/{fighter.ufc_id}"
            soup = self.scraper._get(url)
            if not soup:
                return False
            
            # Career stats section
            stats_items = soup.find_all('li', class_='b-list__box-list-item')
            
            for item in stats_items:
                text = item.get_text(strip=True)
                
                if text.startswith('SLpM:'):
                    val = text.replace('SLpM:', '').strip()
                    fighter.slpm = float(val) if val != '--' else None
                elif text.startswith('Str. Acc.:'):
                    val = text.replace('Str. Acc.:', '').strip().replace('%', '')
                    fighter.sig_strike_acc = float(val) / 100 if val != '--' else None
                elif text.startswith('SApM:'):
                    val = text.replace('SApM:', '').strip()
                    fighter.sapm = float(val) if val != '--' else None
                elif text.startswith('Str. Def:'):
                    val = text.replace('Str. Def:', '').strip().replace('%', '')
                    fighter.sig_strike_def = float(val) / 100 if val != '--' else None
                elif text.startswith('TD Avg.:'):
                    val = text.replace('TD Avg.:', '').strip()
                    fighter.td_avg = float(val) if val != '--' else None
                elif text.startswith('TD Acc.:'):
                    val = text.replace('TD Acc.:', '').strip().replace('%', '')
                    fighter.td_acc = float(val) / 100 if val != '--' else None
                elif text.startswith('TD Def.:'):
                    val = text.replace('TD Def:', '').strip().replace('%', '')
                    fighter.td_def = float(val) / 100 if val != '--' else None
                elif text.startswith('Sub. Avg.:'):
                    val = text.replace('Sub. Avg.:', '').strip()
                    fighter.sub_avg = float(val) if val != '--' else None
                elif text.startswith('Weight:'):
                    weight_str = text.replace('Weight:', '').strip()
                    try:
                        fighter.weight_lbs = int(weight_str.replace('lbs.', '').strip())
                    except:
                        pass
            
            return True
            
        except Exception as e:
            logger.debug(f"Error updating fighter {fighter.name}: {e}")
            return False

    def phase_1_fighter_career_stats(self):
        """Phase 1: Update all fighters with career statistics"""
        logger.info("=" * 60)
        logger.info("PHASE 1: COLLECTING FIGHTER CAREER STATISTICS")
        logger.info("=" * 60)
        
        db = get_session()
        try:
            # Get fighters without career stats
            fighters = db.query(Fighter).filter(Fighter.slpm == None).all()
            total = len(fighters)
            logger.info(f"Found {total} fighters needing career stats")
            
            for i, fighter in enumerate(fighters, 1):
                if self.update_fighter_career_stats(fighter):
                    db.commit()
                    self.stats['fighters_updated'] += 1
                else:
                    self.stats['errors'] += 1
                
                # Milestone reporting
                if i % FIGHTER_MILESTONE == 0:
                    self.log_milestone("Fighter Career Stats", i, f"of {total}")
                    self.log_progress()
                
                # Progress every 50
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{total} fighters processed")
                    
        finally:
            db.close()
            
        logger.info(f"✅ Phase 1 Complete - Updated {self.stats['fighters_updated']} fighters")
        self.log_milestone("PHASE 1 COMPLETE", self.stats['fighters_updated'])
        self.log_progress()

    def phase_2_all_historical_events(self):
        """Phase 2: Collect all historical events"""
        logger.info("=" * 60)
        logger.info("PHASE 2: COLLECTING ALL HISTORICAL EVENTS")
        logger.info("=" * 60)
        
        db = get_session()
        try:
            # Check how many events we have
            existing = db.query(Event).count()
            logger.info(f"Currently have {existing} events")
            
            # Get all completed events
            events = self.scraper.get_all_events(page='completed')
            logger.info(f"Found {len(events)} completed events on UFC Stats")
            
            new_events = 0
            for i, event_data in enumerate(events, 1):
                # Check if exists
                existing = db.query(Event).filter_by(ufc_id=event_data['ufc_id']).first()
                if not existing:
                    event = Event(**event_data)
                    db.add(event)
                    db.commit()
                    new_events += 1
                    self.stats['events_added'] += 1
                
                if i % EVENT_MILESTONE == 0:
                    self.log_milestone("Historical Events", i)
                    self.log_progress()
                    
            logger.info(f"✅ Phase 2 Complete - Added {new_events} new events")
            
        finally:
            db.close()
            
        self.log_milestone("PHASE 2 COMPLETE", self.stats['events_added'])
        self.log_progress()

    def phase_3_all_fights_and_stats(self):
        """Phase 3: Collect all fights with detailed stats"""
        logger.info("=" * 60)
        logger.info("PHASE 3: COLLECTING ALL FIGHTS & DETAILED STATS")
        logger.info("=" * 60)
        
        db = get_session()
        try:
            # Get all events that have fights we haven't scraped
            events = db.query(Event).all()
            logger.info(f"Processing fights from {len(events)} events")
            
            total_fights_before = db.query(Fight).count()
            
            for i, event in enumerate(events, 1):
                try:
                    if not event.url:
                        continue
                        
                    fights = self.scraper.get_event_fights(event.url)
                    
                    for fight_data in fights:
                        # Check if fight exists
                        existing = db.query(Fight).filter_by(ufc_id=fight_data['ufc_id']).first()
                        
                        if not existing:
                            # Get fighter IDs
                            fighter_a = db.query(Fighter).filter_by(ufc_id=fight_data['fighter_a_id']).first()
                            fighter_b = db.query(Fighter).filter_by(ufc_id=fight_data['fighter_b_id']).first()
                            
                            if fighter_a and fighter_b:
                                fight = Fight(
                                    event_id=event.id,
                                    fighter_a_id=fighter_a.id,
                                    fighter_b_id=fighter_b.id,
                                    **{k: v for k, v in fight_data.items() if k not in ['fighter_a_name', 'fighter_b_name', 'fighter_a_id', 'fighter_b_id']}
                                )
                                db.add(fight)
                                db.commit()
                                self.stats['fights_added'] += 1
                                
                                # Get detailed fight stats
                                if fight_data.get('fight_url'):
                                    self._save_fight_stats(db, fight, fight_data['fight_url'], fighter_a.id, fighter_b.id)
                        
                    if i % 10 == 0:
                        logger.info(f"Processed {i}/{len(events)} events")
                        
                    if self.stats['fights_added'] > 0 and self.stats['fights_added'] % FIGHT_MILESTONE == 0:
                        self.log_milestone("Fights Added", self.stats['fights_added'])
                        self.log_progress()
                        
                except Exception as e:
                    logger.error(f"Error processing event {event.name}: {e}")
                    self.stats['errors'] += 1
                    continue
                    
            total_fights_after = db.query(Fight).count()
            logger.info(f"✅ Phase 3 Complete - Total fights: {total_fights_after}")
            
        finally:
            db.close()
            
        self.log_milestone("PHASE 3 COMPLETE", self.stats['fights_added'])
        self.log_progress()

    def _save_fight_stats(self, db, fight, fight_url, fighter_a_id, fighter_b_id):
        """Save detailed stats for a fight"""
        try:
            stats_a, stats_b = self.scraper.get_fight_stats(fight_url)
            
            for fighter_id, stats in [(fighter_a_id, stats_a), (fighter_b_id, stats_b)]:
                if stats:
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
        """Run comprehensive data collection"""
        logger.info("🚀 STARTING COMPREHENSIVE UFC DATA COLLECTION")
        logger.info(f"Start time: {datetime.now()}")
        
        init_db()
        self.log_progress()
        
        # Phase 1: Fighter career stats
        self.phase_1_fighter_career_stats()
        
        # Phase 2: All historical events
        self.phase_2_all_historical_events()
        
        # Phase 3: All fights with detailed stats
        self.phase_3_all_fights_and_stats()
        
        # Final summary
        logger.info("=" * 60)
        logger.info("COMPREHENSIVE SCRAPE COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"Fighters updated with career stats: {self.stats['fighters_updated']}")
        logger.info(f"New events added: {self.stats['events_added']}")
        logger.info(f"New fights added: {self.stats['fights_added']}")
        logger.info(f"New fight stats added: {self.stats['fight_stats_added']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"End time: {datetime.now()}")
        
        self.scraper.print_stats()

if __name__ == "__main__":
    scraper = ComprehensiveScraper()
    scraper.run()
