# UFC Data Sources Research

## Primary Sources

### 1. UFC Stats (ufcstats.com) ⭐ BEST
**What it has:**
- Complete fighter database (5000+ fighters)
- Every UFC fight with detailed statistics
- Event listings with dates
- Fight metrics: strikes, takedowns, control time, submissions

**URL Pattern:**
- Fighters: `http://www.ufcstats.com/statistics/fighters?char=a&page=all`
- Fighter detail: `http://www.ufcstats.com/fighter-details/{id}`
- Events: `http://www.ufcstats.com/statistics/events/completed`
- Fight details: `http://www.ufcstats.com/fight-details/{id}`

**Rate Limiting:** Be respectful, 1-2 second delays

---

### 2. ESPN UFC
**What it has:**
- Fighter rankings
- Recent fight results
- News and updates

**Use case:** Supplementary data, rankings

---

### 3. Tapology
**What it has:**
- Comprehensive fight database (UFC + other promotions)
- Community predictions
- Fight announcements before UFC confirms

**Use case:** Early fight announcements

---

### 4. Odds Sources

#### Sportsbook Odds (Historical)
- **Odds Portal** (oddsportal.com) - Historical odds aggregator
- **Action Network** - Historical lines
- **Bet365, DraftKings** - Current odds (scrape carefully)

#### Best Fight Odds (bestfightodds.com)
- UFC odds comparison
- Line movement tracking
- Opening vs closing odds

---

## Data Architecture

### Tables Needed

1. **fighters**
   - id, ufc_id, name, nickname, weight_class
   - record (wins/losses/draws), height, reach, stance
   - date_of_birth, nationality, team/gym

2. **events**
   - id, ufc_id, name, date, location, venue
   - status (upcoming/completed/cancelled)

3. **fights**
   - id, event_id, fighter_a_id, fighter_b_id
   - winner_id, method, round, time
   - weight_class, is_title_fight, is_main_event

4. **fight_stats** (per fighter per fight)
   - Significant strikes (landed/attempted/%)
   - Total strikes
   - Takedowns (landed/attempted/%)
   - Submissions attempted
   - Control time
   - Knockdowns

5. **odds**
   - fight_id, sportsbook, fighter_id
   - opening_line, closing_line, current_line
   - timestamp, line_movement

6. **schedules** (upcoming fights)
   - event_id, fight_id, scheduled_date
   - status, broadcast_info

---

## Implementation Strategy

### Phase 1: Core Data
1. Scrape all fighters from UFC Stats
2. Scrape all events (completed + upcoming)
3. Scrape all fights with statistics

### Phase 2: Odds Integration
1. Scrape historical odds from Odds Portal
2. Map odds to fights
3. Track line movement

### Phase 3: Predictions
1. Feature engineering from fight stats
2. Build prediction models
3. Compare predictions to actual results

---

## Technical Stack

- **Language:** Python 3.11+
- **Database:** PostgreSQL (production) / SQLite (dev)
- **ORM:** SQLAlchemy 2.0
- **API:** FastAPI
- **Scraping:** Playwright (JavaScript-heavy sites) + requests/BeautifulSoup
- **Scheduling:** Celery + Redis
- **Monitoring:** Built-in logging

---

## Ethical Scraping Guidelines

1. **Rate limiting:** Max 1 request per second
2. **User-Agent:** Identify yourself properly
3. **Caching:** Don't re-scrape unchanged data
4. **Robots.txt:** Respect site restrictions
5. **Peak hours:** Scrape during off-peak times

---

## Known Challenges

1. **UFC Stats URL structure** uses hashes not sequential IDs
2. **Odds data** is fragmented across many sources
3. **Upcoming fights** announced at different times
4. **Name variations** (Jon Jones vs Jonathan Jones)
5. **Weight class changes** fighters move classes

