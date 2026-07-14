from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Text, Date
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

# Many-to-many link table for FIRs and Accused
fir_accused = Table(
    'fir_accused',
    Base.metadata,
    Column('fir_id', Integer, ForeignKey('firs.id', ondelete='CASCADE'), primary_key=True),
    Column('accused_id', Integer, ForeignKey('accused.id', ondelete='CASCADE'), primary_key=True)
)

class District(Base):
    __tablename__ = 'districts'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    population = Column(Integer, default=100000)
    risk_score = Column(Integer, default=50)
    risk_factors = Column(Text, nullable=True)
    
    stations = relationship("PoliceStation", back_populates="district")
    predictions = relationship("CrimePrediction", back_populates="district")

class PoliceStation(Base):
    __tablename__ = 'police_stations'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    district = relationship("District", back_populates="stations")
    firs = relationship("FIR", back_populates="station")
    hotspots = relationship("CrimeHotspot", back_populates="station")

class CrimeCategory(Base):
    __tablename__ = 'crime_categories'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    
    subcategories = relationship("CrimeSubcategory", back_populates="category")
    predictions = relationship("CrimePrediction", back_populates="category")

class CrimeSubcategory(Base):
    __tablename__ = 'crime_subcategories'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey('crime_categories.id', ondelete='CASCADE'))
    
    category = relationship("CrimeCategory", back_populates="subcategories")
    firs = relationship("FIR", back_populates="subcategory")

class FIR(Base):
    __tablename__ = 'firs'
    id = Column(Integer, primary_key=True, index=True)
    fir_number = Column(String(50), unique=True, nullable=False)
    police_station_id = Column(Integer, ForeignKey('police_stations.id'))
    subcategory_id = Column(Integer, ForeignKey('crime_subcategories.id'))
    date_reported = Column(DateTime, default=datetime.utcnow)
    date_occurred = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default='REGISTERED') # REGISTERED, INVESTIGATING, CHARGE_SHEETED, CLOSED, TRIAL
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    station = relationship("PoliceStation", back_populates="firs")
    subcategory = relationship("CrimeSubcategory", back_populates="firs")
    victims = relationship("Victim", back_populates="fir")
    accused_list = relationship("Accused", secondary=fir_accused, back_populates="firs")
    arrests = relationship("Arrest", back_populates="fir")
    convictions = relationship("Conviction", back_populates="fir")
    investigations = relationship("Investigation", back_populates="fir")

class Victim(Base):
    __tablename__ = 'victims'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('firs.id', ondelete='CASCADE'))
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True) # SENIOR_CITIZEN, WOMAN, CHILD, GENERAL
    
    fir = relationship("FIR", back_populates="victims")

class Accused(Base):
    __tablename__ = 'accused'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    prior_offenses_count = Column(Integer, default=0)
    status = Column(String(50), default='ACTIVE') # ACTIVE, ABSCONDING, ARRESTED, CONVICTED, INACTIVE
    
    firs = relationship("FIR", secondary=fir_accused, back_populates="accused_list")
    arrests = relationship("Arrest", back_populates="accused")
    convictions = relationship("Conviction", back_populates="accused")

class Arrest(Base):
    __tablename__ = 'arrests'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('firs.id', ondelete='CASCADE'))
    accused_id = Column(Integer, ForeignKey('accused.id', ondelete='CASCADE'))
    arrest_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default='ARRESTED')
    
    fir = relationship("FIR", back_populates="arrests")
    accused = relationship("Accused", back_populates="arrests")

class Conviction(Base):
    __tablename__ = 'convictions'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('firs.id', ondelete='CASCADE'))
    accused_id = Column(Integer, ForeignKey('accused.id', ondelete='CASCADE'))
    conviction_date = Column(DateTime, nullable=True)
    sentence_months = Column(Integer, nullable=True)
    status = Column(String(50), default='CONVICTED')
    
    fir = relationship("FIR", back_populates="convictions")
    accused = relationship("Accused", back_populates="convictions")

class Investigation(Base):
    __tablename__ = 'investigations'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('firs.id', ondelete='CASCADE'))
    assigned_officer = Column(String(100), nullable=True)
    status = Column(String(50), default='ASSIGNED') # ASSIGNED, ONGOING, SUSPENDED, COMPLETED
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    fir = relationship("FIR", back_populates="investigations")

class CrimePrediction(Base):
    __tablename__ = 'crime_predictions'
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey('crime_categories.id', ondelete='CASCADE'))
    predicted_count = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=True)
    
    district = relationship("District", back_populates="predictions")
    category = relationship("CrimeCategory", back_populates="predictions")

class CrimeHotspot(Base):
    __tablename__ = 'crime_hotspots'
    id = Column(Integer, primary_key=True, index=True)
    police_station_id = Column(Integer, ForeignKey('police_stations.id', ondelete='CASCADE'))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    intensity = Column(Float, nullable=False)
    prediction_date = Column(Date, nullable=False)
    
    station = relationship("PoliceStation", back_populates="hotspots")


class MonthlyCrimeReview(Base):
    __tablename__ = 'monthly_crime_reviews'
    id = Column(Integer, primary_key=True, index=True)
    source_file = Column(String(200), nullable=True)
    sl_no = Column(Integer, nullable=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    heads_of_crime = Column(String(200), nullable=True)
    major_head = Column(String(300), nullable=True)
    minor_head = Column(String(300), nullable=True)
    upto_end_of_month = Column(Integer, nullable=True)
    corresponding_month_prev_year = Column(Integer, nullable=True)
    previous_month = Column(Integer, nullable=True)
    current_month = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MonthlyReviewCategoryMap(Base):
    __tablename__ = 'monthly_review_category_map'
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey('monthly_crime_reviews.id', ondelete='CASCADE'))
    category_id = Column(Integer, ForeignKey('crime_categories.id', ondelete='SET NULL'), nullable=True)
    subcategory_id = Column(Integer, ForeignKey('crime_subcategories.id', ondelete='SET NULL'), nullable=True)

    # mapping metadata
    confidence = Column(Float, nullable=True)
    method = Column(String(50), nullable=True)  # e.g. substring, token_overlap, fuzzy

    # relationships are optional for read convenience
    # review = relationship('MonthlyCrimeReview')
    # category = relationship('CrimeCategory')
    # subcategory = relationship('CrimeSubcategory')
