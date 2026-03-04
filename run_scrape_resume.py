#!/usr/bin/env python3
"""
UFC Data Scrape - RESUME MODE
Skips fighters already in database, continues from where it left off
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
        logging.FileHandler('scrape_resume.log')
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scrapers.ufc_scraper import UFCScraper
from scrapers.odds_scraper import OddsScraper
from models import Fighter, Event, Fight, FightStat, Odds, get_session, init_db

def log_progress():
    db = get_session()
    try:
        fighters = db.query(Fighter).count()
        events = db.query(Event).count()
        fights = db.query(Fight).count()
        stats = db.query(FightStat).count()
        logger.info(f"📊 PROGRESS - Fighters: {fighters}, Events: {events}, Fights: {fights}, Stats: {stats}")
        return {'fighters': fighters, 'events': events, 'fights': fights, 'stats': stats}
    finally:
        db.close()

def get_or_create_fighter(db, ufc_id, name):
    if not ufc_id:
        return None
    fighter = db.query(Fighter).filter_by(ufc_id=ufc_id).first()
    if not fighter and name:
        fighter = Fighter(ufc_id=ufc_id, name=name)
        db.add(fighter)
        db.commit()
    return fighter

def save_fight_stats(db, fight_id, fighter_id, stats):
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
        db.add(stat_record)
        db.commit()
    except Exception as e:
        logger.debug(f"Error saving stats: {e}")
        db.rollback()

def run_scrape_resume():
    logger.info("🚀 RESTARTING UFC DATA SCRAPE (RESUME MODE)")
    logger.info(f"Start time: {datetime.now()}")
    
    init_db()
    scraper = UFCScraper(delay=1.5, max_retries=3)
    db = get_session()
    
    try:
        # Get current counts
        start_stats = log_progress()
        existing_fighter_count = start_stats['fighters']
        logger.info(f"Resuming from: {existing_fighter_count} fighters already saved")
        
        # ========== PHASE 1: FIGHTERS (RESUME) ==========
        logger.info("=" * 50)
        logger.info("PHASE 1: Scraping remaining fighters")
        logger.info("=" * 50)
        
        fighters = scraper.get_all_fighters()
        logger.info(f"Found {len(fighters)} total fighters on UFC Stats")
        
        # Filter to only fighters NOT in database
        fighters_to_process = []
        for f in fighters:
            existing = db.query(Fighter).filter_by(ufc_id=f['ufc_id']).first()
            if not existing:
                fighters_to_process.append(f)
        
        logger.info(f"Need to process: {len(fighters_to_process)} new fighters")
        
        new_count = 0
        skipped = 0
        
        for i, fighter_data in enumerate(fighters_to_process):
            try:
                # Get detailed info
                details = scraper.get_fighter_details(fighter_data['url'])
                if not details:
                    skipped += 1
                    continue
                
                details['weight_class'] = fighter_data.get('weight_class')
                
                fighter = Fighter(**details)
                db.add(fighter)
                new_count += 1
                
                # Commit every 10 fighters
                if new_count % 10 == 0:
                    db.commit()
                    if new_count % 100 == 0:
                        log_progress()
                
                # Log every 50
                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i+1}/{len(fighters_to_process)} processed ({new_count} new)")
                
            except Exception as e:
                logger.error(f"Error processing {fighter_data.get('name')}: {e}")
                db.rollback()
                continue
        
        db.commit()
        logger.info(f"✅ PHASE 1 COMPLETE: {new_count} new fighters added")
        log_progress()
        
        # ========== PHASE 2: EVENTS & FIGHTS ==========
        logger.info("=" * 50)
        logger.info("PHASE 2: Scraping completed events")
        logger.info("=" * 50)
        
        events = scraper.get_all_events(page='completed')
        logger.info(f"Found {len(events)} completed events")
        
        for i, event_data in enumerate(events):
            try:
                # Check if already exists
                event = db.query(Event).filter_by(ufc_id=event_data['ufc_id']).first()
                if event:
                    logger.info(f"[{i+1}/{len(events)}] SKIP: {event_data['name']} (already exists)")
                    continue
                
                logger.info(f"[{i+1}/{len(events)}] NEW: {event_data['name']}")
                
                event = Event(
                    ufc_id=event_data['ufc_id'],
                    name=event_data['name'],
                    date=event_data.get('date'),
                    location=event_data.get('location'),
                    status='completed'
                )
                db.add(event)
                db.commit()
                
                # Get fights
                fights = scraper.get_event_fights(event_data['url'])
                logger.info(f"  Processing {len(fights)} fights...")
                
                for fight_data in fights:
                    try:
                        # Check if exists
                        if db.query(Fight).filter_by(ufc_id=fight_data['ufc_id']).first():
                            continue
                        
                        fighter_a = get_or_create_fighter(db, fight_data['fighter_a_id'], fight_data['fighter_a_name'])
                        fighter_b = get_or_create_fighter(db, fight_data['fighter_b_id'], fight_data['fighter_b_name'])
                        
                        winner_id = None
                        if fight_data.get('winner_id') == fight_data['fighter_a_id']:
                            winner_id = fighter_a.id if fighter_a else None
                        elif fight_data.get('winner_id') == fight_data['fighter_b_id']:
                            winner_id = fighter_b.id if fighter_b else None
                        
                        fight = Fight(
                            ufc_id=fight_data['ufc_id'],
                            event_id=event.id,
                            fighter_a_id=fighter_a.id if fighter_a else None,
                            fighter_b_id=fighter_b.id if fighter_b else None,
                            winner_id=winner_id,
                            method=fight_data.get('method'),
                            end_round=fight_data.get('end_round'),
                            end_time=fight_data.get('end_time'),
                            card_position=fight_data.get('card_position')
                        )
                        db.add(fight)
                        db.commit()
                        
                        # Get stats
                        if fight_data.get('fight_url'):
                            stats_a, stats_b = scraper.get_fight_stats(fight_data['fight_url'])
                            if stats_a and fighter_a:
                                save_fight_stats(db, fight.id, fighter_a.id, stats_a)
                            if stats_b and fighter_b:
                                save_fight_stats(db, fight.id, fighter_b.id, stats_b)
                        
                    except Exception as e:
                        logger.debug(f"Error processing fight: {e}")
                        db.rollback()
                        continue
                
                if (i + 1) % 10 == 0:
                    log_progress()
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                db.rollback()
                continue
        
        logger.info(f"✅ PHASE 2 COMPLETE")
        log_progress()
        
        # ========== PHASE 3: UPCOMING EVENTS ==========
        logger.info("=" * 50)
        logger.info("PHASE 3: Scraping upcoming events")
        logger.info("=" * 50)
        
        upcoming = scraper.get_all_events(page='upcoming')
        logger.info(f"Found {len(upcoming)} upcoming events")
        
        for event_data in upcoming:
            try:
                event = db.query(Event).filter_by(ufc_id=event_data['ufc_id']).first()
                if not event:
                    event = Event(
                        ufc_id=event_data['ufc_id'],
                        name=event_data['name'],
                        date=event_data.get('date'),
                        location=event_data.get('location'),
                        status='upcoming'
                    )
                    db.add(event)
                    db.commit()
            except Exception as e:
                logger.error(f"Error: {e}")
                db.rollback()
        
        logger.info(f"✅ PHASE 3 COMPLETE")
        
        # ========== PHASE 4: ODDS ==========
        logger.info("=" * 50)
        logger.info("PHASE 4: Scraping odds")
        logger.info("=" * 50)
        
        odds_scraper = OddsScraper(delay=1.0)
        odds_data = odds_scraper.get_bestfightodds()
        logger.info(f"Scraped {len(odds_data)} odds entries")
        
        logger.info(f"✅ PHASE 4 COMPLETE")
        
        # Final
        logger.info("=" * 50)
        logger.info("FULL SCRAPE COMPLETE!")
        logger.info("=" * 50)
        log_progress()
        logger.info(f"End time: {datetime.now()}")
        
    finally:
        db.close()

if __name__ == '__main__':
    run_scrape_resume()
