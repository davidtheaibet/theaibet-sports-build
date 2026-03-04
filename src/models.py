from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class Fighter(Base):
    """UFC Fighter profile"""
    __tablename__ = 'fighters'
    
    id = Column(Integer, primary_key=True)
    ufc_id = Column(String(50), unique=True, index=True)
    
    # Basic info
    name = Column(String(100), nullable=False, index=True)
    nickname = Column(String(100))
    weight_class = Column(String(50), index=True)
    
    # Record
    record_wins = Column(Integer, default=0)
    record_losses = Column(Integer, default=0)
    record_draws = Column(Integer, default=0)
    record_no_contests = Column(Integer, default=0)
    
    # Physical
    height = Column(String(20))           # e.g., "6' 2\""
    reach = Column(String(20))            # e.g., "76\""
    stance = Column(String(20))           # Orthodox, Southpaw, Switch
    
    # Personal
    date_of_birth = Column(Date)
    nationality = Column(String(100))
    team = Column(String(200))
    
    # Career Statistics (from UFC Stats)
    slpm = Column(Float)                    # Significant Strikes Landed per Minute
    sig_strike_acc = Column(Float)          # Significant Striking Accuracy (0.0-1.0)
    sapm = Column(Float)                    # Significant Strikes Absorbed per Minute
    sig_strike_def = Column(Float)          # Significant Strike Defence (0.0-1.0)
    td_avg = Column(Float)                  # Average Takedowns Landed per 15 minutes
    td_acc = Column(Float)                  # Takedown Accuracy (0.0-1.0)
    td_def = Column(Float)                  # Takedown Defense (0.0-1.0)
    sub_avg = Column(Float)                 # Average Submissions Attempted per 15 minutes
    
    # Additional physical
    weight_lbs = Column(Integer)            # Actual weight in pounds
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    fights_as_a = relationship("Fight", foreign_keys="Fight.fighter_a_id", back_populates="fighter_a")
    fights_as_b = relationship("Fight", foreign_keys="Fight.fighter_b_id", back_populates="fighter_b")
    wins = relationship("Fight", foreign_keys="Fight.winner_id", back_populates="winner")
    stats = relationship("FightStat", back_populates="fighter")
    
    @property
    def record(self):
        """Formatted record string"""
        return f"{self.record_wins}-{self.record_losses}-{self.record_draws}"
    
    @property
    def age(self):
        """Calculate age from DOB"""
        if not self.date_of_birth:
            return None
        today = datetime.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class Event(Base):
    """UFC Event"""
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True)
    ufc_id = Column(String(50), unique=True, index=True)
    
    name = Column(String(200), nullable=False)
    date = Column(Date, index=True)
    location = Column(String(200))
    venue = Column(String(200))
    url = Column(String(500))  # Event detail page URL
    
    # Event type
    is_ppv = Column(Boolean, default=False)
    is_fight_night = Column(Boolean, default=False)
    
    # Status: upcoming, completed, cancelled
    status = Column(String(20), default='upcoming', index=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    fights = relationship("Fight", back_populates="event", order_by="Fight.card_position")


class Fight(Base):
    """Individual fight"""
    __tablename__ = 'fights'
    
    id = Column(Integer, primary_key=True)
    ufc_id = Column(String(50), unique=True, index=True)
    
    # Event
    event_id = Column(Integer, ForeignKey('events.id'), index=True)
    
    # Fighters
    fighter_a_id = Column(Integer, ForeignKey('fighters.id'), index=True)
    fighter_b_id = Column(Integer, ForeignKey('fighters.id'), index=True)
    winner_id = Column(Integer, ForeignKey('fighters.id'), nullable=True, index=True)
    
    # Result
    method = Column(String(50))           # KO/TKO, Submission, Decision, etc.
    method_details = Column(String(100))  # e.g., "Punch", "Rear Naked Choke"
    end_round = Column(Integer)           # Which round it ended
    end_time = Column(String(10))         # e.g., "3:45"
    end_time_seconds = Column(Integer)    # For calculations
    
    # Context
    weight_class = Column(String(50), index=True)
    is_title_fight = Column(Boolean, default=False)
    is_main_event = Column(Boolean, default=False)
    card_position = Column(Integer)       # 1 = main event, 2 = co-main, etc.
    
    # For upcoming fights
    scheduled_rounds = Column(Integer, default=3)  # 5 for title fights
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("Event", back_populates="fights")
    fighter_a = relationship("Fighter", foreign_keys=[fighter_a_id], back_populates="fights_as_a")
    fighter_b = relationship("Fighter", foreign_keys=[fighter_b_id], back_populates="fights_as_b")
    winner = relationship("Fighter", foreign_keys=[winner_id], back_populates="wins")
    stats = relationship("FightStat", back_populates="fight")
    odds = relationship("Odds", back_populates="fight")
    
    @property
    def result(self):
        """Human-readable result"""
        if not self.winner_id:
            return "Draw/No Contest"
        winner = self.winner.name if self.winner else "Unknown"
        return f"{winner} by {self.method}"


class FightStat(Base):
    """Detailed statistics for a fighter in a specific fight"""
    __tablename__ = 'fight_stats'
    
    id = Column(Integer, primary_key=True)
    
    fight_id = Column(Integer, ForeignKey('fights.id'), index=True)
    fighter_id = Column(Integer, ForeignKey('fighters.id'), index=True)
    
    # Significant strikes
    sig_strikes_landed = Column(Integer, default=0)
    sig_strikes_attempted = Column(Integer, default=0)
    sig_strike_pct = Column(Float)
    
    # Head/body/leg breakdown
    sig_strikes_head_landed = Column(Integer, default=0)
    sig_strikes_head_attempted = Column(Integer, default=0)
    sig_strikes_body_landed = Column(Integer, default=0)
    sig_strikes_body_attempted = Column(Integer, default=0)
    sig_strikes_leg_landed = Column(Integer, default=0)
    sig_strikes_leg_attempted = Column(Integer, default=0)
    
    # Distance/clinch/ground
    sig_strikes_distance_landed = Column(Integer, default=0)
    sig_strikes_clinch_landed = Column(Integer, default=0)
    sig_strikes_ground_landed = Column(Integer, default=0)
    
    # Total strikes
    total_strikes_landed = Column(Integer, default=0)
    total_strikes_attempted = Column(Integer, default=0)
    
    # Takedowns
    takedowns_landed = Column(Integer, default=0)
    takedowns_attempted = Column(Integer, default=0)
    takedown_pct = Column(Float)
    
    # Submissions
    submissions_attempted = Column(Integer, default=0)
    
    # Grappling
    reversals = Column(Integer, default=0)
    control_time_seconds = Column(Integer, default=0)
    
    # Knockdowns
    knockdowns_scored = Column(Integer, default=0)
    
    # Defense (calculated from opponent stats)
    sig_strikes_absorbed = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    fight = relationship("Fight", back_populates="stats")
    fighter = relationship("Fighter", back_populates="stats")
    
    __table_args__ = (
        Index('idx_fight_fighter', 'fight_id', 'fighter_id', unique=True),
    )


class Odds(Base):
    """Betting odds for a fight"""
    __tablename__ = 'odds'
    
    id = Column(Integer, primary_key=True)
    
    fight_id = Column(Integer, ForeignKey('fights.id'), index=True)
    fighter_id = Column(Integer, ForeignKey('fighters.id'), index=True)
    
    # Source
    sportsbook = Column(String(50), index=True)  # DraftKings, Bet365, etc.
    
    # Odds formats
    american_odds = Column(Integer)      # -150, +200
    decimal_odds = Column(Float)         # 1.67, 3.0
    implied_probability = Column(Float)  # 0.60, 0.33
    
    # Line movement
    opening_odds = Column(Integer)
    closing_odds = Column(Integer)
    lowest_odds = Column(Integer)
    highest_odds = Column(Integer)
    
    # Timestamp
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    fight = relationship("Fight", back_populates="odds")
    
    __table_args__ = (
        Index('idx_fight_book_fighter', 'fight_id', 'sportsbook', 'fighter_id', unique=True),
    )


# Database utilities
def get_engine(db_url=None):
    """Create database engine"""
    if db_url is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'ufc.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db_url = f"sqlite:///{db_path}"
    return create_engine(db_url, echo=False)


def init_db(engine=None):
    """Initialize database tables"""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None):
    """Get database session"""
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    engine = init_db()
    print("✅ Database initialized")
    print(f"📁 Location: {engine.url}")
