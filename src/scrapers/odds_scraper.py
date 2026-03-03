"""
Odds Scraper
Scrapes betting odds from various sources
"""
import requests
from bs4 import BeautifulSoup
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class OddsScraper:
    """Scraper for UFC betting odds"""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_bestfightodds(self) -> List[Dict]:
        """
        Scrape current UFC odds from bestfightodds.com
        Returns list of upcoming fights with odds
        """
        url = "https://www.bestfightodds.com/"
        odds_data = []
        
        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find fight tables
            tables = soup.find_all('table', class_='content-list')
            
            for table in tables:
                rows = table.find_all('tr', class_='row')
                
                for row in rows:
                    try:
                        # Get fighter names
                        fighter_links = row.find_all('a', class_='blue-link')
                        if len(fighter_links) < 2:
                            continue
                        
                        fighter_a = fighter_links[0].text.strip()
                        fighter_b = fighter_links[1].text.strip()
                        
                        # Get odds
                        odds_cells = row.find_all('td', class_='price')
                        if len(odds_cells) < 2:
                            continue
                        
                        odds_a = self._parse_odds(odds_cells[0].text)
                        odds_b = self._parse_odds(odds_cells[1].text)
                        
                        # Get event/date info
                        event_elem = row.find_previous('h2', class_='event-title')
                        event_name = event_elem.text.strip() if event_elem else None
                        
                        odds_data.append({
                            'event': event_name,
                            'fighter_a': fighter_a,
                            'fighter_b': fighter_b,
                            'odds_a': odds_a,
                            'odds_b': odds_b,
                            'source': 'bestfightodds',
                            'recorded_at': datetime.utcnow()
                        })
                        
                    except Exception as e:
                        logger.debug(f"Error parsing odds row: {e}")
                        continue
            
            logger.info(f"✅ Scraped {len(odds_data)} fights from Best Fight Odds")
            
        except Exception as e:
            logger.error(f"Error scraping Best Fight Odds: {e}")
        
        return odds_data
    
    def get_draftkings_odds(self) -> List[Dict]:
        """
        DraftKings requires API access or special handling
        This is a placeholder for when you have API access
        """
        logger.info("DraftKings API integration required")
        return []
    
    def _parse_odds(self, text: str) -> Optional[int]:
        """Parse American odds from text"""
        try:
            text = text.strip().replace('+', '').replace('−', '-')
            return int(text)
        except:
            return None
    
    def american_to_decimal(self, american: int) -> float:
        """Convert American odds to decimal"""
        if american > 0:
            return (american / 100) + 1
        else:
            return (100 / abs(american)) + 1
    
    def american_to_implied(self, american: int) -> float:
        """Convert American odds to implied probability"""
        if american > 0:
            return 100 / (american + 100)
        else:
            return abs(american) / (abs(american) + 100)
