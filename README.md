# TheAIBet Sports Data System

Complete UFC data collection and API system for AI predictions.

## Features

- ✅ **Fighter Database** — Complete profiles, records, physical stats
- ✅ **Event History** — All UFC events with dates and locations
- ✅ **Fight Results** — Every fight with detailed outcomes
- ✅ **Fight Statistics** — Strikes, takedowns, control time, submissions
- ✅ **Upcoming Schedule** — Future events and fight cards
- 🔄 **Odds Integration** — Historical and current betting lines
- 🔄 **Prediction Features** — ML-ready data exports

## Quick Start

### 1. Install Dependencies

```bash
cd theaibet-sports-build
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
cd src
python models.py
```

### 3. Run Data Pipeline

```bash
cd src
python pipeline.py
```

This will scrape:
- All fighters (A-Z)
- All completed events
- All upcoming events
- Fight statistics
- Current odds

**For testing with limited data:**
```bash
python -c "from pipeline import UFCPipeline; from models import init_db; init_db(); p = UFCPipeline(); p.run_full_scrape(fighter_limit=50)"
```

### 4. Start API Server

```bash
cd src/api
python main.py
```

API available at: http://localhost:8000

Interactive docs: http://localhost:8000/docs

---

## API Endpoints

### Fighters
| Endpoint | Description |
|----------|-------------|
| `GET /fighters` | List fighters (filter: weight_class, search, min_wins) |
| `GET /fighters/{id}` | Fighter details |
| `GET /fighters/{id}/fights` | Fight history |
| `GET /fighters/{id}/stats` | Aggregated statistics |

### Events
| Endpoint | Description |
|----------|-------------|
| `GET /events` | List events (filter: status, year) |
| `GET /events/{id}` | Event details + fight card |
| `GET /upcoming` | Upcoming fights |

### Fights
| Endpoint | Description |
|----------|-------------|
| `GET /fights/{id}` | Fight details + statistics |

### Stats
| Endpoint | Description |
|----------|-------------|
| `GET /stats/summary` | Database overview |

---

## Project Structure

```
theaibet-sports-build/
├── src/
│   ├── models.py              # SQLAlchemy database models
│   ├── scrapers/
│   │   ├── ufc_scraper.py     # UFC Stats scraper
│   │   └── odds_scraper.py    # Odds scraper
│   ├── api/
│   │   └── main.py            # FastAPI application
│   └── pipeline.py            # Data orchestration
├── data/
│   └── ufc.db                 # SQLite database (auto-created)
├── docs/
│   └── DATA_SOURCES.md        # Data source research
└── requirements.txt
```

---

## Data Sources

### Primary: UFC Stats (ufcstats.com)
- Complete historical UFC data
- Fighter profiles and statistics
- Event listings
- Detailed fight metrics

### Secondary: Best Fight Odds (bestfightodds.com)
- Current betting lines
- Multiple sportsbook comparison
- Line movement tracking

---

## Database Schema

### fighters
- Profile information
- Physical stats (height, reach, stance)
- Fight records
- Nationality, team/gym

### events
- Event names and dates
- Locations and venues
- Status (upcoming/completed)

### fights
- Fighter matchups
- Results and methods
- Round/time ended
- Title fight flags

### fight_stats
- Per-fighter statistics per fight
- Significant strikes (head/body/leg)
- Takedowns and submissions
- Control time and knockdowns

### odds
- Betting lines by sportsbook
- Opening/closing odds
- Line movement history

---

## Rate Limiting & Ethics

The scraper is configured with:
- 1.5 second delay between requests
- Retry logic for failed requests
- User-Agent identification
- Respects server load

---

## Next Steps

1. **Scale Data Collection** — Run full scrape (takes several hours)
2. **Add Odds History** — Integrate historical odds from multiple sources
3. **Feature Engineering** — Build ML features from raw statistics
4. **Prediction Models** — Train models on historical data
5. **Real-time Updates** — Automate daily scraping

---

## License

Private - TheAIBet internal use only
