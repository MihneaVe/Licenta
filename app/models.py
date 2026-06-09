"""SQLAlchemy models mirroring the existing Supabase schema.

These map onto the tables the former Django backend created (same table and
column names), so no data migration is needed — Alembic is baselined to this
schema. Only the tables the FastAPI app actually uses are modelled here:

    analytics_socialpost           (+ topics M2M, district FK)
    analytics_district
    analytics_topiccategory
    analytics_socialpost_topics    (association table)
    rag_postembedding              (pgvector embedding)
    rag_feedback

The dropped Django framework tables (auth_*, django_*, sessions, the duplicate
user/profile models, analytics_mood) are intentionally NOT modelled.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .db import Base

# --- association table: socialpost <-> topiccategory ------------------------
socialpost_topics = Table(
    "analytics_socialpost_topics",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("socialpost_id", BigInteger, ForeignKey("analytics_socialpost.id", ondelete="CASCADE")),
    Column("topiccategory_id", BigInteger, ForeignKey("analytics_topiccategory.id", ondelete="CASCADE")),
)


class District(Base):
    __tablename__ = "analytics_district"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    city = Column(String(100), default="București")
    kind = Column(String(10), default="sector")
    parent_id = Column(BigInteger, ForeignKey("analytics_district.id", ondelete="SET NULL"), nullable=True)
    boundary_geojson = Column(JSONB, nullable=True)
    centroid_lat = Column(Float, nullable=True)
    centroid_lng = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    def __repr__(self):
        return f"<District {self.name}>"


class TopicCategory(Base):
    __tablename__ = "analytics_topiccategory"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, default="")


class SocialPost(Base):
    __tablename__ = "analytics_socialpost"

    id = Column(BigInteger, primary_key=True)
    source = Column(String(20), nullable=False)
    source_id = Column(String(255), default="")
    content = Column(Text, nullable=False)
    author = Column(String(255), default="")
    url = Column(String(200), default="")

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_name = Column(String(255), default="")
    district_id = Column(BigInteger, ForeignKey("analytics_district.id", ondelete="SET NULL"), nullable=True)

    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(20), default="")
    topic_scores = Column(JSONB, nullable=True)

    score = Column(Integer, default=0)
    extra_data = Column(JSONB, nullable=True)
    language = Column(String(10), default="ro")
    ingestion_method = Column(String(20), default="scraper")

    original_date = Column(DateTime(timezone=True), nullable=True)
    scraped_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    district = relationship("District", lazy="joined")
    topics = relationship("TopicCategory", secondary=socialpost_topics, lazy="selectin")
    embedding_row = relationship("PostEmbedding", back_populates="post", uselist=False)

    def __repr__(self):
        return f"<SocialPost {self.id} [{self.source}]>"


class PostEmbedding(Base):
    __tablename__ = "rag_postembedding"

    id = Column(BigInteger, primary_key=True)
    post_id = Column(BigInteger, ForeignKey("analytics_socialpost.id", ondelete="CASCADE"), unique=True, nullable=False)
    embedding = Column(Vector(768), nullable=True)
    model_name = Column(String(100), default="nomic-embed-text")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("SocialPost", back_populates="embedding_row")


class RagFeedback(Base):
    __tablename__ = "rag_feedback"

    id = Column(BigInteger, primary_key=True)
    session_id = Column(String(64), default="")
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    retrieved_post_ids = Column(JSONB, default=list)
    rating = Column(String(10), nullable=False)  # 'up' | 'down'
    context_score = Column(Float, nullable=True)
    answer_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class DistrictScore(Base):
    __tablename__ = "analytics_districtscore"

    id = Column(BigInteger, primary_key=True)
    district_id = Column(BigInteger, ForeignKey("analytics_district.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    avg_sentiment = Column(Float, nullable=False)
    post_count = Column(Integer, default=0)
    issue_count = Column(Integer, default=0)
    overall_score = Column(Float, nullable=False)
    grade = Column(String(2), default="")
    topic_breakdown = Column(JSONB, nullable=True)
    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
