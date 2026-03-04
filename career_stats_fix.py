#!/usr/bin/env python3
"""
UFC Fighter Career Stats - FIXED VERSION
Updates all fighters with career statistics from UFC Stats
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
        logging.FileHandler('career_stats_fix.log')
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scrapers.ufc_scraper import UFCScraper
from models import Fighter, get_session, init_db

class CareerStatsUpdater:
    def __init__(self):
        self.scraper = UFCScraper(delay=1.5, max_retries=3)
        self.updated = 0
        self.errors = 0
        
    def update_fighter(self, db, fighter):
        """Update a fighter with career statistics"""
        try:
            url = f"http://www.ufcstats.com/fighter-details/{fighter.ufc_id}"
            soup = self.scraper._get(url)
            if not soup:
                logger.warning(f"No page for {fighter.name}")
                return False
            
            # Career stats section
            stats_items = soup.find_all('li', class_='b-list__box-list-item')
            
            for item in stats_items:
                text = item.get_text(strip=True)
                
                if text.startswith('SLpM:'):
                    val = text.replace('SLpM:', '').strip()
                    if val != '--':
                        fighter.slpm = float(val)
                elif text.startswith('Str. Acc.:'):
                    val = text.replace('Str. Acc.:', '').strip().replace('%', '')
                    if val != '--':
                        fighter.sig_strike_acc = float(val) / 100
                elif text.startswith('SApM:'):
                    val = text.replace('SApM:', '').strip()
                    if val != '--':
                        fighter.sapm = float(val)
                elif text.startswith('Str. Def:'):
                    val = text.replace('Str. Def:', '').strip().replace('%', '')
                    if val != '--':
                        fighter.sig_strike_def = float(val) / 100
                elif text.startswith('TD Avg.:'):
                    val = text.replace('TD Avg.:', '').strip()
                    if val != '--':
                        fighter.td_avg = float(val)
                elif text.startswith('TD Acc.:'):
                    val = text.replace('TD Acc.:', '').strip().replace('%', '')
                    if val != '--':
                        fighter.td_acc = float(val) / 100
                elif text.startswith('TD Def:'):
                    val = text.replace('TD Def:', '').strip().replace('%', '')
                    if val != '--':
                        fighter.td_def = float(val) / 100
                elif text.startswith('Sub. Avg.:'):
                    val = text.replace('Sub. Avg.:', '').strip()
                    if val != '--':
                        fighter.sub_avg = float(val)
                elif text.startswith('Weight:'):
                    weight_str = text.replace('Weight:', '').strip()
                    try:
                        fighter.weight_lbs = int(weight_str.replace('lbs.', '').strip())
                    except:
                        pass
            
            # Commit immediately after each fighter
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating {fighter.name}: {e}")
            db.rollback()
            return False

    def run(self):
        """Run the update"""
        logger.info("🚀 STARTING FIGHTER CAREER STATS UPDATE (FIXED)")
        logger.info(f"Start time: {datetime.now()}")
        
        init_db()
        db = get_session()
        
        try:
            # Get fighters without career stats
            fighters = db.query(Fighter).filter(Fighter.slpm == None).all()
            total = len(fighters)
            logger.info(f"Found {total} fighters needing career stats")
            
            for i, fighter in enumerate(fighters, 1):
                if self.update_fighter(db, fighter):
                    self.updated += 1
                else:
                    self.errors += 1
                
                # Progress every 50
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{total} processed | Updated: {self.updated} | Errors: {self.errors}")
                
                # Milestone every 500
                if i % 500 == 0:
                    logger.info(f"🏁 MILESTONE: {i}/{total} | Updated: {self.updated}")
                    
        finally:
            db.close()
        
        logger.info("=" * 60)
        logger.info("✅ UPDATE COMPLETE!")
        logger.info(f"Fighters updated: {self.updated}")
        logger.info(f"Errors: {self.errors}")
        logger.info(f"End time: {datetime.now()}")

if __name__ == "__main__":
    updater = CareerStatsUpdater()
    updater.run()
