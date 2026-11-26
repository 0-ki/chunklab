from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

from .models import Block, SourceSpan


@dataclass(frozen=True)
class ParsedDocument:
    filename: str
    media_type: str
    text: str
    sha256: str
    blocks: list[Block]


def parse_upload(filename: str, data: bytes) -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".md", ".markdown", ".html", ".htm", ".txt"}:
        raise ValueError("지원하지 않는 파일 형식입니다. Markdown, HTML, TXT만 업로드할 수 있습니다.")
    text = data.decode("utf-8", errors="replace")
    sha256 = hashlib.sha256(data).hexdigest()
    if suffix in {".md", ".markdown"}:
        blocks = parse_markdown(text)
        media_type = "text/markdown"
    elif suffix in {".html", ".htm"}:
        blocks = parse_html(text)
        media_type = "text/html"
    else:
        blocks = parse_txt(text)
        media_type = "text/plain"
    return ParsedDocument(filename=filename, media_type=media_type, text=text, sha256=sha256, blocks=blocks)


def _line_offsets(text: str) -> list[int]:
    offsets = []
    current = 0
    for line in text.splitlines(keepends=True):
        offsets.append(current)
        current += len(line)
    if not offsets:
        offsets.append(0)
    return offsets


def _source_for_lines(text: str, start_zero: int, end_zero_exclusive: int) -> SourceSpan:
    offsets = _line_offsets(text)
    line_count = len(text.splitlines()) or 1
    start_line = min(start_zero + 1, line_count)
    end_line = min(max(end_zero_exclusive, start_zero + 1), line_count)
    span_start = offsets[start_zero] if start_zero < len(offsets) else len(text)
    if end_zero_exclusive < len(offsets):
        span_end = offsets[end_zero_exclusive]
    else:
        span_end = len(text)
    return SourceSpan(start_line, end_line, span_start, span_end, True)


def _slice_lines(text: str, start_zero: int, end_zero_exclusive: int) -> str:
    return "".join(text.splitlines(keepends=True)[start_zero:end_zero_exclusive]).strip("\n")


def parse_markdown(text: str) -> list[Block]:
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(text)
    blocks: list[Block] = []
    headings_by_level: dict[int, str] = {}
    covered: list[tuple[int, int]] = []
    order = 0

    def is_covered(start: int, end: int) -> bool:
        return any(start >= a and end <= b for a, b in covered)

    i = 0
    while i < len(tokens):
        token = tokens[i]
        line_map = token.map
        if line_map is None:
            i += 1
            continue
        start, end = line_map
        if is_covered(start, end):
            i += 1
            continue

        block_type: str | None = None
        indivisible = False
        content: str | None = None

        if token.type == "heading_open":
            level = int(token.tag[1])
            inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
            title = inline.content.strip() if inline else _slice_lines(text, start, end).lstrip("#").strip()
            headings_by_level = {k: v for k, v in headings_by_level.items() if k < level}
            headings_by_level[level] = title
            block_type = "heading"
            content = _slice_lines(text, start, end)
        elif token.type == "paragraph_open":
            block_type = "paragraph"
        elif token.type in {"bullet_list_open", "ordered_list_open", "blockquote_open"}:
            block_type = token.type.replace("_open", "")
            covered.append((start, end))
        elif token.type == "table_open":
            block_type = "table"
            indivisible = True
            covered.append((start, end))
        elif token.type in {"fence", "code_block"}:
            block_type = "code"
            indivisible = True
            content = _slice_lines(text, start, end)
        elif token.type == "html_block":
            block_type = "html_block_text"
            content = _slice_lines(text, start, end)

        if block_type:
            block_text = (content if content is not None else _slice_lines(text, start, end)).strip()
            if block_text:
                blocks.append(
                    Block(
                        id=f"b{order:04d}",
                        type=block_type,
                        text=block_text,
                        heading_path=[headings_by_level[k] for k in sorted(headings_by_level)],
                        source=_source_for_lines(text, start, end),
                        order=order,
                        indivisible=indivisible,
                    )
                )
                order += 1
        i += 1
    return blocks


def parse_txt(text: str) -> list[Block]:
    blocks: list[Block] = []
    lines = text.splitlines()
    order = 0
    start: int | None = None
    buffer: list[str] = []
    heading_path: list[str] = []

    def flush(end_index: int) -> None:
        nonlocal order, start, buffer
        if start is None or not buffer:
            return
        body = "\n".join(buffer).strip()
        if body:
            blocks.append(
                Block(
                    id=f"b{order:04d}",
                    type="paragraph",
                    text=body,
                    heading_path=list(heading_path),
                    source=_source_for_lines(text, start, end_index),
                    order=order,
                )
            )
            order += 1
        start = None
        buffer = []

    for idx, line in enumerate(lines):
        if not line.strip():
            flush(idx)
            continue
        if start is None:
            start = idx
        buffer.append(line)
    flush(len(lines))
    return blocks


def _clean_html_text(value: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", unescape(value)).strip()


def _dom_path(tag) -> str:
    parts: list[str] = []
    current = tag
    while current and getattr(current, "name", None) and current.name != "[document]":
        if not current.parent:
            parts.append(current.name)
        else:
            siblings = [s for s in current.parent.find_all(current.name, recursive=False)]
            index = siblings.index(current) + 1 if current in siblings else 1
            parts.append(f"{current.name}[{index}]")
        current = current.parent
    return " > ".join(reversed(parts))


def parse_html(text: str) -> list[Block]:
    soup = BeautifulSoup(text, "lxml")
    for unsafe in soup(["script", "style", "noscript", "template", "iframe", "object", "embed"]):
        unsafe.decompose()

    root = soup.body or soup
    blocks: list[Block] = []
    headings_by_level: dict[int, str] = {}
    order = 0
    seen: set[int] = set()
    selectors = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "table"]
    for tag in root.find_all(selectors):
        if id(tag) in seen:
            continue
        if tag.find_parent(["table"]) and tag.name != "table":
            continue
        body = _clean_html_text(tag.get_text("\n" if tag.name in {"table", "pre"} else " ", strip=True))
        if not body:
            continue
        if tag.name and re.fullmatch(r"h[1-6]", tag.name):
            level = int(tag.name[1])
            headings_by_level = {k: v for k, v in headings_by_level.items() if k < level}
            headings_by_level[level] = body
            block_type = "heading"
            indivisible = False
        elif tag.name == "table":
            block_type = "table"
            indivisible = True
        elif tag.name == "pre":
            block_type = "code"
            indivisible = True
        elif tag.name == "li":
            block_type = "list_item"
            indivisible = False
        else:
            block_type = "paragraph"
            indivisible = False
        blocks.append(
            Block(
                id=f"b{order:04d}",
                type=block_type,
                text=body,
                heading_path=[headings_by_level[k] for k in sorted(headings_by_level)],
                source=SourceSpan(
                    mapped=False,
                    note=f"HTML parsed as inert text; original line/span unmapped; dom_path={_dom_path(tag)}",
                ),
                order=order,
                indivisible=indivisible,
                flags=["html_unmapped_source"],
            )
        )
        seen.add(id(tag))
        order += 1
    return blocks
