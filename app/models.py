from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base

class Lead(Base):
    __tablename__ = "leads"

    id                      = Column(Integer, primary_key=True, index=True)
    linkedin_url            = Column(String, unique=True, nullable=False)
    contact_email           = Column(String, unique=True, nullable=True)
    company_website         = Column(String, nullable=True)
    company_name            = Column(String, nullable=True)
    industry                = Column(String, nullable=True)
    company_size            = Column(String, nullable=True)
    location                = Column(String, nullable=True)
    established_year        = Column(String, nullable=True)
    headquarters            = Column(String, nullable=True)
    branches                = Column(String, nullable=True)
    company_description     = Column(Text, nullable=True)
    description_vector      = Column(Vector(384), nullable=True)
    contact_name            = Column(String, nullable=True)
    contact_title           = Column(String, nullable=True)
    contact_linkedin        = Column(String, nullable=True)

    # Agent 2 fills these
    intel_brief             = Column(Text, nullable=True)
    pain_points             = Column(Text, nullable=True)
    recent_activity         = Column(Text, nullable=True)
    hook_used               = Column(Text, nullable=True)
    linkedin_connected      = Column(Boolean, default=False)
    linkedin_requested_at   = Column(DateTime, nullable=True)

    # Agent 3 fills these
    follow_up_count         = Column(Integer, default=0)
    last_contacted_at       = Column(DateTime, nullable=True)
    next_followup_at        = Column(DateTime, nullable=True)

    status                  = Column(String, default='NEW')
    status_updated_at       = Column(DateTime, default=func.now())
    scraped_at              = Column(DateTime, default=func.now())
    updated_at              = Column(DateTime, default=func.now(), onupdate=func.now())
