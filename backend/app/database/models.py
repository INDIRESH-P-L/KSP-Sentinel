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
    stations = relationship("PoliceStation", back_populates="taluk")

class PoliceStation(Base):
    __tablename__ = 'police_stations'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='CASCADE'))
    taluk_id = Column(Integer, ForeignKey('taluks.id', ondelete='SET NULL'), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(Geometry('POINT', srid=4326), nullable=True)

    district = relationship("District", back_populates="stations")
    taluk = relationship("Taluk", back_populates="stations")
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
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='SET NULL'), nullable=True)
    date_reported = Column(DateTime, default=datetime.utcnow)
    date_occurred = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default='REGISTERED') # REGISTERED, INVESTIGATING, CHARGE_SHEETED, CLOSED, TRIAL
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(Geometry('POINT', srid=4326), nullable=True)

    station = relationship("PoliceStation", back_populates="firs")
    subcategory = relationship("CrimeSubcategory", back_populates="firs")
    location = relationship("Location", back_populates="incidents")
    victims = relationship("Victim", back_populates="fir")
    accused_list = relationship("Accused", secondary=fir_accused, back_populates="firs")
    arrests = relationship("Arrest", back_populates="fir")
    convictions = relationship("Conviction", back_populates="fir")
    investigations = relationship("Investigation", back_populates="fir")
    chargesheets = relationship("ChargeSheet", back_populates="fir")
    embeddings = relationship("CrimeEmbedding", back_populates="fir", uselist=False)
    person_links = relationship("PersonIncidentLink", back_populates="fir")
    modus_operandi = relationship("ModusOperandi", back_populates="fir", uselist=False)
    vehicle_links = relationship("VehicleIncidentLink", back_populates="fir")
    cluster_memberships = relationship("CaseClusterMember", back_populates="fir")

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

class User(Base):
    """Console login accounts (username/password/role), managed via the admin panel.

    Distinct from `Officer` above, which is crime-data personnel referenced by FIRs
    and patrol routes -- not something you log in as. This table is the actual
    authentication/authorization store for KSP Sentinel access."""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default='Investigator')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

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

    members = relationship("CaseClusterMember", backref="cluster")

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


# --- Intelligence layer: unified Person/Location/MO/Vehicle model ---
# A reusable entity graph sitting alongside the legacy Accused/Victim tables so the
# *same* person or location across incidents is one record, not a re-typed duplicate,
# and MO is queryable structured data rather than free text buried in `description`.

class Person(Base):
    __tablename__ = 'persons'
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    id_reference = Column(String(50), nullable=True)  # masked reference only, never a raw national ID
    photo_reference = Column(String(300), nullable=True)  # Stratus/object-storage key, not the binary itself
    # Legacy source pointers so a Person can be traced back to the record it was backfilled from
    source_accused_id = Column(Integer, ForeignKey('accused.id', ondelete='SET NULL'), nullable=True)
    source_victim_id = Column(Integer, ForeignKey('victims.id', ondelete='SET NULL'), nullable=True)
    # Section 228A IPC / BNS equivalent: suppress identity in any non-authorized view or export
    sensitive = Column(Boolean, default=False)

    incident_links = relationship("PersonIncidentLink", back_populates="person")
    vehicles = relationship("Vehicle", back_populates="owner")


class Location(Base):
    __tablename__ = 'locations'
    id = Column(Integer, primary_key=True, index=True)
    address_text = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_type = Column(String(30), default='crime_scene')  # crime_scene, residence, hangout
    geom = Column(Geometry('POINT', srid=4326), nullable=True)

    incidents = relationship("FIR", back_populates="location")


class PersonIncidentLink(Base):
    """Join table that doubles as the network-graph edge list: Person <-> FIR with a typed role."""
    __tablename__ = 'person_incident_links'
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey('persons.id', ondelete='CASCADE'))
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    role = Column(String(30), nullable=False)  # accused, victim, witness, complainant
    relationship_notes = Column(Text, nullable=True)

    person = relationship("Person", back_populates="incident_links")
    fir = relationship("FIR", back_populates="person_links")


class ModusOperandi(Base):
    """Structured MO tags per incident so pattern-matching doesn't require reading free text."""
    __tablename__ = 'modus_operandi'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), unique=True)
    entry_method = Column(String(60), nullable=True)  # forced_entry, day_entry, night_entry, online, none
    weapon_used = Column(String(60), nullable=True)
    time_of_day_pattern = Column(String(20), nullable=True)  # morning, afternoon, evening, night
    target_type = Column(String(60), nullable=True)  # residence, commercial, individual, vehicle, digital

    fir = relationship("FIR", back_populates="modus_operandi")


class Vehicle(Base):
    __tablename__ = 'vehicles'
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(30), nullable=True)
    vehicle_type = Column(String(50), nullable=True)  # two_wheeler, four_wheeler, commercial
    color = Column(String(30), nullable=True)
    owner_person_id = Column(Integer, ForeignKey('persons.id', ondelete='SET NULL'), nullable=True)

    owner = relationship("Person", back_populates="vehicles")
    incident_links = relationship("VehicleIncidentLink", back_populates="vehicle")


class VehicleIncidentLink(Base):
    __tablename__ = 'vehicle_incident_links'
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id', ondelete='CASCADE'))
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))
    role = Column(String(30), nullable=True)  # used_by_accused, stolen, getaway

    vehicle = relationship("Vehicle", back_populates="incident_links")
    fir = relationship("FIR", back_populates="vehicle_links")


class CaseClusterMember(Base):
    """Real membership rows for CrimeCluster, populated by the ST-DBSCAN/clustering job
    (CrimeCluster previously only stored a rough district_ids string, not actual case membership)."""
    __tablename__ = 'case_cluster_members'
    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey('crime_clusters.id', ondelete='CASCADE'))
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'))

    fir = relationship("FIR", back_populates="cluster_memberships")
