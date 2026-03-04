"""
Data Pipeline
Orchestrates scraping and storage of UFC data
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.ufc_scraper import UFCScraper
from scrapers.odds_scraper import OddsScraper
from models import Fighter, Event, Fight, FightStat, Odds, get_session, init_db

logger = logging.getLogger(__name__)


class UFCPipeline:
    """Pipeline for collecting and storing UFC data"""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.ufc_scraper = UFCScraper(delay=1.5)
        self.odds_scraper = OddsScraper(delay=1.0)
        self.db = db_session or get_session()
    
    def run_full_scrape(self, fighter_limit: Optional[int] = None):
        """
        Run complete scrape of all UFC data
        
        Args:
            fighter_limit: Limit number of fighters (for testing)
        """
        logger.info("🚀 Starting full UFC data scrape")
        
        # 1. Scrape fighters
        self.scrape_fighters(limit=fighter_limit)
        
        # 2. Scrape completed events and fights
        self.scrape_completed_events()
        
        # 3. Scrape upcoming events
        self.scrape_upcoming_events()
        
        # 4. Scrape current odds
        self.scrape_current_odds()
        
        self.ufc_scraper.print_stats()
        logger.info("✅ Full scrape complete")
    
    def scrape_fighters(self, limit: Optional[int] = None):
        """Scrape and store fighter profiles"""
        logger.info("👤 Scraping fighters...")
        
        fighters = self.ufc_scraper.get_all_fighters()
        if limit:
            fighters = fighters[:limit]
        
        new_count = 0
        updated_count = 0
        
        for fighter_data in fighters:
            try:
                # Check if exists
                existing = self.db.query(Fighter).filter_by(ufc_id=fighter_data['ufc_id']).first()
                
                # Get detailed info
                details = self.ufc_scraper.get_fighter_details(fighter_data['url'])
                if not details:
                    continue
                
                details['weight_class'] = fighter_data.get('weight_class')
                
                if existing:
                    # Update existing
                    for key, value in details.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    updated_count += 1
                else:
                    # Create new
                    fighter = Fighter(**details)
                    self.db.add(fighter)
                    new_count += 1
                
                # Commit every 10 fighters
                if (new_count + updated_count) % 10 == 0:
                    self.db.commit()
                    logger.info(f"  Progress: {new_count} new, {updated_count} updated")
                
            except Exception as e:
                logger.error(f"Error processing fighter {fighter_data.get('name')}: {e}")
                self.db.rollback()
                continue
        
        self.db.commit()
        logger.info(f"✅ Fighters: {new_count} new, {updated_count} updated")
    
    def scrape_completed_events(self, limit: Optional[int] = None):
        """Scrape completed events and their fights"""
        logger.info("📅 Scraping completed events...")
        
        events = self.ufc_scraper.get_all_events(page='completed')
        if limit:
            events = events[:limit]
        
        for event_data in events:
            try:
                self._process_event(event_data)
            except Exception as e:
                logger.error(f"Error processing event {event_data.get('name')}: {e}")
                self.db.rollback()
                continue
        
        logger.info(f"✅ Completed events processed")
    
    def scrape_upcoming_events(self):
        """Scrape upcoming event schedule"""
        logger.info("📅 Scraping upcoming events...")
        
        events = self.ufc_scraper.get_all_events(page='upcoming')
        
        for event_data in events:
            try:
                self._process_event(event_data)
            except Exception as e:
                logger.error(f"Error processing upcoming event: {e}")
                self.db.rollback()
                continue
        
        logger.info(f"✅ Upcoming events processed")
    
    def _process_event(self, event_data: dict):
        """Process a single event and its fights"""
        # Check if event exists
        event = self.db.query(Event).filter_by(ufc_id=event_data['ufc_id']).first()
        
        if not event:
            event = Event(
                ufc_id=event_data['ufc_id'],
                name=event_data['name'],
                date=event_data.get('date'),
                location=event_data.get('location'),
                status=event_data.get('status', 'completed')
            )
            self.db.add(event)
            self.db.commit()
        
        # Get fights for this event
        fights = self.ufc_scraper.get_event_fights(event_data['url'])
        
        for fight_data in fights:
            try:
                self._process_fight(fight_data, event.id)
            except Exception as e:
                logger.debug(f"Error processing fight: {e}")
                continue
    
    def _process_fight(self, fight_data: dict, event_id: int):
        """Process a single fight"""
        # Check if fight exists
        fight = self.db.query(Fight).filter_by(ufc_id=fight_data['ufc_id']).first()
        
        if fight:
            return  # Already have this fight
        
        # Get or create fighters
        fighter_a = self._get_or_create_fighter(fight_data['fighter_a_id'], fight_data['fighter_a_name'])
        fighter_b = self._get_or_create_fighter(fight_data['fighter_b_id'], fight_data['fighter_b_name'])
        
        # Determine winner
        winner_id = None
        if fight_data.get('winner_id') == fight_data['fighter_a_id']:
            winner_id = fighter_a.id if fighter_a else None
        elif fight_data.get('winner_id') == fight_data['fighter_b_id']:
            winner_id = fighter_b.id if fighter_b else None
        
        # Create fight
        fight = Fight(
            ufc_id=fight_data['ufc_id'],
            event_id=event_id,
            fighter_a_id=fighter_a.id if fighter_a else None,
            fighter_b_id=fighter_b.id if fighter_b else None,
            winner_id=winner_id,
            method=fight_data.get('method'),
            end_round=fight_data.get('end_round'),
            end_time=fight_data.get('end_time'),
            card_position=fight_data.get('card_position')
        )
        self.db.add(fight)
        self.db.commit()
        
        # Get fight stats
        if fight_data.get('fight_url'):
            stats_a, stats_b = self.ufc_scraper.get_fight_stats(fight_data['fight_url'])
            
            if stats_a and fighter_a:
                self._save_fight_stats(fight.id, fighter_a.id, stats_a)
            if stats_b and fighter_b:
                self._save_fight_stats(fight.id, fighter_b.id, stats_b)
    
    def _get_or_create_fighter(self, ufc_id: str, name: str) -> Optional[Fighter]:
        """Get existing fighter or create placeholder"""
        if not ufc_id:
            return None
        
        fighter = self.db.query(Fighter).filter_by(ufc_id=ufc_id).first()
        
        if not fighter and name:
            # Create placeholder
            fighter = Fighter(
                ufc_id=ufc_id,
                name=name
            )
            self.db.add(fighter)
            self.db.commit()
        
        return fighter
    
    def _save_fight_stats(self, fight_id: int, fighter_id: int, stats: dict):
        """Save fight statistics"""
        try:
            stat_record = FightStat(
                fight_id=fight_id,
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
            self.db.add(stat_record)
            self.db.commit()
        except Exception as e:
            logger.debug(f"Error saving stats: {e}")
            self.db.rollback()
    
    def scrape_current_odds(self):
        """Scrape current betting odds"""
        logger.info("💰 Scraping current odds...")
        
        odds_data = self.odds_scraper.get_bestfightodds()
        
        # TODO: Match odds to fights in database
        # This requires name matching logic
        
        logger.info(f"✅ Scraped {len(odds_data)} odds entries")


if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run pipeline
    pipeline = UFCPipeline()
    pipeline.run_full_scrape(fighter_limit=20)  # Start with 20 for testing
