import os
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Text, Date, Boolean
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.types import UserDefinedType
from datetime import datetime

# Detect database engine type
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ksp_sentinel.db")
SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///./ksp_sentinel.db")
USE_POSTGRES = not (DATABASE_URL.startswith("sqlite") or SQLITE_URL.startswith("sqlite"))

# Define Geometry and Vector classes
Geometry = None
Vector = None

if USE_POSTGRES:
    try:
        from geoalchemy2 import Geometry
    except ImportError:
        pass

    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:
        pass

# Fallback types for SQLite or when libraries are missing
if Geometry is None:
    class Geometry(UserDefinedType):
        def __init__(self, geometry_type='GEOMETRY', srid=4326, *args, **kwargs):
            self.geometry_type = geometry_type
            self.srid = srid
        def get_col_spec(self, **kw):
            return "TEXT"

if Vector is None:
    class Vector(UserDefinedType):
        def __init__(self, dim, *args, **kwargs):
            self.dim = dim
        def get_col_spec(self, **kw):
            return "TEXT"

Base = declarative_base()

# Many-to-many link table for FIRs and Accused
fir_accused = Table(
    'fir_accused',
    Base.metadata,
    Column('fir_id', Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), primary_key=True),
    Column('accused_id', Integer, ForeignKey('accused.id', ondelete='CASCADE'), primary_key=True)
)

class District(Base):
    __tablename__ = 'districts'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    population = Column(Integer, default=100000)
    risk_score = Column(Integer, default=50)
    risk_factors = Column(Text, nullable=True)
    
    # Socio-economic indicators
    urbanization_rate = Column(Float, default=30.0)
    literacy_rate = Column(Float, default=75.0)
    unemployment_rate = Column(Float, default=5.0)
    poverty_rate = Column(Float, default=15.0)
    
    geom = Column(Geometry('MULTIPOLYGON', srid=4326), nullable=True)
    
    stations = relationship("PoliceStation", back_populates="district")
    predictions = relationship("CrimeForecast", back_populates="district")
    taluks = relationship("Taluk", back_populates="district")
    risk_score_ref = relationship("CrimeRiskScore", back_populates="district", uselist=False)

class Taluk(Base):
    __tablename__ = 'taluks'
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    name = Column(String(100), nullable=False)
    geom = Column(Geometry('MULTIPOLYGON', srid=4326), nullable=True)
    
    district = relationship("District", back_populates="taluks")

class PoliceStation(Base):
    __tablename__ = 'police_stations'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(Geometry('POINT', srid=4326), nullable=True)
    
    district = relationship("District", back_populates="stations")
    firs = relationship("FIR", back_populates="station")
    hotspots = relationship("CrimeHotspot", back_populates="station")
    officers = relationship("Officer", back_populates="station")

class CrimeCategory(Base):
    __tablename__ = 'crime_categories'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    major_head = Column(String(200), nullable=True)
    minor_head = Column(String(200), nullable=True)
    
    subcategories = relationship("CrimeSubcategory", back_populates="category")
    predictions = relationship("CrimeForecast", back_populates="category")

class CrimeSubcategory(Base):
    __tablename__ = 'crime_subcategories'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey('crime_categories.id', ondelete='CASCADE'))
    
    category = relationship("CrimeCategory", back_populates="subcategories")
    firs = relationship("FIR", back_populates="subcategory")

class FIR(Base):
    __tablename__ = 'fir_cases'
    id = Column(Integer, primary_key=True, index=True)
    fir_number = Column(String(50), unique=True, nullable=False)
    police_station_id = Column(Integer, ForeignKey('police_stations.id', ondelete='SET NULL'))
    subcategory_id = Column(Integer, ForeignKey('crime_subcategories.id', ondelete='SET NULL'))
    date_reported = Column(DateTime, default=datetime.utcnow)
    date_occurred = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default='REGISTERED') # REGISTERED, INVESTIGATING, CHARGE_SHEETED, CLOSED, TRIAL
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(Geometry('POINT', srid=4326), nullable=True)
    
    station = relationship("PoliceStation", back_populates="firs")
    subcategory = relationship("CrimeSubcategory", back_populates="firs")
    victims = relationship("Victim", back_populates="fir")
    accused_list = relationship("Accused", secondary=fir_accused, back_populates="firs")
    arrests = relationship("Arrest", back_populates="fir")
    convictions = relationship("Conviction", back_populates="fir")
    investigations = relationship("Investigation", back_populates="fir")
    chargesheets = relationship("ChargeSheet", back_populates="fir")
    embeddings = relationship("CrimeEmbedding", back_populates="fir", uselist=False)

class Victim(Base):
    __tablename__ = 'victims'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True) # SENIOR_CITIZEN, WOMAN, CHILD, GENERAL
    injured = Column(Integer, default=0)
    dead = Column(Integer, default=0)
    
    fir = relationship("FIR", back_populates="victims")

class Accused(Base):
    __tablename__ = 'accused'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    repeat_offender = Column(Boolean, default=False)
    history_sheet = Column(Boolean, default=False)
    gang = Column(String(200), nullable=True)
    prior_offenses_count = Column(Integer, default=0)
    status = Column(String(50), default='ACTIVE') # ACTIVE, ABSCONDING, ARRESTED, CONVICTED, INACTIVE
    
    firs = relationship("FIR", secondary=fir_accused, back_populates="accused_list")
    arrests = relationship("Arrest", back_populates="accused")
    convictions = relationship("Conviction", back_populates="accused")

class Arrest(Base):
    __tablename__ = 'arrests'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    accused_id = Column(Integer, ForeignKey('accused.id', ondelete='CASCADE'))
    arrest_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default='ARRESTED')
    officer = Column(String(100), nullable=True)
    court = Column(String(100), nullable=True)
    
    fir = relationship("FIR", back_populates="arrests")
    accused = relationship("Accused", back_populates="arrests")

class Conviction(Base):
    __tablename__ = 'convictions'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    accused_id = Column(Integer, ForeignKey('accused.id', ondelete='CASCADE'))
    conviction_date = Column(DateTime, nullable=True)
    sentence_months = Column(Integer, nullable=True)
    status = Column(String(50), default='CONVICTED')
    court = Column(String(100), nullable=True)
    sentence = Column(String(200), nullable=True)
    years = Column(Float, nullable=True)
    fine = Column(Float, nullable=True)
    
    fir = relationship("FIR", back_populates="convictions")
    accused = relationship("Accused", back_populates="convictions")

class Investigation(Base):
    __tablename__ = 'investigations'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    assigned_officer = Column(String(100), nullable=True)
    status = Column(String(50), default='ASSIGNED') # ASSIGNED, ONGOING, SUSPENDED, COMPLETED
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    fir = relationship("FIR", back_populates="investigations")

class ChargeSheet(Base):
    __tablename__ = 'chargesheets'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    filed_date = Column(DateTime, default=datetime.utcnow)
    sections = Column(String(200), nullable=True)
    status = Column(String(50), default='FILED')
    
    fir = relationship("FIR", back_populates="chargesheets")

class Officer(Base):
    __tablename__ = 'officers'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    badge_number = Column(String(50), unique=True, nullable=False)
    rank = Column(String(50), nullable=True)
    station_id = Column(Integer, ForeignKey('police_stations.id', ondelete='SET NULL'), nullable=True)
    status = Column(String(50), default='ACTIVE')
    
    station = relationship("PoliceStation", back_populates="officers")

class MonthlyCrimeReview(Base):
    __tablename__ = 'crime_review_monthly'
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

class YearlyCrimeReview(Base):
    __tablename__ = 'crime_review_yearly'
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    head_of_crime = Column(String(200), nullable=False)
    count = Column(Integer, nullable=False)
    increase_percentage = Column(Float, nullable=True)

class CrimeStatistic(Base):
    __tablename__ = 'crime_statistics'
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey('crime_categories.id', ondelete='CASCADE'))
    total_count = Column(Integer, nullable=False)
    rate_per_lakh = Column(Float, nullable=True)

class CrimeEmbedding(Base):
    __tablename__ = 'crime_embeddings'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), unique=True)
    embedding = Column(Vector(384), nullable=True)
    
    fir = relationship("FIR", back_populates="embeddings")

class CrimeCluster(Base):
    __tablename__ = 'crime_clusters'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    district_ids = Column(String(200), nullable=True)
    count = Column(Integer, default=0)

class CrimeForecast(Base):
    __tablename__ = 'crime_forecasts'
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey('crime_categories.id', ondelete='CASCADE'))
    predicted_count = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=True)
    
    district = relationship("District", back_populates="predictions")
    category = relationship("CrimeCategory", back_populates="predictions")

class CrimeRiskScore(Base):
    __tablename__ = 'crime_risk_scores'
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'), unique=True)
    score = Column(Integer, default=50)
    safety_index = Column(Float, default=50.0)
    population_density = Column(Float, default=100.0)
    
    district = relationship("District", back_populates="risk_score_ref")

class CrimeAlert(Base):
    __tablename__ = 'crime_alerts'
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(50), default='WARNING')
    created_at = Column(DateTime, default=datetime.utcnow)

class CrimeNetwork(Base):
    __tablename__ = 'crime_network'
    id = Column(Integer, primary_key=True, index=True)
    source_accused_id = Column(Integer, ForeignKey('accused.id', ondelete='CASCADE'))
    target_accused_id = Column(Integer, ForeignKey('accused.id', ondelete='CASCADE'))
    connection_strength = Column(Float, default=1.0)
    common_firs_count = Column(Integer, default=1)

class CrimeSimilarity(Base):
    __tablename__ = 'crime_similarity'
    id = Column(Integer, primary_key=True, index=True)
    fir_id_1 = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    fir_id_2 = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    similarity_score = Column(Float, nullable=False)

class PatrolRoute(Base):
    __tablename__ = 'patrol_routes'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    geom = Column(Geometry('LINESTRING', srid=4326), nullable=True)
    assigned_officer_id = Column(Integer, ForeignKey('officers.id', ondelete='SET NULL'), nullable=True)

class CrimeHotspot(Base):
    __tablename__ = 'crime_hotspots'
    id = Column(Integer, primary_key=True, index=True)
    police_station_id = Column(Integer, ForeignKey('police_stations.id', ondelete='CASCADE'))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    intensity = Column(Float, nullable=False)
    prediction_date = Column(Date, nullable=False)
    
    station = relationship("PoliceStation", back_populates="hotspots")

class MonthlyReviewCategoryMap(Base):
    __tablename__ = 'monthly_review_category_map'
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey('crime_review_monthly.id', ondelete='CASCADE'))
    category_id = Column(Integer, ForeignKey('crime_categories.id', ondelete='SET NULL'), nullable=True)
    subcategory_id = Column(Integer, ForeignKey('crime_subcategories.id', ondelete='SET NULL'), nullable=True)
    confidence = Column(Float, nullable=True)
    method = Column(String(50), nullable=True)
