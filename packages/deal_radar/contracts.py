"""Canonical data contracts. Evidence-first: every inferred fact keeps provenance."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FactStatus(str, Enum):
    SELLER_STATED = "seller_stated"
    VISIBLE_IN_IMAGE = "visible_in_image"
    OCR_EXTRACTED = "ocr_extracted"
    AI_INFERRED = "inferred"
    EXTERNAL = "external"
    UNKNOWN = "unknown"
    CONTRADICTED = "contradicted"
    VERIFIED = "verified"
    SUPPORTED = "supported"


class Evidence(BaseModel):
    type: str  # title|description|image|ocr|seller|external|benchmark
    detail: str = ""
    image_id: str | None = None
    confidence: float = 1.0


class Fact(BaseModel):
    value: Any
    status: FactStatus = FactStatus.UNKNOWN
    confidence: float = 0.0
    sources: list[Evidence] = Field(default_factory=list)


class Seller(BaseModel):
    name: str = ""
    id: str | None = None
    rating: float | None = None
    listings_count: int | None = None
    account_age_days: int | None = None


class CanonicalListing(BaseModel):
    id: str  # f"{source}:{native_id}"
    source: str
    native_id: str
    url: str
    title: str = ""
    description: str = ""
    price: float | None = None
    currency: str = "EUR"
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    seller: Seller = Field(default_factory=Seller)
    location: str = ""
    postcode: str = ""
    distance_km: float | None = None
    condition: str = ""
    shipping: str = ""  # raw shipping text, e.g. "Versand möglich", "Nur Abholung"
    shipping_cost: float | None = None
    pickup_available: bool = False
    shipping_available: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)
    ocr_texts: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=utcnow)

    def field_text(self, field: str) -> str:
        if field == "title":
            return self.title
        if field == "description":
            return self.description
        if field == "tags":
            return " ".join(self.tags)
        if field == "category":
            return self.category
        if field == "seller_name":
            return self.seller.name
        if field == "location":
            return self.location
        if field == "condition":
            return self.condition
        if field == "ocr":
            return "\n".join(self.ocr_texts)
        if field == "all_text":
            return " ".join([self.title, self.description, " ".join(self.tags), self.category, *self.ocr_texts])
        # attributes.* support
        if field.startswith("attributes."):
            key = field.split(".", 1)[1]
            v = self.attributes.get(key, "")
            return str(v) if v is not None else ""
        return ""


class RiskAssessment(BaseModel):
    score: float = 0.0  # 0..1, never boolean
    confidence: float = 0.0
    severity: str = "low"  # low|medium|high
    reasons: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    calibrated: bool = False


class EnrichmentFact(BaseModel):
    field: str
    value: Any
    confidence: float = 0.0
    status: FactStatus = FactStatus.UNKNOWN
    sources: list[Evidence] = Field(default_factory=list)


class ScoredListing(BaseModel):
    listing: CanonicalListing
    match_score: float = 0.0
    deal_dna: dict[str, float] = Field(default_factory=dict)
    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    enrichments: list[EnrichmentFact] = Field(default_factory=list)
    value_score: float = 0.0
    final_score: float = 0.0
    lane: str = "top"  # top|good|review|risky|hidden
    why: list[str] = Field(default_factory=list)
