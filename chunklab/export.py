from __future__ import annotations

import json
from typing import Any

from .chunker import structural_chunk
from .models import Chunk, Issue
from .parsers import ParsedDocument, parse_upload
from .screening import ScreenResult, prescreen_blocks
from .token_budget import Utf8ByteBudget


def process_upload(filename: str, data: bytes, hard_limit: int) -> tuple[ParsedDocument, list[Chunk], list[Issue]]:
    doc = parse_upload(filename, data)
    if not doc.blocks:
        raise ValueError("업로드한 파일에서 청킹할 수 있는 텍스트를 찾지 못했습니다.")
    chunks, issues = structural_chunk(doc.blocks, hard_limit=hard_limit, budget=Utf8ByteBudget())
    return doc, chunks, issues


def process_upload_screened(
    filename: str,
    data: bytes,
    hard_limit: int,
    *,
    restore_block_ids: set[str] | None = None,
) -> tuple[ParsedDocument, ScreenResult, list[Chunk], list[Issue]]:
    doc = parse_upload(filename, data)
    if not doc.blocks:
        raise ValueError("업로드한 파일에서 청킹할 수 있는 텍스트를 찾지 못했습니다.")
    screen = prescreen_blocks(doc.blocks, restore_block_ids=restore_block_ids)
    if not screen.blocks:
        raise ValueError("사전 검사 후 내보낼 수 있는 텍스트가 없습니다. 필요한 블록을 명시적으로 복원하세요.")
    chunks, issues = structural_chunk(screen.blocks, hard_limit=hard_limit, budget=Utf8ByteBudget())
    return doc, screen, chunks, issues


def chunk_to_record(doc: ParsedDocument, chunk: Chunk, budget_name: str = "utf8_bytes") -> dict[str, Any]:
    record = {
        "schema": "chunklab.offline.v1",
        "document": {
            "filename": doc.filename,
            "media_type": doc.media_type,
            "sha256": doc.sha256,
        },
        "chunk_id": chunk.id,
        "order": chunk.order,
        "text": chunk.text,
        "heading_path": chunk.heading_path,
        "source": chunk.source.to_json(),
        "block_ids": chunk.block_ids,
        "block_types": chunk.block_types,
        "budget": {"mode": budget_name, "count": chunk.budget_count},
        "flags": chunk.flags,
    }
    if chunk.audit:
        record["audit"] = chunk.audit
    return record


def chunks_to_jsonl(doc: ParsedDocument, chunks: list[Chunk]) -> str:
    return "\n".join(
        json.dumps(chunk_to_record(doc, chunk), ensure_ascii=False, sort_keys=True) for chunk in chunks
    ) + ("\n" if chunks else "")


def issues_to_report(issues: list[Issue]) -> str:
    if not issues:
        return "No issues.\n"
    return "\n".join(json.dumps(issue.to_json(), ensure_ascii=False, sort_keys=True) for issue in issues) + "\n"
