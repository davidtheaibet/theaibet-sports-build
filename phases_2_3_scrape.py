#!/usr/bin/env python3
"""
UFC Phases 2 & 3: Events + All Fights with Detailed Stats
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
        logging.FileHandler('phases_2_3.log')
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scrapers.ufc_scraper import UFCScraper
from models import Fighter, Event, Fight, FightStat, get_session, init_db

FIGHT_MILESTONE = 500

class PhasesTwoThreeScraper:
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

    def phase_2_historical_events(self):
        """Phase 2: Collect all historical events"""
        logger.info("=" * 60)
        logger.info("PHASE 2: COLLECTING ALL HISTORICAL EVENTS")
        logger.info("=" * 60)
        
        db = get_session()
        try:
            existing = db.query(Event).count()
            logger.info(f"Currently have {existing} events")
            
            # Get all completed events
            events = self.scraper.get_all_events(page='completed')
            logger.info(f"Found {len(events)} completed events on UFC Stats")
            
            new_events = 0
            for i, event_data in enumerate(events, 1):
                try:
                    # Check if exists
                    existing = db.query(Event).filter_by(ufc_id=event_data['ufc_id']).first()
                    if not existing:
                        event = Event(**event_data)
                        db.add(event)
                        db.commit()
                        new_events += 1
                        self.stats['events_added'] += 1
                    
                    if i % 50 == 0:
                        logger.info(f"Progress: {i}/{len(events)} events checked")
                        
                except Exception as e:
                    logger.error(f"Error adding event {event_data.get('name', 'unknown')}: {e}")
                    self.stats['errors'] += 1
                    db.rollback()
                    continue
            
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
            # Get all events
            events = db.query(Event).all()
            logger.info(f"Processing fights from {len(events)} events")
            
            total_fights_before = db.query(Fight).count()
            
            for i, event in enumerate(events, 1):
                try:
                    if not event.url:
                        logger.debug(f"Skipping event {event.name} - no URL")
                        continue
                    
                    # Get fights for this event
                    fights = self.scraper.get_event_fights(event.url)
                    
                    for fight_data in fights:
                        try:
                            # Check if fight exists
                            existing = db.query(Fight).filter_by(ufc_id=fight_data['ufc_id']).first()
                            
                            if not existing:
                                # Get fighter IDs from database
                                fighter_a = db.query(Fighter).filter_by(ufc_id=fight_data['fighter_a_id']).first()
                                fighter_b = db.query(Fighter).filter_by(ufc_id=fight_data['fighter_b_id']).first()
                                
                                if fighter_a and fighter_b:
                                    # Create fight record
                                    fight = Fight(
                                        event_id=event.id,
                                        fighter_a_id=fighter_a.id,
                                        fighter_b_id=fighter_b.id,
                                        winner_id=db.query(Fighter).filter_by(ufc_id=fight_data['winner_id']).first().id if fight_data.get('winner_id') and db.query(Fighter).filter_by(ufc_id=fight_data['winner_id']).first() else None,
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
                        logger.info(f"Processed {i}/{len(events)} events, {self.stats['fights_added']} new fights added")
                        
                except Exception as e:
                    logger.error(f"Error processing event {event.name}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            total_fights_after = db.query(Fight).count()
            logger.info(f"✅ Phase 3 Complete - Total fights in DB: {total_fights_after}")
            
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
                    # Check if stats already exist
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
        """Run phases 2 and 3"""
        logger.info("🚀 STARTING PHASES 2 & 3: EVENTS + ALL FIGHTS")
        logger.info(f"Start time: {datetime.now()}")
        
        init_db()
        self.log_progress()
        
        # Phase 2: Historical Events
        self.phase_2_historical_events()
        
        # Phase 3: All Fights with Stats
        self.phase_3_all_fights_and_stats()
        
        # Final summary
        logger.info("=" * 60)
        logger.info("PHASES 2 & 3 COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"New events added: {self.stats['events_added']}")
        logger.info(f"New fights added: {self.stats['fights_added']}")
        logger.info(f"New fight stats added: {self.stats['fight_stats_added']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"End time: {datetime.now()}")
        
        self.scraper.print_stats()

if __name__ == "__main__":
    scraper = PhasesTwoThreeScraper()
    scraper.run()
