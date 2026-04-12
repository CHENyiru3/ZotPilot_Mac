"""Tests for structured ingest candidates and ingest_by_identifiers."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

import zotpilot.tools.ingestion as ingestion_tool
from zotpilot.state import ToolError
from zotpilot.tools.ingestion.models import IngestCandidate


@pytest.fixture
def ingest_env(monkeypatch):
    """Patch external dependencies so ingest tool tests stay local and deterministic."""
    zotero = MagicMock()
    zotero.get_item_key_by_doi.return_value = None
    zotero.get_item_key_by_arxiv_id.return_value = None

    monkeypatch.setattr(ingestion_tool, "_ensure_inbox_collection", lambda: "INBOX")
    monkeypatch.setattr(ingestion_tool, "_get_zotero", lambda: zotero)
    monkeypatch.setattr(ingestion_tool, "_get_writer", lambda: MagicMock())
    monkeypatch.setattr(
        ingestion_tool.connector,
        "check_connector_availability",
        lambda *args, **kwargs: (False, None, None),
    )
    monkeypatch.setattr(
        ingestion_tool.connector,
        "run_preflight_check",
        lambda *args, **kwargs: ([], [], False),
    )
    monkeypatch.setattr(
        ingestion_tool.connector,
        "resolve_doi_to_landing_url",
        lambda doi: f"https://resolved.example/{doi}",
    )
    monkeypatch.setattr(
        ingestion_tool.connector,
        "_doi_api_fallback",
        lambda doi, title, **kwargs: {
            "status": "saved_metadata_only",
            "method": "api_fallback",
            "item_key": f"KEY-{doi}",
            "has_pdf": False,
            "title": title or "",
            "action_required": None,
            "warning": "Created via DOI API",
        },
    )
    return zotero


def test_candidate_accepts_minimal_doi():
    candidate = IngestCandidate(doi="10.1/x")
    assert candidate.doi == "10.1/x"


def test_candidate_accepts_minimal_arxiv():
    candidate = IngestCandidate(arxiv_id="2301.00001")
    assert candidate.arxiv_id == "2301.00001"


def test_candidate_extras_ignored():
    candidate = IngestCandidate.model_validate(
        {
            "doi": "10.1/x",
            "title": "Paper",
            "cited_by_count": 100,
            "authors": ["Ada"],
            "venue": {"display_name": "Nature"},
            "publisher": "Nature",
            "journal": "Nature",
            "top_venue": True,
            "local_duplicate": False,
            "existing_item_key": None,
        }
    )

    assert candidate.doi == "10.1/x"
    assert set(candidate.model_dump()) == {
        "doi",
        "arxiv_id",
        "landing_page_url",
        "oa_url",
        "is_oa_published",
        "title",
        "openalex_id",
    }


def test_candidate_empty_is_valid_at_pydantic_layer():
    candidate = IngestCandidate()
    assert candidate.model_dump() == {
        "doi": None,
        "arxiv_id": None,
        "landing_page_url": None,
        "oa_url": None,
        "is_oa_published": False,
        "title": None,
        "openalex_id": None,
    }


def test_save_priority_journal_when_oa_published_true():
    internal = ingestion_tool._candidates_to_internal(
        [
            IngestCandidate(
                doi="10.1234/journal",
                arxiv_id="2301.00001",
                is_oa_published=True,
            )
        ]
    )[0]

    assert internal["doi"] == "10.1234/journal"
    assert internal["url"] == "https://doi.org/10.1234/journal"


def test_save_priority_arxiv_when_oa_published_false():
    internal = ingestion_tool._candidates_to_internal(
        [
            IngestCandidate(
                doi="10.1234/journal",
                arxiv_id="2301.00001",
                is_oa_published=False,
            )
        ]
    )[0]

    assert internal["doi"] == "10.48550/arxiv.2301.00001"
    assert internal["url"] == "https://arxiv.org/abs/2301.00001"
    assert internal["source_doi"] == "10.1234/journal"


def test_save_priority_arxiv_only():
    internal = ingestion_tool._candidates_to_internal(
        [IngestCandidate(arxiv_id="2301.00001")]
    )[0]

    assert internal["doi"] == "10.48550/arxiv.2301.00001"
    assert internal["url"] == "https://arxiv.org/abs/2301.00001"


def test_save_priority_doi_only_non_oa():
    internal = ingestion_tool._candidates_to_internal(
        [IngestCandidate(doi="10.1234/journal", is_oa_published=False)]
    )[0]

    assert internal["doi"] == "10.1234/journal"
    assert internal["url"] == "https://doi.org/10.1234/journal"


def test_save_priority_landing_fallback():
    internal = ingestion_tool._candidates_to_internal(
        [IngestCandidate(landing_page_url="https://publisher.example/paper")]
    )[0]

    assert internal["doi"] is None
    assert internal["url"] == "https://publisher.example/paper"


def test_save_priority_all_empty_fails(ingest_env):
    result = ingestion_tool.ingest_by_identifiers(candidates=[IngestCandidate()])

    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["error"] == "no_usable_identifier"
    assert result["results"][0]["candidate_index"] == 0


def test_dedup_cross_identifier_journal_in_library_arxiv_input(ingest_env):
    ingest_env.get_item_key_by_doi.side_effect = (
        lambda doi: "ITEMJOURNAL" if doi == "10.1234/journal" else None
    )

    result = ingestion_tool.ingest_by_identifiers(
        candidates=[
            IngestCandidate(
                doi="10.1234/journal",
                arxiv_id="2301.00001",
                is_oa_published=False,
                title="Paper",
            )
        ]
    )

    assert result["results"][0]["status"] == "duplicate"
    assert result["results"][0]["item_key"] == "ITEMJOURNAL"


def test_dedup_cross_identifier_arxiv_in_library_journal_input(ingest_env):
    ingest_env.get_item_key_by_doi.side_effect = (
        lambda doi: "ITEMARXIV" if doi == "10.48550/arxiv.2301.00001" else None
    )

    result = ingestion_tool.ingest_by_identifiers(
        candidates=[
            IngestCandidate(
                doi="10.1234/journal",
                arxiv_id="2301.00001",
                is_oa_published=True,
                title="Paper",
            )
        ]
    )

    assert result["results"][0]["status"] == "duplicate"
    assert result["results"][0]["item_key"] == "ITEMARXIV"


def test_dedup_via_extra_field(ingest_env):
    ingest_env.get_item_key_by_arxiv_id.side_effect = (
        lambda arxiv_id: "ITEMEXTRA" if arxiv_id == "2301.00001" else None
    )

    result = ingestion_tool.ingest_by_identifiers(
        candidates=[
            IngestCandidate(
                doi="10.1234/journal",
                arxiv_id="2301.00001",
                is_oa_published=True,
                title="Paper",
            )
        ]
    )

    assert result["results"][0]["status"] == "duplicate"
    assert result["results"][0]["item_key"] == "ITEMEXTRA"


def test_exactly_one_candidates_xor_identifiers(ingest_env):
    with pytest.raises(ToolError):
        ingestion_tool.ingest_by_identifiers(
            candidates=[IngestCandidate(doi="10.1/x")],
            identifiers=["10.1/x"],
        )


def test_neither_candidates_nor_identifiers_fails():
    with pytest.raises(ToolError):
        ingestion_tool.ingest_by_identifiers()


def test_empty_candidates_list_rejected(ingest_env):
    """Empty list is indistinguishable from 'no useful input' — reject loudly.

    This catches the 'upstream filter wiped every selection' bug where
    agents chain `[r for r in search_results if not r['local_duplicate']]`
    and the filter removes everything. Silent success (`total=0`) would
    hide the bug; loud failure surfaces it.
    """
    with pytest.raises(ToolError, match="at least one candidate"):
        ingestion_tool.ingest_by_identifiers(candidates=[])


def test_empty_identifiers_list_rejected(ingest_env):
    """Same rule for the deprecated str branch — empty list is not a valid call."""
    with pytest.raises(ToolError, match="at least one candidate"):
        ingestion_tool.ingest_by_identifiers(identifiers=[])


def test_empty_candidates_error_mentions_upstream_filter(ingest_env):
    """The error message must coach agents on the common 'filter ate everything'
    failure mode — regression guard on user-facing guidance text."""
    with pytest.raises(ToolError) as exc_info:
        ingestion_tool.ingest_by_identifiers(candidates=[])
    assert "upstream filter" in str(exc_info.value)


def test_str_branch_still_works_with_deprecation_warning(ingest_env, caplog):
    with caplog.at_level(logging.WARNING, logger="zotpilot.tools.ingestion"):
        result = ingestion_tool.ingest_by_identifiers(identifiers=["10.1234/test"])

    assert result["results"][0]["status"] == "saved_metadata_only"
    assert result["results"][0]["identifier"] == "10.1234/test"
    assert "deprecated identifiers=<list[str]>" in caplog.text


# ---------------------------------------------------------------------------
# MCP client compat: list params serialized as JSON strings
# ---------------------------------------------------------------------------
# Some MCP client wrappers (Qwen-based 'Sisyphus' runtimes, older Claude Code
# builds) send list[T] params as JSON strings instead of real arrays. The tool
# must accept both forms transparently via a Pydantic BeforeValidator.

def test_candidates_accepts_json_string(ingest_env):
    """A JSON-string form of candidates must be parsed before Pydantic validation."""
    payload = '[{"doi": "10.1234/test", "title": "JSON-string candidate"}]'
    result = ingestion_tool.ingest_by_identifiers(candidates=payload)

    assert result["total"] == 1
    assert result["results"][0]["status"] == "saved_metadata_only"
    assert result["results"][0]["identifier"] == "10.1234/test"


def test_identifiers_accepts_json_string(ingest_env):
    """A JSON-string form of identifiers must also be accepted via BeforeValidator."""
    payload = '["10.1234/test"]'
    result = ingestion_tool.ingest_by_identifiers(identifiers=payload)

    assert result["total"] == 1
    assert result["results"][0]["status"] == "saved_metadata_only"
    assert result["results"][0]["identifier"] == "10.1234/test"


def test_candidates_malformed_json_raises_type_error(ingest_env):
    """Malformed JSON passes through as str, Pydantic then reports a type error —
    never silently swallow so the caller sees what went wrong."""
    from pydantic import ValidationError

    with pytest.raises((ToolError, ValidationError)):
        ingestion_tool.ingest_by_identifiers(candidates="not json at all")


def test_candidates_empty_json_string_list_rejected(ingest_env):
    """JSON-string `[]` still hits the empty-list rejection (the upstream-filter
    failure mode shouldn't have an escape hatch via string wrapping)."""
    with pytest.raises(ToolError, match="at least one candidate"):
        ingestion_tool.ingest_by_identifiers(candidates="[]")


# ---------------------------------------------------------------------------
# _parse_json_string_list helper — unit tests
# ---------------------------------------------------------------------------
# The helper is attached via Pydantic BeforeValidator to four different params:
# ingest_by_identifiers(candidates, identifiers) and
# search_academic_databases(concepts, institutions). Exercising it in isolation
# covers all four paths without mocking OpenAlex in the search path.

def test_parse_json_string_list_passes_through_real_list():
    from zotpilot.tools.ingestion import _parse_json_string_list
    payload = [{"doi": "10.1/x"}]
    assert _parse_json_string_list(payload) is payload  # identity, no copy


def test_parse_json_string_list_passes_through_none():
    from zotpilot.tools.ingestion import _parse_json_string_list
    assert _parse_json_string_list(None) is None


def test_parse_json_string_list_decodes_json_array_of_dicts():
    from zotpilot.tools.ingestion import _parse_json_string_list
    result = _parse_json_string_list('[{"doi": "10.1/x"}, {"arxiv_id": "2301.00001"}]')
    assert isinstance(result, list)
    assert result == [{"doi": "10.1/x"}, {"arxiv_id": "2301.00001"}]


def test_parse_json_string_list_decodes_json_array_of_strings():
    from zotpilot.tools.ingestion import _parse_json_string_list
    result = _parse_json_string_list('["Computer vision", "NLP"]')
    assert result == ["Computer vision", "NLP"]


def test_parse_json_string_list_malformed_passes_through_string():
    """Malformed input stays as a string so Pydantic surfaces a clear type error
    instead of us silently returning [] and masking the bug."""
    from zotpilot.tools.ingestion import _parse_json_string_list
    bad = "not valid json"
    assert _parse_json_string_list(bad) == bad


def test_parse_json_string_list_scalar_json_passes_through():
    """If the JSON decodes but isn't a list (e.g. '42' or '{}'), return unchanged
    so Pydantic validates it against the declared list[T] type and errors out."""
    from zotpilot.tools.ingestion import _parse_json_string_list
    assert _parse_json_string_list('42') == '42'
    assert _parse_json_string_list('{"doi": "10.1/x"}') == '{"doi": "10.1/x"}'
