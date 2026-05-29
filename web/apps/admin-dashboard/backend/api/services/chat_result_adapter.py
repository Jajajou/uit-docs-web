"""Compatibility adapter for upstream chat results.

This keeps the /web backend tolerant to the new LangGraph direction:
- references prefer ``file_path`` over legacy ``file_source``
- responses may include ``response_type`` (full_answer / partial_answer / fallback)
- response text may be exposed as ``final_answer``, ``generated_response``,
  ``response_text`` or the legacy ``response``
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Literal

NormalizedResponseType = Literal["full_answer", "partial_answer", "fallback"]

_NO_CONTEXT_MARKERS = (
    "no relevant context found",
    "no query context could be built",
    "khong tim thay ngu canh",
    "khong co ngu canh",
    "khong tim thay thong tin phu hop",
)

_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_REFERENCE_SECTION_PATTERN = re.compile(
    r"(?:^|\n)\s{0,3}(?:#{1,6}\s*)?(?:tài liệu tham khảo|tai lieu tham khao|references?)\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)


@dataclass(slots=True)
class NormalizedChatResult:
    response_text: str
    response_type: NormalizedResponseType
    references: list[dict[str, Any]] = field(default_factory=list)
    confidence_summary: dict[str, Any] = field(default_factory=dict)
    no_context: bool = False


def normalize_reference_path(reference: dict[str, Any]) -> str:
    for key in ("file_path", "file_source", "url", "href", "source"):
        value = str(reference.get(key) or "").strip()
        if value:
            return value
    return ""


def _normalize_response_text(result: dict[str, Any]) -> str:
    for key in ("final_answer", "generated_response", "response_text", "response"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_markdown_references(response_text: str) -> list[dict[str, Any]]:
    if not response_text:
        return []

    section_start = _REFERENCE_SECTION_PATTERN.search(response_text)
    candidate_text = response_text[section_start.end() :] if section_start else response_text
    normalized: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for index, (title, href) in enumerate(_MARKDOWN_LINK_PATTERN.findall(candidate_text), start=1):
        normalized_title = title.strip()
        normalized_href = href.strip()
        if not normalized_title or not normalized_href or normalized_href in seen_paths:
            continue

        seen_paths.add(normalized_href)
        normalized.append(
            {
                "reference_id": f"ref-markdown-{index}",
                "title": normalized_title,
                "file_path": normalized_href,
                "href": normalized_href,
                "url": normalized_href,
                "excerpt": "Nguồn được trích trực tiếp từ phần tài liệu tham khảo của câu trả lời live.",
            }
        )

    return normalized


def _normalize_references(result: dict[str, Any], response_text: str) -> list[dict[str, Any]]:
    raw_references = result.get("references") or result.get("sources") or _extract_markdown_references(response_text)
    if not isinstance(raw_references, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw_references:
        if not isinstance(item, dict):
            continue
        reference = dict(item)
        normalized_path = normalize_reference_path(reference)
        if normalized_path:
            reference["file_path"] = normalized_path
        normalized.append(reference)
    return normalized


def _normalize_response_type(
    result: dict[str, Any],
    response_text: str,
    references: list[dict[str, Any]],
) -> NormalizedResponseType:
    raw_response_type = result.get("response_type")
    if raw_response_type is None:
        confidence_summary = result.get("confidence_summary")
        if isinstance(confidence_summary, dict):
            raw_response_type = confidence_summary.get("response_type")

    normalized = str(raw_response_type or "").strip().lower()
    if normalized in {"full_answer", "partial_answer", "fallback"}:
        return normalized
    if not response_text and not references:
        return "fallback"
    return "full_answer"


def _detect_no_context(response_text: str) -> bool:
    if not response_text:
        return True
    lower_text = response_text.casefold()
    return any(marker in lower_text for marker in _NO_CONTEXT_MARKERS)


def normalize_chat_result(result: dict[str, Any] | None) -> NormalizedChatResult:
    payload = result if isinstance(result, dict) else {}
    response_text = _normalize_response_text(payload)
    references = _normalize_references(payload, response_text)
    response_type = _normalize_response_type(payload, response_text, references)
    confidence_summary = payload.get("confidence_summary")
    normalized_confidence_summary = confidence_summary if isinstance(confidence_summary, dict) else {}
    return NormalizedChatResult(
        response_text=response_text,
        response_type=response_type,
        references=references,
        confidence_summary=normalized_confidence_summary,
        no_context=_detect_no_context(response_text),
    )
