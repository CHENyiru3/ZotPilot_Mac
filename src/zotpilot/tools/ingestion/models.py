"""Pydantic models for ingestion tool schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IngestCandidate(BaseModel):
    """Structured candidate handed from search results into ingestion."""

    model_config = ConfigDict(extra="ignore")

    doi: str | None = Field(
        default=None,
        description=(
            "Canonical publisher DOI (for example '10.1109/CVPR.2023.xxx'). "
            "Preferred when is_oa_published=True."
        ),
    )
    arxiv_id: str | None = Field(
        default=None,
        description=(
            "arXiv ID without version (for example '2301.00001'). "
            "Used for OA preprint routing when is_oa_published=False."
        ),
    )
    landing_page_url: str | None = Field(
        default=None,
        description=(
            "Publisher landing page URL from OpenAlex primary_location."
        ),
    )
    oa_url: str | None = Field(
        default=None,
        description="Best open-access URL from the search result.",
    )
    is_oa_published: bool = Field(
        default=False,
        description=(
            "Whether the published journal version is itself open access. "
            "True prefers the journal DOI route; False prefers arXiv when available."
        ),
    )
    title: str | None = Field(
        default=None,
        description="Paper title for traceability and wrong-paper guardrails.",
    )
    openalex_id: str | None = Field(
        default=None,
        description="OpenAlex work ID for traceability.",
    )
