from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from chunklab.app import _source_preview
from chunklab.export import chunks_to_jsonl, process_upload
from chunklab.parsers import parse_html, parse_markdown


def test_markdown_korean_headings_and_limit() -> None:
    source = """# 안내

한국어 문단입니다. 검색 근거를 보존합니다.

## 세부

짧은 설명입니다.
"""
    doc, chunks, issues = process_upload("sample.md", source.encode("utf-8"), hard_limit=120)
    assert not issues
    assert chunks
    assert all(chunk.budget_count <= 120 for chunk in chunks)
    assert any("안내" in chunk.heading_path for chunk in chunks)
    assert any(chunk.source.mapped for chunk in chunks)


def test_markdown_code_indivisible_oversized_flagged_not_exported() -> None:
    source = "# Dev\n\n```python\n" + ("print('긴 코드')\n" * 20) + "```\n\n다음 문단\n"
    doc, chunks, issues = process_upload("code.md", source.encode("utf-8"), hard_limit=80)
    assert issues
    assert issues[0].block_type == "code"
    assert "excluded from JSONL" in issues[0].message
    assert all(chunk.budget_count <= 80 for chunk in chunks)
    assert "긴 코드" not in chunks_to_jsonl(doc, chunks)


def test_html_is_inert_and_unmapped() -> None:
    html = """<html><body><h1>제목</h1><script>window.evil = true</script><p>본문</p></body></html>"""
    blocks = parse_html(html)
    text = "\n".join(block.text for block in blocks)
    assert "제목" in text
    assert "본문" in text
    assert "window.evil" not in text
    assert all(not block.source.mapped for block in blocks)
    assert all("html_unmapped_source" in block.flags for block in blocks)


def test_jsonl_schema_and_source_span() -> None:
    source = "# H\n\nAlpha\n\nBeta\n"
    doc, chunks, issues = process_upload("a.md", source.encode("utf-8"), hard_limit=50)
    assert not issues
    payload = chunks_to_jsonl(doc, chunks)
    records = [json.loads(line) for line in payload.splitlines()]
    assert records
    first = records[0]
    assert first["schema"] == "chunklab.offline.v1"
    assert first["document"]["filename"] == "a.md"
    assert first["budget"]["mode"] == "utf8_bytes"
    assert first["source"]["mapped"] is True
    assert first["source"]["line_start"] >= 1


def test_markdown_table_oversized_is_issue() -> None:
    source = "# T\n\n| A | B |\n|---|---|\n" + "\n".join(f"| {i} | {'x' * 20} |" for i in range(10))
    blocks = parse_markdown(source)
    assert any(block.type == "table" and block.indivisible for block in blocks)
    doc, chunks, issues = process_upload("table.md", source.encode("utf-8"), hard_limit=100)
    assert any(issue.block_type == "table" for issue in issues)
    assert all(chunk.budget_count <= 100 for chunk in chunks)


def test_markdown_does_not_cross_top_level_heading_boundary() -> None:
    source = "# A\n\nAlpha\n\n# B\n\nBeta\n"
    doc, chunks, issues = process_upload("headings.md", source.encode("utf-8"), hard_limit=400)
    assert not issues
    assert [chunk.heading_path for chunk in chunks] == [["A"], ["B"]]
    assert chunks[0].text == "# A\n\nAlpha"
    assert chunks[1].text == "# B\n\nBeta"


def test_heading_nesting_with_skipped_levels() -> None:
    blocks = parse_markdown("# A\n\n### C\n\nc\n\n## B\n\nb\n")
    paragraphs = [block for block in blocks if block.type == "paragraph"]
    assert paragraphs[0].heading_path == ["A", "C"]
    assert paragraphs[1].heading_path == ["A", "B"]


def test_korean_long_txt_split_has_line_only_provenance() -> None:
    source = "가나다라" * 40
    doc, chunks, issues = process_upload("long.txt", source.encode("utf-8"), hard_limit=32)
    assert not issues
    assert chunks
    assert all(chunk.budget_count <= 32 for chunk in chunks)
    assert all(chunk.source.mapped for chunk in chunks)
    assert all(chunk.source.line_start == 1 and chunk.source.line_end == 1 for chunk in chunks)
    assert all(chunk.source.span_start is None and chunk.source.span_end is None for chunk in chunks)
    assert all("Line-only provenance" in (chunk.source.note or "") for chunk in chunks)


def test_html_dom_note_survives_chunk_merge_and_preview() -> None:
    doc, chunks, issues = process_upload(
        "sample.html",
        b"<html><body><h1>Title</h1><p>Body</p></body></html>",
        hard_limit=400,
    )
    assert not issues
    assert chunks
    assert chunks[0].source.mapped is False
    assert "dom_path=" in (chunks[0].source.note or "")
    assert "dom_path=" in _source_preview(doc.text, chunks[0].source.line_start, chunks[0].source.line_end) + (
        chunks[0].source.note or ""
    )


def test_empty_and_unsupported_inputs_are_readable_errors() -> None:
    with pytest.raises(ValueError, match="텍스트를 찾지 못했습니다"):
        process_upload("empty.txt", b"", hard_limit=100)
    with pytest.raises(ValueError, match="지원하지 않는 파일 형식"):
        process_upload("file.pdf", b"hello", hard_limit=100)


@pytest.mark.parametrize(
    ("filename", "content", "mime"),
    [
        ("real.md", b"# A\n\nAlpha\n", "text/markdown"),
        ("real.html", b"<html><body><h1>A</h1><p>Alpha</p></body></html>", "text/html"),
        ("real.txt", "Alpha\n\nBeta\n".encode("utf-8"), "text/plain"),
    ],
)
def test_app_upload_widget_accepts_real_filenames(filename: str, content: bytes, mime: str) -> None:
    app_path = Path(__file__).resolve().parents[1] / "chunklab" / "app.py"
    app = AppTest.from_file(app_path)
    app.run()
    app.file_uploader[0].upload(filename, content, mime).run()
    assert not app.exception
    assert app.download_button
    assert any(button.label == "JSONL 다운로드" for button in app.download_button)
