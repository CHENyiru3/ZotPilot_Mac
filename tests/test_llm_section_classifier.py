"""Tests for optional LLM section refinement."""

from __future__ import annotations

import json

import httpx

from zotpilot.models import SectionSpan
from zotpilot.pdf.llm_section_classifier import DeepSeekSectionClassifier


def _response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
    )


def test_refines_unknown_section_with_deepseek(monkeypatch):
    calls = []

    def fake_post(self, url, *, headers, json):  # noqa: ANN001, ARG001
        calls.append(json)
        content = {"sections": [{"id": 1, "label": "results", "confidence": 0.82}]}
        return _response(200, {"choices": [{"message": {"content": json_module.dumps(content)}}]})

    json_module = json
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    text = "Abstract\n" + ("known abstract. " * 20) + "\nSpatial transcriptomic clocks\n" + ("result text. " * 80)
    split = text.index("Spatial transcriptomic clocks")
    sections = [
        SectionSpan("abstract", 0, split, "Abstract", 1.0),
        SectionSpan("unknown", split, len(text), "Spatial transcriptomic clocks", 0.5),
    ]
    classifier = DeepSeekSectionClassifier(api_key="test-key", unknown_threshold=0.1)

    refined = classifier.refine_sections(
        full_markdown=text,
        sections=sections,
        title="Brain ageing",
        publication="Nature",
        year=2026,
    )

    assert refined[1].label == "results"
    assert refined[1].confidence == 0.82
    assert calls[0]["model"] == "deepseek-v4-pro"
    assert calls[0]["thinking"] == {"type": "disabled"}


def test_low_confidence_decision_is_ignored(monkeypatch):
    def fake_post(self, url, *, headers, json):  # noqa: ANN001, ARG001
        content = {"sections": [{"id": 0, "label": "methods", "confidence": 0.4}]}
        return _response(200, {"choices": [{"message": {"content": json_module.dumps(content)}}]})

    json_module = json
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    text = "Unknown heading\n" + ("protocol text. " * 80)
    sections = [SectionSpan("unknown", 0, len(text), "Unknown heading", 0.5)]
    classifier = DeepSeekSectionClassifier(api_key="test-key", unknown_threshold=0.1)

    refined = classifier.refine_sections(full_markdown=text, sections=sections)

    assert refined[0].label == "unknown"


def test_no_api_call_when_unknown_ratio_is_low(monkeypatch):
    def fake_post(self, url, *, headers, json):  # noqa: ANN001, ARG001
        raise AssertionError("DeepSeek should not be called")

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    text = ("known text. " * 200) + "tiny unknown"
    split = len(text) - len("tiny unknown")
    sections = [
        SectionSpan("results", 0, split, "Results", 1.0),
        SectionSpan("unknown", split, len(text), "", 0.5),
    ]
    classifier = DeepSeekSectionClassifier(api_key="test-key", unknown_threshold=0.2)

    refined = classifier.refine_sections(full_markdown=text, sections=sections)

    assert refined is sections


def test_retries_without_thinking_if_endpoint_rejects_parameter(monkeypatch):
    statuses = []

    def fake_post(self, url, *, headers, json):  # noqa: ANN001, ARG001
        statuses.append("thinking" in json)
        if "thinking" in json:
            return _response(400, {"error": {"message": "unknown field"}})
        content = {"sections": [{"id": 0, "label": "discussion", "confidence": 0.7}]}
        return _response(200, {"choices": [{"message": {"content": json_module.dumps(content)}}]})

    json_module = json
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    text = "Interpretation\n" + ("discussion text. " * 80)
    sections = [SectionSpan("unknown", 0, len(text), "Interpretation", 0.5)]
    classifier = DeepSeekSectionClassifier(api_key="test-key", unknown_threshold=0.1)

    refined = classifier.refine_sections(full_markdown=text, sections=sections)

    assert refined[0].label == "discussion"
    assert statuses == [True, False]
