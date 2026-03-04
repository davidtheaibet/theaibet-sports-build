"""Monitor scrape progress"""
import sys
sys.path.insert(0, 'src')
from models import get_session, Fighter, Event, Fight, FightStat
import time

def show_stats():
    db = get_session()
    try:
        fighters = db.query(Fighter).count()
        events = db.query(Event).count()
        fights = db.query(Fight).count()
        stats = db.query(FightStat).count()
        
        print(f"📊 Current Counts:")
        print(f"   Fighters: {fighters}")
        print(f"   Events: {events}")
        print(f"   Fights: {fights}")
        print(f"   Fight Stats: {stats}")
    finally:
        db.close()

if __name__ == '__main__':
    show_stats()
