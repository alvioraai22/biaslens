```python
"""
SQLAlchemy models for BiasLens application.

This module defines the database schema for job postings, bias analyses,
screening patterns, and generated reports.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class BiasCategory(str, enum.Enum):
    """Enumeration of bias categories detected by the system."""
    GENDER = "gender"
    AGE = "age"
    RACE_ETHNICITY = "race_ethnicity"
    EDUCATIONAL = "educational"
    SOCIOECONOMIC = "socioeconomic"
    DISABILITY = "disability"
    CULTURAL = "cultural"
    LANGUAGE = "language"


class SeverityLevel(str, enum.Enum):
    """Severity levels for detected bias."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalysisStatus(str, enum.Enum):
    """Status of analysis jobs."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Organization(Base):
    """Organization/company using BiasLens."""
    
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)  # e.g., "50-200", "200-500"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Configuration settings stored as JSON
    settings = Column(JSON, default={})
    
    # Relationships
    users = relationship("User", back_populates="organization")
    job_postings = relationship("JobPosting", back_populates="organization")
    screening_patterns = relationship("ScreeningPattern", back_populates="organization")


class User(Base):
    """User accounts within organizations."""
    
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="user")  # admin, manager, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    job_postings = relationship("JobPosting", back_populates="created_by_user")


class JobPosting(Base):
    """Job posting submissions for bias analysis."""
    
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Job details
    title = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    
    # Metadata
    location = Column(String(255), nullable=True)
    employment_type = Column(String(50), nullable=True)  # full-time, part-time, contract
    salary_range_min = Column(Float, nullable=True)
    salary_range_max = Column(Float, nullable=True)
    
    # Status and tracking
    status = Column(String(50), default="draft")  # draft, published, archived
    external_id = Column(String(255), nullable=True, index=True)  # ID from ATS
    posted_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Raw data storage for additional fields
    metadata = Column(JSON, default={})
    
    # Relationships
    organization = relationship("Organization", back_populates="job_postings")
    created_by_user = relationship("User", back_populates="job_postings")
    analyses = relationship("BiasAnalysis", back_populates="job_posting", cascade="all, delete-orphan")


class BiasAnalysis(Base):
    """Bias analysis results for a job posting."""
    
    __tablename__ = "bias_analyses"

    id = Column(Integer, primary_key=True, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False)
    
    # Analysis metadata
    analysis_version = Column(String(20), default="1.0")  # Track model versions
    status = Column(SQLEnum(AnalysisStatus), default=AnalysisStatus.PENDING)
    
    # Overall scores (0-100 scale, higher = more bias detected)
    overall_bias_score = Column(Float, nullable=True)
    gender_bias_score = Column(Float, nullable=True)
    age_bias_score = Column(Float, nullable=True)
    educational_bias_score = Column(Float, nullable=True)
    cultural_bias_score = Column(Float, nullable=True)
    
    # Sentiment scores
    sentiment_score = Column(Float, nullable=True)  # -1 to 1
    inclusivity_score = Column(Float, nullable=True)  # 0 to 100
    
    # Language metrics
    readability_score = Column(Float, nullable=True)  # Flesch reading ease
    word_count = Column(Integer, nullable=True)
    
    # Detailed findings stored as JSON
    # Structure: {category: {severity, examples: [{text, context, suggestion}]}}
    findings = Column(JSON, default={})
    
    # Recommendations for improvement
    recommendations = Column(JSON, default=[])
    
    # NLP processing results
    key_phrases = Column(JSON, default=[])
    flagged_terms = Column(JSON, default=[])
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Relationships
    job_posting = relationship("JobPosting", back_populates="analyses")
    detected_biases = relationship("DetectedBias", back_populates="analysis", cascade="all, delete-orphan")


class DetectedBias(Base):
    """Individual bias instances detected in analysis."""
    
    __tablename__ = "detected_biases"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("bias_analyses.id"), nullable=False)
    
    # Bias details
    category = Column(SQLEnum(BiasCategory), nullable=False, index=True)
    severity = Column(SQLEnum(SeverityLevel), nullable=False)
    
    # Text and context
    flagged_text = Column(Text, nullable=False)
    context = Column(Text, nullable=True)  # Surrounding text
    location = Column(String(50), nullable=True)  # title, description, requirements, etc.
    
    # Position in text
    start_position = Column(Integer, nullable=True)
    end_position = Column(Integer, nullable=True)
    
    # Explanation and suggestion
    explanation = Column(Text, nullable=False)
    suggested_alternative = Column(Text, nullable=True)
    
    # Confidence score (0-1)
    confidence = Column(Float, nullable=True)
    
    # Additional metadata
    metadata = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analysis = relationship("BiasAnalysis", back_populates="detected_biases")


class ScreeningPattern(Base):
    """Candidate screening patterns for statistical bias analysis."""
    
    __tablename__ = "screening_patterns"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id"), nullable=True)
    
    # Time period for pattern analysis
    analysis_start_date = Column(DateTime(timezone=True), nullable=False)
    analysis_end_date = Column(DateTime(timezone=True), nullable=False)
    
    # Aggregate statistics (stored as JSON for flexibility)
    # Structure: {demographic_category: {applied, screened, interviewed, hired}}
    demographic_stats = Column(JSON, nullable=False)
    
    # Statistical measures
    # Adverse impact ratios, chi-square tests, etc.
    statistical_tests = Column(JSON, default={})
    
    # Screening stage metrics
    application_stage_stats = Column(JSON, default={})
    interview_stage_stats = Column(JSON, default={})
    offer_stage_stats = Column(JSON, default={})
    
    # Sample size and data quality
    total_candidates = Column(Integer, nullable=False)
    data_completeness_score = Column(Float, nullable=True)  # 0-1
    
    # Flagged disparities
    flagged_disparities = Column(JSON, default=[])
    
    # Notes and comments
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="screening_patterns")
    job_posting = relationship("JobPosting")


class BiasReport(Base):
    """Generated reports combining multiple analyses."""
    
    __tablename__ = "bias_reports"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Report details
    title = Column(String(255), nullable=False)
    report_type = Column(String(50), nullable=False)  # job_posting, screening, comprehensive
    description = Column(Text, nullable=True)
    
    # Date range for report
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Related entities (as JSON array of IDs)
    job_posting_ids = Column(JSON, default=[])
    analysis_ids = Column(JSON, default=[])
    screening_pattern_ids = Column(JSON, default=[])
    
    # Report content and metrics
    executive_summary = Column(Text, nullable=True)
    key_findings = Column(JSON, default=[])
    metrics = Column(JSON, default={})
    charts_data = Column(JSON, default={})  # Data for dashboard visualizations
    
    # Recommendations
    recommendations = Column(JSON