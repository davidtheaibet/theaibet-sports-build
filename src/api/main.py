from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload
from typing import List, Optional
from datetime import date, datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Fighter, Event, Fight, FightStat, Odds, get_session
from pydantic import BaseModel

app = FastAPI(
    title="TheAIBet Sports API",
    description="UFC data API for predictions and analysis",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== PYDANTIC MODELS ==============

class FighterSummary(BaseModel):
    id: int
    name: str
    nickname: Optional[str]
    weight_class: Optional[str]
    record: str
    
    class Config:
        from_attributes = True


class FighterDetail(BaseModel):
    id: int
    name: str
    nickname: Optional[str]
    weight_class: Optional[str]
    record_wins: int
    record_losses: int
    record_draws: int
    height: Optional[str]
    reach: Optional[str]
    stance: Optional[str]
    age: Optional[int]
    nationality: Optional[str]
    
    class Config:
        from_attributes = True


class EventSummary(BaseModel):
    id: int
    name: str
    date: Optional[date]
    location: Optional[str]
    status: str
    
    class Config:
        from_attributes = True


class FightSummary(BaseModel):
    id: int
    fighter_a_name: str
    fighter_b_name: str
    winner_name: Optional[str]
    method: Optional[str]
    date: Optional[date]
    
    class Config:
        from_attributes = True


class StatsSummary(BaseModel):
    total_fighters: int
    total_events: int
    total_fights: int
    upcoming_fights: int
    weight_classes: dict


# ============== ENDPOINTS ==============

@app.get("/")
def root():
    return {
        "name": "TheAIBet Sports API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "fighters": "/fighters",
            "events": "/events",
            "upcoming": "/upcoming",
            "stats": "/stats/summary"
        }
    }


@app.get("/fighters", response_model=List[FighterSummary])
def list_fighters(
    weight_class: Optional[str] = Query(None, description="Filter by weight class (e.g., 'Lightweight')"),
    search: Optional[str] = Query(None, description="Search by name"),
    min_wins: Optional[int] = Query(None, description="Minimum wins"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List UFC fighters with filters"""
    db = get_session()
    try:
        query = db.query(Fighter)
        
        if weight_class:
            query = query.filter(Fighter.weight_class.ilike(f"%{weight_class}%"))
        
        if search:
            query = query.filter(Fighter.name.ilike(f"%{search}%"))
        
        if min_wins:
            query = query.filter(Fighter.record_wins >= min_wins)
        
        fighters = query.order_by(Fighter.record_wins.desc()).offset(offset).limit(limit).all()
        return fighters
    finally:
        db.close()


@app.get("/fighters/{fighter_id}", response_model=FighterDetail)
def get_fighter(fighter_id: int):
    """Get detailed fighter information"""
    db = get_session()
    try:
        fighter = db.query(Fighter).filter(Fighter.id == fighter_id).first()
        if not fighter:
            raise HTTPException(status_code=404, detail="Fighter not found")
        return fighter
    finally:
        db.close()


@app.get("/fighters/{fighter_id}/fights")
def get_fighter_fights(
    fighter_id: int,
    limit: int = Query(20, ge=1, le=100)
):
    """Get fight history for a fighter"""
    db = get_session()
    try:
        fighter = db.query(Fighter).filter(Fighter.id == fighter_id).first()
        if not fighter:
            raise HTTPException(status_code=404, detail="Fighter not found")
        
        fights = db.query(Fight).filter(
            (Fight.fighter_a_id == fighter_id) | (Fight.fighter_b_id == fighter_id)
        ).options(
            joinedload(Fight.fighter_a),
            joinedload(Fight.fighter_b),
            joinedload(Fight.winner),
            joinedload(Fight.event)
        ).order_by(desc(Fight.id)).limit(limit).all()
        
        result = []
        for fight in fights:
            opponent = fight.fighter_b if fight.fighter_a_id == fighter_id else fight.fighter_a
            result_type = "Win" if fight.winner_id == fighter_id else "Loss" if fight.winner_id else "Draw/NC"
            
            result.append({
                "id": fight.id,
                "opponent": opponent.name if opponent else "Unknown",
                "result": result_type,
                "method": fight.method,
                "round": fight.end_round,
                "event": fight.event.name if fight.event else None,
                "date": fight.event.date if fight.event else None,
                "is_title_fight": fight.is_title_fight
            })
        
        return result
    finally:
        db.close()


@app.get("/fighters/{fighter_id}/stats")
def get_fighter_stats(fighter_id: int):
    """Get aggregated statistics for a fighter"""
    db = get_session()
    try:
        fighter = db.query(Fighter).filter(Fighter.id == fighter_id).first()
        if not fighter:
            raise HTTPException(status_code=404, detail="Fighter not found")
        
        stats = db.query(FightStat).filter(FightStat.fighter_id == fighter_id).all()
        
        if not stats:
            return {"message": "No statistics available"}
        
        total_fights = len(stats)
        
        return {
            "total_fights_analyzed": total_fights,
            "avg_sig_strikes_landed": sum(s.sig_strikes_landed for s in stats) / total_fights,
            "avg_sig_strikes_accuracy": sum(s.sig_strike_pct for s in stats if s.sig_strike_pct) / len([s for s in stats if s.sig_strike_pct]) if any(s.sig_strike_pct for s in stats) else 0,
            "avg_takedowns_landed": sum(s.takedowns_landed for s in stats) / total_fights,
            "avg_submissions_attempted": sum(s.submissions_attempted for s in stats) / total_fights,
            "avg_knockdowns": sum(s.knockdowns_scored for s in stats) / total_fights,
            "total_knockdowns": sum(s.knockdowns_scored for s in stats),
            "total_submissions_attempted": sum(s.submissions_attempted for s in stats)
        }
    finally:
        db.close()


@app.get("/events", response_model=List[EventSummary])
def list_events(
    status: Optional[str] = Query(None, description="Filter by status: upcoming, completed"),
    year: Optional[int] = Query(None, description="Filter by year"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """List UFC events"""
    db = get_session()
    try:
        query = db.query(Event)
        
        if status:
            query = query.filter(Event.status == status)
        
        if year:
            query = query.filter(func.strftime('%Y', Event.date) == str(year))
        
        events = query.order_by(desc(Event.date)).offset(offset).limit(limit).all()
        return events
    finally:
        db.close()


@app.get("/events/{event_id}")
def get_event(event_id: int):
    """Get event details with fight card"""
    db = get_session()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        fights = db.query(Fight).filter(Fight.event_id == event_id).options(
            joinedload(Fight.fighter_a),
            joinedload(Fight.fighter_b),
            joinedload(Fight.winner)
        ).order_by(Fight.card_position).all()
        
        fight_card = []
        for fight in fights:
            fight_card.append({
                "id": fight.id,
                "fighter_a": fight.fighter_a.name if fight.fighter_a else "TBD",
                "fighter_b": fight.fighter_b.name if fight.fighter_b else "TBD",
                "winner": fight.winner.name if fight.winner else None,
                "method": fight.method,
                "round": fight.end_round,
                "is_title_fight": fight.is_title_fight,
                "weight_class": fight.weight_class
            })
        
        return {
            "id": event.id,
            "name": event.name,
            "date": event.date,
            "location": event.location,
            "status": event.status,
            "fight_card": fight_card
        }
    finally:
        db.close()


@app.get("/upcoming")
def get_upcoming_fights(limit: int = Query(20, ge=1, le=100)):
    """Get upcoming scheduled fights"""
    db = get_session()
    try:
        upcoming_fights = db.query(Fight).join(Event).filter(
            Event.status == 'upcoming'
        ).options(
            joinedload(Fight.fighter_a),
            joinedload(Fight.fighter_b),
            joinedload(Fight.event)
        ).order_by(Event.date).limit(limit).all()
        
        result = []
        for fight in upcoming_fights:
            result.append({
                "id": fight.id,
                "event": fight.event.name,
                "date": fight.event.date,
                "fighter_a": fight.fighter_a.name if fight.fighter_a else "TBD",
                "fighter_b": fight.fighter_b.name if fight.fighter_b else "TBD",
                "weight_class": fight.weight_class,
                "is_title_fight": fight.is_title_fight
            })
        
        return result
    finally:
        db.close()


@app.get("/stats/summary")
def get_stats_summary():
    """Get database statistics summary"""
    db = get_session()
    try:
        fighter_count = db.query(Fighter).count()
        event_count = db.query(Event).count()
        fight_count = db.query(Fight).count()
        upcoming_count = db.query(Fight).join(Event).filter(Event.status == 'upcoming').count()
        
        # Weight class distribution
        weight_classes = db.query(
            Fighter.weight_class,
            func.count(Fighter.id).label('count')
        ).filter(Fighter.weight_class.isnot(None)).group_by(Fighter.weight_class).all()
        
        return StatsSummary(
            total_fighters=fighter_count,
            total_events=event_count,
            total_fights=fight_count,
            upcoming_fights=upcoming_count,
            weight_classes={wc: count for wc, count in weight_classes if wc}
        )
    finally:
        db.close()


@app.get("/fights/{fight_id}")
def get_fight(fight_id: int):
    """Get detailed fight information"""
    db = get_session()
    try:
        fight = db.query(Fight).filter(Fight.id == fight_id).options(
            joinedload(Fight.fighter_a),
            joinedload(Fight.fighter_b),
            joinedload(Fight.winner),
            joinedload(Fight.event),
            joinedload(Fight.stats)
        ).first()
        
        if not fight:
            raise HTTPException(status_code=404, detail="Fight not found")
        
        stats_data = []
        for stat in fight.stats:
            stats_data.append({
                "fighter": stat.fighter.name if stat.fighter else None,
                "sig_strikes_landed": stat.sig_strikes_landed,
                "sig_strikes_attempted": stat.sig_strikes_attempted,
                "sig_strike_pct": stat.sig_strike_pct,
                "takedowns_landed": stat.takedowns_landed,
                "takedowns_attempted": stat.takedowns_attempted,
                "submissions_attempted": stat.submissions_attempted,
                "knockdowns": stat.knockdowns_scored
            })
        
        return {
            "id": fight.id,
            "event": fight.event.name if fight.event else None,
            "date": fight.event.date if fight.event else None,
            "fighter_a": fight.fighter_a.name if fight.fighter_a else None,
            "fighter_b": fight.fighter_b.name if fight.fighter_b else None,
            "winner": fight.winner.name if fight.winner else None,
            "method": fight.method,
            "method_details": fight.method_details,
            "round": fight.end_round,
            "time": fight.end_time,
            "weight_class": fight.weight_class,
            "is_title_fight": fight.is_title_fight,
            "statistics": stats_data
        }
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
