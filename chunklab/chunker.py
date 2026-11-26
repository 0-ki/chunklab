from __future__ import annotations

from collections.abc import Collection

from .models import Block, Chunk, Issue, SourceSpan
from .token_budget import Utf8ByteBudget


def structural_chunk(
    blocks: list[Block],
    hard_limit: int,
    budget: Utf8ByteBudget | None = None,
    extra_cut_after_block_ids: Collection[str] | None = None,
) -> tuple[list[Chunk], list[Issue]]:
    if hard_limit <= 0:
        raise ValueError("hard_limit must be positive")
    budget = budget or Utf8ByteBudget()
    extra_cuts = set(extra_cut_after_block_ids or [])
    chunks: list[Chunk] = []
    issues: list[Issue] = []
    current: list[Block] = []
    current_count = 0

    def flush() -> None:
        nonlocal current, current_count
        if not current:
            return
        text = "\n\n".join(block.text for block in current)
        count = budget.count(text)
        source = _merge_sources([b.source for b in current])
        flags = sorted({flag for b in current for flag in b.flags})
        chunks.append(
            Chunk(
                id=f"c{len(chunks):04d}",
                order=len(chunks),
                text=text,
                heading_path=list(current[-1].heading_path),
                source=source,
                block_ids=[b.id for b in current],
                block_types=[b.type for b in current],
                budget_count=count,
                flags=flags,
            )
        )
        current = []
        current_count = 0

    def add_piece(block: Block) -> None:
        nonlocal current, current_count
        if block.type == "heading" and current:
            flush()
        sep = 2 if current else 0
        count = budget.count(block.text)
        if current and current_count + sep + count > hard_limit:
            flush()
        current.append(block)
        current_count = budget.count("\n\n".join(b.text for b in current))

    for block in blocks:
        count = budget.count(block.text)
        if count <= hard_limit:
            add_piece(block)
            if block.id in extra_cuts:
                flush()
            continue
        if block.indivisible:
            flush()
            issues.append(
                Issue(
                    id=f"i{len(issues):04d}",
                    severity="error",
                    message=(
                        f"{block.type} block is indivisible and exceeds hard limit "
                        f"({count} > {hard_limit}); excluded from JSONL export."
                    ),
                    block_id=block.id,
                    block_type=block.type,
                    budget_count=count,
                    source=block.source,
                    heading_path=list(block.heading_path),
                )
            )
            continue
        for piece_index, piece in enumerate(_split_divisible_block(block, hard_limit, budget)):
            add_piece(piece)
    flush()

    over = [chunk for chunk in chunks if chunk.budget_count > hard_limit]
    if over:
        raise RuntimeError(f"internal error: chunks exceeded hard limit: {[chunk.id for chunk in over]}")
    return chunks, issues


def _merge_sources(sources: list[SourceSpan]) -> SourceSpan:
    notes = [source.note for source in sources if source.note]
    note = " | ".join(dict.fromkeys(notes)) or None
    if not sources:
        return SourceSpan(mapped=False, note="No source spans available.")
    if not all(source.mapped for source in sources):
        return SourceSpan(
            mapped=False,
            note=note or "One or more source spans are unmapped.",
        )

    line_starts = [source.line_start for source in sources if source.line_start is not None]
    line_ends = [source.line_end for source in sources if source.line_end is not None]
    span_starts = [source.span_start for source in sources if source.span_start is not None]
    span_ends = [source.span_end for source in sources if source.span_end is not None]
    if not line_starts or not line_ends:
        return SourceSpan(mapped=False, note=note or "Mapped source lacks line numbers.")

    line_start = min(line_starts)
    line_end = max(line_ends)
    if span_starts and span_ends:
        return SourceSpan(line_start, line_end, min(span_starts), max(span_ends), True, note)
    return SourceSpan(
        line_start=line_start,
        line_end=line_end,
        span_start=None,
        span_end=None,
        mapped=True,
        note=note or "Line-only provenance; character span unavailable after split.",
    )


def _split_divisible_block(block: Block, hard_limit: int, budget: Utf8ByteBudget) -> list[Block]:
    pieces: list[Block] = []
    lines = block.text.splitlines() or [block.text]
    buffer: list[str] = []
    start_line = block.source.line_start
    piece_no = 0

    def emit(end_line: int | None) -> None:
        nonlocal buffer, start_line, piece_no
        text = "\n".join(buffer).strip()
        if text:
            source = SourceSpan(
                line_start=start_line,
                line_end=end_line,
                span_start=None,
                span_end=None,
                mapped=block.source.mapped and start_line is not None and end_line is not None,
                note="Line-only provenance after hard-limit split; character span unavailable.",
            )
            pieces.append(
                Block(
                    id=f"{block.id}.{piece_no}",
                    type=block.type,
                    text=text,
                    heading_path=list(block.heading_path),
                    source=source,
                    order=block.order,
                    flags=block.flags + ["split_for_hard_limit"],
                )
            )
            piece_no += 1
        buffer = []
        start_line = (end_line + 1) if end_line is not None else None

    for offset, line in enumerate(lines):
        actual_line = (block.source.line_start + offset) if block.source.line_start is not None else None
        candidate = "\n".join(buffer + [line]).strip()
        if candidate and budget.count(candidate) <= hard_limit:
            buffer.append(line)
            continue
        if buffer:
            emit(actual_line - 1 if actual_line is not None else None)
        if budget.count(line) <= hard_limit:
            buffer = [line]
            start_line = actual_line
        else:
            for part in _split_long_text(line, hard_limit, budget):
                pieces.append(
                    Block(
                        id=f"{block.id}.{piece_no}",
                        type=block.type,
                        text=part,
                        heading_path=list(block.heading_path),
                        source=SourceSpan(
                            line_start=actual_line,
                            line_end=actual_line,
                            span_start=None,
                            span_end=None,
                            mapped=block.source.mapped and actual_line is not None,
                            note="Line-only provenance after hard-limit split within one line; character span unavailable.",
                        ),
                        order=block.order,
                        flags=block.flags + ["split_for_hard_limit", "line_split_for_hard_limit"],
                    )
                )
                piece_no += 1
            buffer = []
            start_line = (actual_line + 1) if actual_line is not None else None
    if buffer:
        end_line = (start_line + len(buffer) - 1) if start_line is not None else None
        emit(end_line)
    return pieces


def _split_long_text(text: str, hard_limit: int, budget: Utf8ByteBudget) -> list[str]:
    parts: list[str] = []
    current = ""
    for char in text:
        if current and budget.count(current + char) > hard_limit:
            parts.append(current)
            current = char
        else:
            current += char
    if current:
        parts.append(current)
    return parts
