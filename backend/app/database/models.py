from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Text, Date, Boolean
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.types import UserDefinedType
from datetime import datetime

from app.logging import logger
# The dialect comes from the URL session.py actually opened. Re-deriving it here from
# os.getenv was a second, subtly different expression that was always False, so on a
# real PostGIS/pgvector database every geom and embedding column silently became TEXT.
# (session.py imports nothing from this module, so the direction is safe.)
from app.database.session import USE_POSTGRES

# Define Geometry and Vector classes
Geometry = None
Vector = None

if USE_POSTGRES:
    try:
        from geoalchemy2 import Geometry
    except ImportError:
        # Degrading to TEXT against PostGIS is a data-shape change, not a detail:
        # spatial queries will not work and nobody would guess why from the schema.
        logger.warning(
            "PostgreSQL is configured but geoalchemy2 is not installed -- geometry columns "
            "fall back to TEXT and spatial queries will not work. Install geoalchemy2."
        )

    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:
        logger.warning(
            "PostgreSQL is configured but pgvector is not installed -- embedding columns "
            "fall back to TEXT and vector similarity search will not work. Install pgvector."
        )

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

    # MFA (backend/app/core/mfa.py). totp_secret is Fernet-encrypted at rest -- never
    # store or return the plaintext secret outside the one-time enrollment response.
    totp_secret = Column(Text, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    # Anti-replay: the TOTP time-step of the last code this user successfully
    # authenticated with. A 30-second-valid code could otherwise be reused for any
    # request within that window (e.g. two verify-otp calls, or a shoulder-surfed
    # code re-submitted moments later) -- rejecting any step <= this one closes that.
    last_totp_step = Column(Integer, nullable=True)

    # Data-scoping for RBAC (backend/app/core/security.py::scope_to_user_district).
    # Nullable: most accounts (legacy demo logins, newly created users) have no
    # district/station assigned yet, which scope_to_user_district treats as unscoped
    # rather than "show nothing" -- see that module for why.
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='SET NULL'), nullable=True)
    station_id = Column(Integer, ForeignKey('police_stations.id', ondelete='SET NULL'), nullable=True)

    # Break-glass override for IPC 228A-style sensitive cases (backend/app/core/masking.py).
    # Independent of role -- even a Superintendent doesn't see a sensitive-flagged
    # person's identity unless this is explicitly granted by an Admin.
    can_view_sensitive = Column(Boolean, default=False)

class RefreshToken(Base):
    """Refresh tokens are stored hashed (never the raw token) so a DB read alone can't
    be replayed as a session, and can be revoked individually (logout) or in bulk
    (password reset, account deactivation) without needing to rotate the JWT signing
    key for everyone else."""
    __tablename__ = 'refresh_tokens'
    id = Column(Integer, primary_key=True, index=True)
    # Nullable: the legacy demo-password login path (unregistered usernames) issues a
    # real refresh token too but has no backing User row to attach it to.
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    replaced_by_id = Column(Integer, nullable=True)

class AuditLog(Base):
    """Append-only security/action log. Login attempts (success and failure), RBAC
    denials, AI queries, evidence access, and user-management changes all write here.
    Deliberately stores only resource identifiers and outcomes, never PII values --
    the log itself must not become a second place PII can leak from."""
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    username = Column(String(100), nullable=True)  # retained even if the user row is later deleted
    action = Column(String(100), nullable=False, index=True)
    resource = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    success = Column(Boolean, default=True)
    detail = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

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


# ─────────────────────────────────────────────────────────────────────────────
# Investigation Intelligence additions (NEW_FEATURES.md)
# Additive only: new tables, no changes to any existing model above.
# ─────────────────────────────────────────────────────────────────────────────

class MOPatternMatch(Base):
    """A flagged modus-operandi correspondence between two FIRs in DIFFERENT districts.

    Cross-district is the whole point: two burglaries in one station's beat sharing an
    MO is routine, whereas the same signature surfacing in Mangaluru and Bengaluru is
    the thing an investigator would otherwise never see.

    Pairs are stored canonically with fir_id_1 < fir_id_2 so a pair is recorded once,
    not twice in both orders.
    """
    __tablename__ = 'mo_pattern_matches'
    id = Column(Integer, primary_key=True, index=True)
    fir_id_1 = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), index=True)
    fir_id_2 = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), index=True)
    # entry_method | weapon | time_pattern | combined
    match_type = Column(String(30), nullable=False)
    similarity_score = Column(Float, nullable=False)
    district_id_1 = Column(Integer, ForeignKey('districts.id', ondelete='SET NULL'), nullable=True, index=True)
    district_id_2 = Column(Integer, ForeignKey('districts.id', ondelete='SET NULL'), nullable=True, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)


class SectionSuggestion(Base):
    """A retrieved IPC/BNS section candidate for a complaint (NEW_FEATURES.md, Feature 2).

    fir_id is NULLABLE on purpose: the suggestion endpoint is designed to be callable
    while a complaint is still being drafted, before any FIR row exists. Rows are only
    written when the caller ties the suggestion to a real case, so exploratory lookups
    during drafting don't accumulate noise in the table.

    Storing `reference_description` alongside the score records *why* the section was
    proposed at the time -- the reference file is editable, so a later edit must not
    silently rewrite the justification attached to a past case.
    """
    __tablename__ = 'section_suggestions'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), nullable=True, index=True)
    suggested_section = Column(String(60), nullable=False)
    confidence = Column(Float, nullable=False)
    reference_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class EvidenceItem(Base):
    """A digital evidence item attached to a case (NEW_FEATURES.md, Feature 4).

    `file_reference` is an OPAQUE pointer -- this service never holds or retrieves the
    bytes. `content_hash` is therefore a baseline *reported* by whichever system does
    hold them, not something computed here. On a reported mismatch the baseline is
    deliberately NOT overwritten: the item is flagged instead, so the original
    fingerprint stays on record for the court rather than being silently replaced.
    """
    __tablename__ = 'evidence_items'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), index=True, nullable=False)
    item_type = Column(String(50), nullable=False)   # photo, video, audio, document, device_image, cdr, other
    file_reference = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    added_by = Column(String(100), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, index=True)
    current_custodian = Column(String(100), nullable=False)
    # --- integrity state (required by the spec's flagging behaviour) ---
    content_hash = Column(String(64), nullable=True)          # SHA-256 baseline, as reported
    integrity_flagged = Column(Boolean, default=False, index=True)
    integrity_flagged_at = Column(DateTime, nullable=True)

    access_logs = relationship("EvidenceAccessLog", back_populates="evidence",
                               order_by="EvidenceAccessLog.timestamp")


class EvidenceAccessLog(Base):
    """Append-only chain-of-custody trail for one evidence item.

    Written exclusively through app.services.evidence.log_evidence_action() so the
    logging rule lives in one place and no route can touch an item without leaving a
    trace. Rows are never updated or deleted.
    """
    __tablename__ = 'evidence_access_log'
    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey('evidence_items.id', ondelete='CASCADE'), index=True, nullable=False)
    accessed_by = Column(String(100), nullable=False)
    action = Column(String(30), nullable=False)      # added, viewed, modified, transferred, exported
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    hash_before = Column(String(64), nullable=True)  # NULL on 'added' (no prior state)
    hash_after = Column(String(64), nullable=True)   # NULL when no hash was reported (view-only)
    # Records whether an integrity check actually happened, so a row can never imply
    # verification that no bytes were available to perform.
    verification = Column(String(30), nullable=True)  # verified | integrity_mismatch | not_verified | baseline_recorded
    # Who held the item before and after this row's action. Structured columns, not
    # prose: the from/to pair used to live only inside `detail`, and the caller's
    # optional free-text note REPLACED it -- so any transfer that supplied a note
    # erased the participants from the trail, and "who held this on date X" (the one
    # question a custody log exists to answer) became unanswerable.
    custodian_before = Column(String(100), nullable=True)
    custodian_after = Column(String(100), nullable=True)
    detail = Column(String(300), nullable=True)

    evidence = relationship("EvidenceItem", back_populates="access_logs")


class CaseNudge(Base):
    """A supervisor-facing prompt that a case needs attention (NEW_FEATURES.md, Feature 3).

    Generated by a daily scan, never by hand. `due_date` is what the nudge is counting
    down to -- the staleness threshold date, the court date, or the derived chargesheet
    deadline -- so a single column orders every nudge type by urgency.

    One open nudge per (fir_id, nudge_type): the scan re-runs daily and must prompt, not
    nag. A resolved nudge can be superseded by a new one if the condition recurs.
    """
    __tablename__ = 'case_nudges'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), index=True, nullable=False)
    # staleness | court_date | chargesheet_deadline
    nudge_type = Column(String(30), nullable=False, index=True)
    due_date = Column(DateTime, nullable=True, index=True)
    # pending | acknowledged | resolved
    status = Column(String(20), default='pending', index=True)
    assigned_supervisor = Column(String(100), nullable=True, index=True)
    # Why the scan raised it, recorded at creation so a later data change doesn't
    # rewrite the justification attached to an open nudge.
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_note = Column(String(300), nullable=True)

    fir = relationship("FIR")


class OfficerIncidentHistory(Base):
    """A past incident where officers met violence or resistance at a location
    (NEW_FEATURES.md, Feature 2).

    Kept separate from `fir_cases` because it answers a different question: not "what
    crime happened here" but "what happened to officers who came here". The two are
    linked (`fir_id`) where a case exists, but an incident can also be recorded without
    one -- resistance during a patrol stop never becomes an FIR.

    Coordinates are denormalised onto the row rather than reached through `location_id`
    so a radius query stays a single indexed scan; `location_id` is kept for provenance.
    """
    __tablename__ = 'officer_incident_history'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='SET NULL'), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='SET NULL'), nullable=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    # assault_on_officer | resistance | weapon_involved
    incident_type = Column(String(40), nullable=False, index=True)
    severity = Column(Integer, default=3)          # 1 (minor) .. 5 (severe)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    description = Column(Text, nullable=True)
    officers_injured = Column(Integer, default=0)


class OfficerShift(Base):
    """An officer's duty roster entry (NEW_FEATURES.md, Feature 1).

    Availability for patrol assignment is read from here rather than from
    `officers.status`, which records employment state (ACTIVE/SUSPENDED), not whether
    someone is on shift right now.
    """
    __tablename__ = 'officer_shifts'
    id = Column(Integer, primary_key=True, index=True)
    officer_id = Column(Integer, ForeignKey('officers.id', ondelete='CASCADE'), index=True, nullable=False)
    station_id = Column(Integer, ForeignKey('police_stations.id', ondelete='SET NULL'), nullable=True, index=True)
    shift_start = Column(DateTime, nullable=False, index=True)
    shift_end = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default='on_duty', index=True)   # on_duty | off_duty | on_leave

    officer = relationship("Officer")


class PatrolAssignment(Base):
    """One officer directed to one hotspot for one shift.

    The hotspot's coordinates and intensity are copied onto the row rather than only
    referenced by `hotspot_id`: `crime_hotspots` is regenerated by the prediction job, so
    a past assignment that only pointed at a row id would lose its meaning (or point at a
    different place) the next time hotspots were recomputed. A duty record has to stay
    readable after the inputs move on.
    """
    __tablename__ = 'patrol_assignments'
    id = Column(Integer, primary_key=True, index=True)
    officer_id = Column(Integer, ForeignKey('officers.id', ondelete='CASCADE'), index=True, nullable=False)
    shift_id = Column(Integer, ForeignKey('officer_shifts.id', ondelete='SET NULL'), nullable=True, index=True)
    hotspot_id = Column(Integer, ForeignKey('crime_hotspots.id', ondelete='SET NULL'), nullable=True)
    station_id = Column(Integer, ForeignKey('police_stations.id', ondelete='SET NULL'), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey('districts.id', ondelete='SET NULL'), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    intensity = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True)
    priority_rank = Column(Integer, nullable=False)      # 1 = highest-intensity hotspot
    assigned_at = Column(DateTime, default=datetime.utcnow, index=True)

    officer = relationship("Officer")
    shift = relationship("OfficerShift")


class FIRComplainantContact(Base):
    """A complainant's phone, stored ONLY as a keyed hash (NEW_FEATURES.md, Feature 5).

    The public FIR-status endpoint verifies a caller by phone number, and nothing in the
    original schema held one. Rather than adding a plaintext phone column -- which would
    make this table a standing liability the moment the database leaked -- only an
    HMAC-SHA256 of the normalised number is kept, keyed with the server SECRET_KEY.

    A bare SHA-256 would not be enough: an Indian mobile is effectively 10 digits, so the
    whole keyspace can be hashed in seconds. The HMAC key is what makes the stored digest
    useless to anyone who has the database but not the key.

    Consequence, by design: the number cannot be read back out. This table can verify a
    number someone already knows; it can never be used to look one up or message someone
    who has not supplied it.
    """
    __tablename__ = 'fir_complainant_contacts'
    id = Column(Integer, primary_key=True, index=True)
    fir_id = Column(Integer, ForeignKey('fir_cases.id', ondelete='CASCADE'), index=True, nullable=False)
    phone_hmac = Column(String(64), nullable=False, index=True)
    # Channel the complainant agreed to be contacted on, if any.
    preferred_channel = Column(String(20), nullable=True)   # whatsapp | sms
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    fir = relationship("FIR")
