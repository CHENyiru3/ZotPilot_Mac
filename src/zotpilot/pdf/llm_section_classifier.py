"""Optional LLM-assisted section refinement for difficult article layouts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from ..models import SectionSpan

logger = logging.getLogger(__name__)

VALID_SECTION_LABELS = {
    "abstract",
    "introduction",
    "background",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "references",
    "appendix",
    "preamble",
    "unknown",
}


@dataclass
class SectionLLMDecision:
    """A single LLM section classification decision."""

    section_id: int
    label: str
    confidence: float


class DeepSeekSectionClassifier:
    """Refine ambiguous section spans with DeepSeek's OpenAI-compatible chat API.

    This is intentionally conservative: only unknown spans are sent, each
    candidate is bounded to a short heading/snippet, and low-confidence
    decisions are ignored.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-v4-pro",
        base_url: str = "https://api.deepseek.com",
        timeout: float = 30.0,
        max_spans: int = 24,
        unknown_threshold: float = 0.15,
        min_confidence: float = 0.65,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_spans = max_spans
        self.unknown_threshold = unknown_threshold
        self.min_confidence = min_confidence

    def refine_sections(
        self,
        *,
        full_markdown: str,
        sections: list[SectionSpan],
        title: str = "",
        publication: str = "",
        year: int | None = None,
    ) -> list[SectionSpan]:
        """Return refined sections, or the original list if refinement is unnecessary."""
        if not self._needs_refinement(full_markdown, sections):
            return sections

        candidates = self._build_candidates(full_markdown, sections)
        if not candidates:
            return sections

        try:
            decisions = self._classify(candidates, title=title, publication=publication, year=year)
        except Exception as exc:
            logger.warning("DeepSeek section refinement failed: %s", exc)
            return sections

        if not decisions:
            return sections

        return self._apply_decisions(sections, decisions)

    def _needs_refinement(self, full_markdown: str, sections: list[SectionSpan]) -> bool:
        total = max(len(full_markdown.strip()), 1)
        unknown_chars = sum(
            max(0, min(span.char_end, len(full_markdown)) - max(span.char_start, 0))
            for span in sections
            if span.label == "unknown"
        )
        return (unknown_chars / total) >= self.unknown_threshold

    def _build_candidates(self, full_markdown: str, sections: list[SectionSpan]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        total = max(len(full_markdown), 1)
        for idx, span in enumerate(sections):
            if span.label != "unknown":
                continue
            text = full_markdown[span.char_start:span.char_end].strip()
            if len(text) < 180:
                continue
            prev_label = sections[idx - 1].label if idx > 0 else ""
            next_label = sections[idx + 1].label if idx + 1 < len(sections) else ""
            candidates.append({
                "id": idx,
                "heading": span.heading_text[:180],
                "position": round(span.char_start / total, 3),
                "prev_label": prev_label,
                "next_label": next_label,
                "snippet": text[:900],
            })
            if len(candidates) >= self.max_spans:
                break
        return candidates

    def _classify(
        self,
        candidates: list[dict[str, Any]],
        *,
        title: str,
        publication: str,
        year: int | None,
    ) -> list[SectionLLMDecision]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You classify academic paper section spans. Return JSON only. "
                        "Use only these labels: abstract, introduction, background, methods, "
                        "results, discussion, conclusion, references, appendix, preamble, unknown. "
                        "Prefer unknown when evidence is weak."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "Classify each candidate span into one section label.",
                            "paper": {
                                "title": title,
                                "publication": publication,
                                "year": year,
                            },
                            "candidates": candidates,
                            "response_schema": {
                                "sections": [
                                    {"id": "candidate id", "label": "section label", "confidence": "0.0-1.0"}
                                ]
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": max(256, min(2048, 80 * len(candidates))),
            "response_format": {"type": "json_object"},
        }
        if self.model.startswith("deepseek-v4"):
            payload["thinking"] = {"type": "disabled"}

        data = self._post_chat(payload)
        content = data["choices"][0]["message"].get("content", "")
        parsed = json.loads(content)
        return self._parse_decisions(parsed)

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 400 and "thinking" in payload:
                retry_payload = dict(payload)
                retry_payload.pop("thinking", None)
                response = client.post(url, headers=headers, json=retry_payload)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}

    def _parse_decisions(self, parsed: dict[str, Any]) -> list[SectionLLMDecision]:
        raw_sections = parsed.get("sections", [])
        if not isinstance(raw_sections, list):
            return []

        decisions: list[SectionLLMDecision] = []
        for item in raw_sections:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip().lower()
            if label not in VALID_SECTION_LABELS:
                continue
            try:
                raw_id = item.get("id")
                if raw_id is None:
                    continue
                section_id = int(raw_id)
                confidence = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            decisions.append(SectionLLMDecision(section_id=section_id, label=label, confidence=confidence))
        return decisions

    def _apply_decisions(
        self,
        sections: list[SectionSpan],
        decisions: list[SectionLLMDecision],
    ) -> list[SectionSpan]:
        by_id = {decision.section_id: decision for decision in decisions}
        refined: list[SectionSpan] = []
        changed = 0
        for idx, span in enumerate(sections):
            decision = by_id.get(idx)
            if (
                span.label == "unknown"
                and decision is not None
                and decision.label != "unknown"
                and decision.confidence >= self.min_confidence
            ):
                refined.append(SectionSpan(
                    label=decision.label,
                    char_start=span.char_start,
                    char_end=span.char_end,
                    heading_text=span.heading_text,
                    confidence=min(max(decision.confidence, 0.0), 0.95),
                ))
                changed += 1
            else:
                refined.append(span)

        if changed:
            logger.info("DeepSeek section refinement relabeled %d unknown span(s)", changed)
        return refined
