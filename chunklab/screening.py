from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .models import Block, SourceSpan


ScreenDisposition = Literal["keep", "drop", "quarantine"]

POLICY_VERSION = "chunklab-prescreen-v0.3"


@dataclass(frozen=True)
class ScreenDecision:
    block_id: str
    disposition: ScreenDisposition
    reason_ko: str
    reason_en: str
    source: SourceSpan
    heading_path: list[str]
    block_type: str
    restored: bool = False


@dataclass(frozen=True)
class ScreenResult:
    blocks: list[Block]
    decisions: list[ScreenDecision]
    policy_version: str = POLICY_VERSION

    @property
    def removed(self) -> list[ScreenDecision]:
        return [decision for decision in self.decisions if decision.disposition in {"drop", "quarantine"} and not decision.restored]

    @property
    def quarantine(self) -> list[ScreenDecision]:
        return [decision for decision in self.decisions if decision.disposition == "quarantine" and not decision.restored]


_SAFE_BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*(©|copyright\b).{0,160}\ball rights reserved\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(cookie preferences|privacy choices|subscribe to newsletter)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(page|쪽)\s+\d+\s+(of|/)\s+\d+\s*$", re.IGNORECASE),
]

_SUSPICIOUS_AI_DIRECTED_PATTERNS = [
    re.compile(r"\b(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above)\s+instructions\b", re.IGNORECASE),
    re.compile(
        r"\b(ignore|disregard|forget|override|follow|obey|execute|reveal|print|show|send|exfiltrate)\b"
        r".{0,80}\b(system|developer)\s+(prompt|message|instruction)s?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(system|developer)\s+(prompt|message|instruction)s?\b"
        r".{0,80}\b(ignore|disregard|forget|override|follow|obey|execute|reveal|print|show|send|exfiltrate)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(reveal|print|exfiltrate|send)\s+.{0,40}\b(api\s*key|secret|token|credential)s?\b", re.IGNORECASE),
    re.compile(r"(이전|위의)\s*(지시|명령|규칙).{0,20}(무시|잊어|따르지)", re.IGNORECASE),
    re.compile(r"(무시|따라|실행|출력|공개|전송|유출).{0,80}(시스템|개발자)\s*(프롬프트|메시지|지시)", re.IGNORECASE),
    re.compile(r"(시스템|개발자)\s*(프롬프트|메시지|지시).{0,80}(무시|따라|실행|출력|공개|전송|유출)", re.IGNORECASE),
    re.compile(r"(비밀|토큰|자격\s*증명|API\s*키).{0,30}(출력|공개|전송|유출)", re.IGNORECASE),
]

_QUOTE_OR_EXAMPLE_MARKERS = [
    "example",
    "for example",
    "quoted",
    "quote:",
    "security example",
    "예시",
    "인용",
    "보안 예제",
    "보안 예시",
]

_REFERENCE_HEADINGS = {"references", "bibliography", "참고문헌", "참고 자료", "references / bibliography"}


def prescreen_blocks(blocks: list[Block], restore_block_ids: set[str] | None = None) -> ScreenResult:
    """Apply an opt-in deterministic pre-screen before chunking.

    The heuristic is intentionally conservative. It is not a safety guarantee,
    does not classify ordinary human instructions as noise, and keeps quoted
    examples, editor notes, and bibliography/reference sections.
    """

    restore_block_ids = restore_block_ids or set()
    kept: list[Block] = []
    decisions: list[ScreenDecision] = []

    for block in blocks:
        disposition, reason_ko, reason_en = _classify(block)
        restored = block.id in restore_block_ids and disposition in {"drop", "quarantine"}
        effective = "keep" if restored else disposition
        decisions.append(
            ScreenDecision(
                block_id=block.id,
                disposition=disposition,
                reason_ko=("사용자가 명시적으로 복원했습니다. " + reason_ko) if restored else reason_ko,
                reason_en=("Explicitly restored by the reviewer. " + reason_en) if restored else reason_en,
                source=block.source,
                heading_path=list(block.heading_path),
                block_type=block.type,
                restored=restored,
            )
        )
        if effective == "keep":
            flags = list(block.flags)
            if restored and "screen_restored" not in flags:
                flags.append("screen_restored")
            kept.append(
                Block(
                    id=block.id,
                    type=block.type,
                    text=block.text,
                    heading_path=list(block.heading_path),
                    source=block.source,
                    order=block.order,
                    indivisible=block.indivisible,
                    flags=flags,
                )
            )
    return ScreenResult(blocks=kept, decisions=decisions)


def _classify(block: Block) -> tuple[ScreenDisposition, str, str]:
    text = block.text.strip()
    lower = text.lower()
    if block.type == "heading":
        return "keep", "제목은 제거하지 않고 출처 맥락을 보존합니다.", "Heading kept to preserve source context."
    if _in_reference_section(block):
        return "keep", "참고문헌/레퍼런스 섹션은 보존합니다.", "Reference or bibliography section is kept."
    if _looks_like_quoted_example(block, lower):
        return "keep", "인용문·예시로 보이는 내용은 보존합니다.", "Quoted examples are kept."
    if any(pattern.search(text) for pattern in _SUSPICIOUS_AI_DIRECTED_PATTERNS):
        return (
            "quarantine",
            "명시적인 AI 대상 지시 또는 비밀 유출 요구로 보여 일반 내보내기에서 제외합니다.",
            "Explicit AI-directed or secret-exfiltration text; excluded from normal export.",
        )
    if any(pattern.fullmatch(text) or pattern.search(text) for pattern in _SAFE_BOILERPLATE_PATTERNS):
        return (
            "drop",
            "보수적인 구조 상용구 후보로 판단되어 일반 내보내기에서 제외합니다.",
            "Conservative structural boilerplate candidate; excluded from normal export.",
        )
    return "keep", "보존합니다.", "Kept."


def _in_reference_section(block: Block) -> bool:
    return any(part.strip().lower() in _REFERENCE_HEADINGS for part in block.heading_path)


def _looks_like_quoted_example(block: Block, lower: str) -> bool:
    if block.type == "blockquote" or lower.startswith(">"):
        return True
    if any(marker in lower for marker in _QUOTE_OR_EXAMPLE_MARKERS):
        return True
    # A suspicious phrase wrapped in quotation marks is more likely an example
    # than an operative instruction; keep it for reviewer-visible evidence.
    return bool(re.search(r'["“”\']\s*(ignore|disregard|이전|위의)', lower))
