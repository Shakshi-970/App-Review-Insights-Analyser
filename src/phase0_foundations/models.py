from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional, Literal

class Review(BaseModel):
    review_id: str
    product: str               # e.g. "Groww"
    store: Literal["appstore", "playstore"]
    rating: int                # 1-5
    title: Optional[str] = None
    text: str
    date: datetime
    language: str = "en"

class CleanReview(Review):
    original_text: str         # preserved before PII scrub
    is_pii_scrubbed: bool = True

class Cluster(BaseModel):
    cluster_id: int
    label: Optional[str] = None       # assigned by HDBSCAN, -1 = noise
    reviews: List[CleanReview]
    centroid_indices: List[int] # top-k closest to centroid

class Theme(BaseModel):
    name: str
    description: str
    quotes: List[str]          # validated verbatim quotes
    action_ideas: List[str]

class PulseReport(BaseModel):
    product: str
    iso_week: str              # e.g. "2026-W17"
    period: str                # e.g. "Last 12 weeks"
    review_count: int
    themes: List[Theme]
    generated_at: datetime = datetime.now()

class RenderedReport(BaseModel):
    product: str
    iso_week: str
    doc_markdown: str          # for Google Docs append
    email_html: str            # for Gmail teaser
    heading_anchor: str        # stable ID for idempotency

class RunRecord(BaseModel):
    run_id: str
    product: str
    iso_week: str
    status: Literal["success", "failed", "skipped", "pending_email"]
    doc_id: Optional[str] = None
    heading_id: Optional[str] = None
    email_message_id: Optional[str] = None
    review_count: int = 0
    token_usage: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="ignore")
