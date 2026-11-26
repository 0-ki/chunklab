from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from .models import Chunk


POLICY_VERSION = "chunklab-quality-audit-v0.5"
UNKNOWN_CATEGORY = "unknown"


DEFAULT_TAXONOMY: dict[str, tuple[str, ...]] = {
    "returns_policy": ("return", "refund", "eligible", "반품", "환불", "대상"),
    "pricing": ("price", "fee", "cost", "payment", "가격", "요금", "결제"),
    "support": ("support", "contact", "help", "문의", "지원", "고객센터"),
    "security": ("security", "secret", "token", "credential", "보안", "비밀", "토큰", "자격"),
}


@dataclass(frozen=True)
class QualityAuditConfig:
    taxonomy: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(DEFAULT_TAXONOMY))
    max_categories: int = 3
    max_reasons: int = 6
    max_keywords_per_category: int = 16
    min_information_terms: int = 3
    min_information_bytes: int = 40
    policy_version: str = POLICY_VERSION


_EN_WORD_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,}", re.IGNORECASE)
_HANGUL_RE = re.compile(r"[가-힣0-9]+")
_LEADING_DEPENDENCY_RE = re.compile(
    r"^\s*(however|but|therefore|so|also|then|this|that|these|those|it|they|he|she|its|their)\b",
    re.IGNORECASE,
)
_KO_DEPENDENCY_RE = re.compile(r"^\s*(단|그러나|하지만|따라서|또한|그리고|이|그|해당|위|아래|전술한|후술한)")


def parse_taxonomy_lines(value: str) -> dict[str, tuple[str, ...]]:
    """Parse a small user taxonomy from ``category: keyword, keyword`` lines.

    Invalid or empty category names are ignored. The explicit ``unknown``
    fallback is always reserved by the audit output and should not be supplied.
    """

    taxonomy: dict[str, tuple[str, ...]] = {}
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        raw_name, raw_keywords = line.split(":", 1)
        name = _safe_category_name(raw_name)
        if not name or name == UNKNOWN_CATEGORY:
            continue
        keywords = tuple(
            keyword.strip().casefold()
            for keyword in re.split(r"[,|]", raw_keywords)
            if keyword.strip()
        )
        if keywords:
            taxonomy[name] = keywords
    return taxonomy


def taxonomy_to_text(taxonomy: dict[str, tuple[str, ...]] | None = None) -> str:
    source = taxonomy or DEFAULT_TAXONOMY
    return "\n".join(f"{name}: {', '.join(keywords)}" for name, keywords in source.items())


def audit_chunks(chunks: list[Chunk], config: QualityAuditConfig | None = None) -> list[Chunk]:
    """Return chunks with deterministic audit metadata.

    This is audit-first: no chunk is removed, reordered, rescored for ranking, or
    rewritten. Only flags and ``quality_audit`` export metadata are added.
    """

    config = config or QualityAuditConfig()
    _validate_config(config)
    audited: list[Chunk] = []
    for chunk in chunks:
        audit = _audit_chunk(chunk, config)
        flags = list(chunk.flags)
        if audit["low_information"]["value"] and "low_information" not in flags:
            flags.append("low_information")
        if not audit["self_contained"]["value"] and "self_contained" not in flags:
            flags.append("self_contained")
        audited.append(replace(chunk, flags=flags, audit={"quality": audit}))
    return audited


def _audit_chunk(chunk: Chunk, config: QualityAuditConfig) -> dict[str, Any]:
    terms = _terms(chunk.text)
    byte_count = len(chunk.text.encode("utf-8"))
    reasons: list[dict[str, Any]] = []

    low_information = len(terms) < config.min_information_terms or byte_count < config.min_information_bytes
    if low_information:
        reasons.append(
            _reason(
                "low_information",
                "rule:min_terms_or_bytes",
                f"Only {len(terms)} distinct lexical terms and {byte_count} UTF-8 bytes.",
                "서로 다른 어휘 항목 수 또는 UTF-8 바이트 수가 낮습니다.",
                score=min(1.0, max(len(terms) / max(1, config.min_information_terms), byte_count / max(1, config.min_information_bytes))),
            )
        )

    dependency_match = _LEADING_DEPENDENCY_RE.search(chunk.text) or _KO_DEPENDENCY_RE.search(chunk.text)
    self_contained = True
    if dependency_match and not chunk.heading_path:
        self_contained = False
        reasons.append(
            _reason(
                "self_contained",
                "rule:leading_dependency_marker_without_heading",
                f"Starts with context-dependent marker {dependency_match.group(0)!r} and has no heading path.",
                f"문맥 의존 표시({dependency_match.group(0)!r})로 시작하지만 제목 경로가 없습니다.",
                score=0.0,
            )
        )
    elif dependency_match:
        reasons.append(
            _reason(
                "self_contained",
                "rule:leading_dependency_marker_with_heading",
                f"Starts with context-dependent marker {dependency_match.group(0)!r}; heading path is available as context.",
                f"문맥 의존 표시({dependency_match.group(0)!r})로 시작하지만 제목 경로가 맥락으로 제공됩니다.",
                score=0.5,
            )
        )

    categories = _match_taxonomy(chunk.text, config)
    if categories == [UNKNOWN_CATEGORY]:
        reasons.append(
            _reason(
                "taxonomy",
                "rule:no_configured_keyword_match",
                "No configured taxonomy keyword matched conservatively; assigned explicit unknown.",
                "설정된 taxonomy 키워드가 보수적으로 일치하지 않아 unknown으로 표시했습니다.",
                score=0.0,
            )
        )

    return {
        "policy_version": config.policy_version,
        "mode": "deterministic_local_rules",
        "low_information": {
            "value": low_information,
            "score": round(min(1.0, len(terms) / max(1, config.min_information_terms)), 4),
            "score_provenance": "rule:distinct_lexical_terms_and_utf8_bytes",
        },
        "self_contained": {
            "value": self_contained,
            "score": 1.0 if self_contained else 0.0,
            "score_provenance": "rule:leading_dependency_marker_and_heading_path",
        },
        "taxonomy": {
            "labels": categories,
            "unknown": categories == [UNKNOWN_CATEGORY],
            "score_provenance": "rule:configured_keyword_exact_or_hangul_substring",
        },
        "caps": {
            "max_categories": config.max_categories,
            "max_reasons": config.max_reasons,
            "max_keywords_per_category": config.max_keywords_per_category,
        },
        "reasons": reasons[: config.max_reasons],
    }


def _match_taxonomy(text: str, config: QualityAuditConfig) -> list[str]:
    text_folded = text.casefold()
    terms = _terms(text)
    matched: list[str] = []
    for category, raw_keywords in config.taxonomy.items():
        safe = _safe_category_name(category)
        if not safe or safe == UNKNOWN_CATEGORY:
            continue
        for keyword in tuple(raw_keywords)[: config.max_keywords_per_category]:
            needle = keyword.strip().casefold()
            if not needle:
                continue
            if _keyword_matches(needle, text_folded, terms):
                matched.append(safe)
                break
        if len(matched) >= config.max_categories:
            break
    return matched or [UNKNOWN_CATEGORY]


def _keyword_matches(needle: str, text_folded: str, terms: set[str]) -> bool:
    if re.search(r"[가-힣]", needle):
        return needle in text_folded
    return needle in terms


def _terms(text: str) -> set[str]:
    lowered = text.casefold()
    terms = {match.group(0) for match in _EN_WORD_RE.finditer(lowered)}
    terms.update(match.group(0) for match in _HANGUL_RE.finditer(lowered))
    return terms


def _reason(flag: str, rule_id: str, reason_en: str, reason_ko: str, *, score: float) -> dict[str, Any]:
    return {
        "flag": flag,
        "rule_id": rule_id,
        "reason_en": reason_en,
        "reason_ko": reason_ko,
        "score": round(float(score), 4),
        "score_provenance": f"rule:{rule_id}",
    }


def _safe_category_name(raw: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", raw.strip().casefold()).strip("_")


def _validate_config(config: QualityAuditConfig) -> None:
    if config.max_categories <= 0:
        raise ValueError("max_categories must be positive")
    if config.max_reasons <= 0:
        raise ValueError("max_reasons must be positive")
    if config.max_keywords_per_category <= 0:
        raise ValueError("max_keywords_per_category must be positive")
    if config.min_information_terms <= 0:
        raise ValueError("min_information_terms must be positive")
    if config.min_information_bytes <= 0:
        raise ValueError("min_information_bytes must be positive")
