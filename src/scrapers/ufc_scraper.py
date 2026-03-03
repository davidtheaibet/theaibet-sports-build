"""
Comprehensive UFC Data Scraper
Scrapes fighters, events, fights, and statistics from ufcstats.com
"""
import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import logging
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://www.ufcstats.com"


class UFCScraper:
    """UFC Stats scraper with rate limiting and error handling"""
    
    def __init__(self, delay: float = 1.5, max_retries: int = 3):
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.stats = {'requests': 0, 'errors': 0, 'cached': 0}
    
    def _get(self, url: str) -> Optional[BeautifulSoup]:
        """Make request with retry logic"""
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.delay)
                response = self.session.get(url, timeout=30)
                self.stats['requests'] += 1
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
            except Exception as e:
                self.stats['errors'] += 1
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * 2)
                else:
                    logger.error(f"Failed to fetch {url}")
                    return None
        return None
    
    # ==================== FIGHTERS ====================
    
    def get_all_fighters(self) -> List[Dict]:
        """Get complete fighter list from all pages (A-Z)"""
        fighters = []
        letters = 'abcdefghijklmnopqrstuvwxyz'
        
        for letter in letters:
            url = f"{BASE_URL}/statistics/fighters?char={letter}&page=all"
            logger.info(f"Fetching fighters starting with '{letter.upper()}'...")
            
            soup = self._get(url)
            if not soup:
                continue
            
            table = soup.find('table', class_='b-statistics__table')
            if not table:
                continue
            
            rows = table.find_all('tr', class_='b-statistics__table-row')
            
            for row in rows:
                try:
                    if 'b-statistics__table-row_type_head' in row.get('class', []):
                        continue
                    
                    link = row.find('a', class_='b-link_style_black')
                    if not link:
                        continue
                    
                    name = link.text.strip()
                    href = link.get('href', '')
                    ufc_id = href.split('/')[-1] if '/' in href else None
                    
                    cols = row.find_all('td')
                    weight_class = cols[5].text.strip() if len(cols) >= 6 else None
                    
                    fighters.append({
                        'name': name,
                        'ufc_id': ufc_id,
                        'url': href,
                        'weight_class': weight_class
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing fighter row: {e}")
                    continue
            
            count = len([f for f in fighters if f.get('name') and f['name'][0].lower() == letter])
            logger.info(f"  Found {count} fighters")
        
        logger.info(f"✅ Total fighters found: {len(fighters)}")
        return fighters
    
    def get_fighter_details(self, url: str) -> Dict:
        """Get detailed fighter information"""
        soup = self._get(url)
        if not soup:
            return {}
        
        details = {'ufc_id': url.split('/')[-1]}
        
        try:
            # Name
            name_elem = soup.find('span', class_='b-content__title-highlight')
            if name_elem:
                details['name'] = name_elem.text.strip()
            
            # Nickname
            nickname_elem = soup.find('p', class_='b-content__Nickname')
            details['nickname'] = nickname_elem.text.strip() if nickname_elem else None
            
            # Record
            record_elem = soup.find('span', class_='b-content__title-record')
            if record_elem:
                record_match = re.search(r'(\d+)-(\d+)-(\d+)', record_elem.text)
                if record_match:
                    details['record_wins'] = int(record_match.group(1))
                    details['record_losses'] = int(record_match.group(2))
                    details['record_draws'] = int(record_match.group(3))
            
            # Physical stats
            for item in soup.find_all('li', class_='b-list__box-list-item'):
                text = item.get_text(strip=True)
                
                if text.startswith('Height:'):
                    details['height'] = text.replace('Height:', '').strip()
                elif text.startswith('Reach:'):
                    details['reach'] = text.replace('Reach:', '').strip()
                elif text.startswith('STANCE:'):
                    details['stance'] = text.replace('STANCE:', '').strip()
                elif text.startswith('DOB:'):
                    dob_str = text.replace('DOB:', '').strip()
                    try:
                        details['date_of_birth'] = datetime.strptime(dob_str, '%b %d, %Y').date()
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Error parsing fighter details: {e}")
        
        return details
    
    # ==================== EVENTS ====================
    
    def get_all_events(self, page: str = 'completed') -> List[Dict]:
        """Get all events (completed or upcoming)"""
        events = []
        page_num = 1
        
        while True:
            url = f"{BASE_URL}/statistics/events/{page}?page={page_num}"
            logger.info(f"Fetching events page {page_num}...")
            
            soup = self._get(url)
            if not soup:
                break
            
            table = soup.find('table', class_='b-statistics__table-events')
            if not table:
                break
            
            rows = table.find_all('tr', class_='b-statistics__table-row')
            if not rows or len(rows) <= 1:
                break
            
            for row in rows[1:]:  # Skip header
                try:
                    link = row.find('a', class_='b-link_style_black')
                    if not link:
                        continue
                    
                    name = link.text.strip()
                    href = link.get('href', '')
                    ufc_id = href.split('/')[-1] if '/' in href else None
                    
                    # Get date
                    date_elem = row.find('span', class_='b-statistics__date')
                    event_date = None
                    if date_elem:
                        try:
                            event_date = datetime.strptime(date_elem.text.strip(), '%B %d, %Y').date()
                        except:
                            pass
                    
                    # Get location
                    location_elem = row.find('td', class_='b-statistics__table-col_l_align_left')
                    location = location_elem.text.strip() if location_elem else None
                    
                    events.append({
                        'name': name,
                        'ufc_id': ufc_id,
                        'url': href,
                        'date': event_date,
                        'location': location,
                        'status': 'completed' if page == 'completed' else 'upcoming'
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing event row: {e}")
                    continue
            
            # Check for next page
            pagination = soup.find('div', class_='pagination')
            if not pagination or not pagination.find('a', class_='b-statistics__pagination-item', string='next'):
                break
            
            page_num += 1
        
        logger.info(f"✅ Total events found: {len(events)}")
        return events
    
    # ==================== FIGHTS ====================
    
    def get_event_fights(self, url: str) -> List[Dict]:
        """Get all fights from an event"""
        soup = self._get(url)
        if not soup:
            return []
        
        fights = []
        
        try:
            # Find event info
            event_name = soup.find('span', class_='b-content__title-highlight')
            event_name = event_name.text.strip() if event_name else "Unknown"
            
            # Get fight rows
            fight_rows = soup.find_all('tr', class_='b-fight-details__table-row')
            
            for position, row in enumerate(fight_rows, 1):
                try:
                    # Skip header rows
                    if 'b-fight-details__table-row__head' in row.get('class', []):
                        continue
                    
                    # Get fight link
                    fight_link = row.get('data-link')
                    if not fight_link:
                        continue
                    
                    fight_id = fight_link.split('/')[-1]
                    
                    # Get fighters
                    fighter_links = row.find_all('a', class_='b-link_style_black')
                    if len(fighter_links) < 2:
                        continue
                    
                    fighter_a_name = fighter_links[0].text.strip()
                    fighter_a_url = fighter_links[0].get('href', '')
                    fighter_a_id = fighter_a_url.split('/')[-1] if fighter_a_url else None
                    
                    fighter_b_name = fighter_links[1].text.strip()
                    fighter_b_url = fighter_links[1].get('href', '')
                    fighter_b_id = fighter_b_url.split('/')[-1] if fighter_b_url else None
                    
                    # Get result
                    result_elem = row.find('i', class_='b-flag__text')
                    result = result_elem.text.strip() if result_elem else None
                    
                    # Determine winner
                    winner_id = None
                    if result and 'win' in result.lower():
                        # First fighter is winner
                        winner_id = fighter_a_id
                    
                    # Get method
                    cols = row.find_all('td')
                    method = cols[7].text.strip() if len(cols) > 7 else None
                    
                    # Get round and time
                    round_num = None
                    end_time = None
                    if len(cols) > 8:
                        try:
                            round_num = int(cols[8].text.strip())
                        except:
                            pass
                    if len(cols) > 9:
                        end_time = cols[9].text.strip()
                    
                    fights.append({
                        'ufc_id': fight_id,
                        'fighter_a_name': fighter_a_name,
                        'fighter_a_id': fighter_a_id,
                        'fighter_b_name': fighter_b_name,
                        'fighter_b_id': fighter_b_id,
                        'winner_id': winner_id,
                        'method': method,
                        'end_round': round_num,
                        'end_time': end_time,
                        'card_position': position,
                        'fight_url': fight_link
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing fight: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error getting event fights: {e}")
        
        return fights
    
    def get_fight_stats(self, url: str) -> Tuple[Dict, Dict]:
        """Get detailed statistics for both fighters in a fight"""
        soup = self._get(url)
        if not soup:
            return {}, {}
        
        stats_a = {'knockdowns': 0}
        stats_b = {'knockdowns': 0}
        
        try:
            # Get fighter names
            fighter_sections = soup.find_all('div', class_='b-fight-details__person')
            if len(fighter_sections) >= 2:
                stats_a['fighter_name'] = fighter_sections[0].find('a').text.strip() if fighter_sections[0].find('a') else None
                stats_b['fighter_name'] = fighter_sections[1].find('a').text.strip() if fighter_sections[1].find('a') else None
            
            # Get stats tables
            totals_table = soup.find('table', class_='b-fight-details__table_tot')
            significant_table = soup.find('table', class_='b-fight-details__table_significant-strikes')
            
            if totals_table:
                rows = totals_table.find_all('tr', class_='b-fight-details__table-row')
                if len(rows) >= 2:
                    # Parse totals row for both fighters
                    self._parse_totals_row(rows[1], stats_a, stats_b)
            
            if significant_table:
                rows = significant_table.find_all('tr', class_='b-fight-details__table-row')
                if len(rows) >= 2:
                    self._parse_significant_row(rows[1], stats_a, stats_b)
            
        except Exception as e:
            logger.error(f"Error parsing fight stats: {e}")
        
        return stats_a, stats_b
    
    def _parse_totals_row(self, row, stats_a: Dict, stats_b: Dict):
        """Parse totals statistics row"""
        try:
            cols = row.find_all('td', class_='b-fight-details__table-col')
            if len(cols) >= 10:
                # Knockdowns
                stats_a['knockdowns'] = self._parse_stat(cols[1].text)
                stats_b['knockdowns'] = self._parse_stat(cols[2].text)
                
                # Significant strikes
                sig_str = cols[3].text.strip().split(' of ')
                if len(sig_str) == 2:
                    stats_a['sig_strikes_landed'] = self._parse_stat(sig_str[0])
                    stats_a['sig_strikes_attempted'] = self._parse_stat(sig_str[1])
                
                sig_str_b = cols[4].text.strip().split(' of ')
                if len(sig_str_b) == 2:
                    stats_b['sig_strikes_landed'] = self._parse_stat(sig_str_b[0])
                    stats_b['sig_strikes_attempted'] = self._parse_stat(sig_str_b[1])
                
                # Total strikes
                total_str = cols[7].text.strip().split(' of ')
                if len(total_str) == 2:
                    stats_a['total_strikes_landed'] = self._parse_stat(total_str[0])
                    stats_a['total_strikes_attempted'] = self._parse_stat(total_str[1])
                
                total_str_b = cols[8].text.strip().split(' of ')
                if len(total_str_b) == 2:
                    stats_b['total_strikes_landed'] = self._parse_stat(total_str_b[0])
                    stats_b['total_strikes_attempted'] = self._parse_stat(total_str_b[1])
                
                # Takedowns
                td = cols[9].text.strip().split(' of ')
                if len(td) == 2:
                    stats_a['takedowns_landed'] = self._parse_stat(td[0])
                    stats_a['takedowns_attempted'] = self._parse_stat(td[1])
                
                td_b = cols[10].text.strip().split(' of ') if len(cols) > 10 else []
                if len(td_b) == 2:
                    stats_b['takedowns_landed'] = self._parse_stat(td_b[0])
                    stats_b['takedowns_attempted'] = self._parse_stat(td_b[1])
                
                # Submissions
                if len(cols) > 12:
                    stats_a['submissions_attempted'] = self._parse_stat(cols[13].text)
                if len(cols) > 13:
                    stats_b['submissions_attempted'] = self._parse_stat(cols[14].text)
                
        except Exception as e:
            logger.debug(f"Error parsing totals: {e}")
    
    def _parse_significant_row(self, row, stats_a: Dict, stats_b: Dict):
        """Parse significant strikes row"""
        try:
            cols = row.find_all('td', class_='b-fight-details__table-col')
            if len(cols) >= 6:
                # Head strikes
                head = cols[3].text.strip().split(' of ')
                if len(head) == 2:
                    stats_a['sig_strikes_head_landed'] = self._parse_stat(head[0])
                    stats_a['sig_strikes_head_attempted'] = self._parse_stat(head[1])
                
                head_b = cols[4].text.strip().split(' of ')
                if len(head_b) == 2:
                    stats_b['sig_strikes_head_landed'] = self._parse_stat(head_b[0])
                    stats_b['sig_strikes_head_attempted'] = self._parse_stat(head_b[1])
                
                # Body strikes
                body = cols[5].text.strip().split(' of ')
                if len(body) == 2:
                    stats_a['sig_strikes_body_landed'] = self._parse_stat(body[0])
                    stats_a['sig_strikes_body_attempted'] = self._parse_stat(body[1])
                
                body_b = cols[6].text.strip().split(' of ')
                if len(body_b) == 2:
                    stats_b['sig_strikes_body_landed'] = self._parse_stat(body_b[0])
                    stats_b['sig_strikes_body_attempted'] = self._parse_stat(body_b[1])
                
        except Exception as e:
            logger.debug(f"Error parsing significant strikes: {e}")
    
    def _parse_stat(self, text) -> int:
        """Parse numeric stat from text"""
        try:
            return int(text.strip())
        except:
            return 0
    
    def print_stats(self):
        """Print scraping statistics"""
        logger.info(f"📊 Scraping Stats: {self.stats['requests']} requests, {self.stats['errors']} errors")
