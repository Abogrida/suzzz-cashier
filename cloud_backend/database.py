from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load secret from .env if it exists
load_dotenv()

# Use SQLite for simplicity in this demo, but easy to switch to Postgres
# DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/dbname")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cloud.db")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Models ---

class SyncOrder(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    local_id = Column(Integer, index=True) # ID from the cashier machine
    order_number = Column(Integer)
    total_amount = Column(Float)
    created_at = Column(String)
    status = Column(String)
    raw_data = Column(JSON) # Full JSON dump

class SyncInvoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    local_id = Column(Integer, index=True)
    invoice_number = Column(String)
    total_amount = Column(Float)
    created_at = Column(String)
    raw_data = Column(JSON)

class SyncShift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, index=True)
    local_id = Column(Integer, index=True)
    shift_name = Column(String)
    total_revenue = Column(Float)
    opened_at = Column(String)
    closed_at = Column(String)
    raw_data = Column(JSON)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
