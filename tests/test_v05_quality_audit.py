from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from chunklab.audit import QualityAuditConfig, audit_chunks, parse_taxonomy_lines
from chunklab.benchmark import _evidence_text_covered, _retrieve, run_synthetic_benchmark
from chunklab.export import chunks_to_jsonl, process_upload
from chunklab.models import Chunk, SourceSpan
from chunklab.token_budget import Utf8ByteBudget


def test_quality_audit_adds_explainable_flags_without_dropping_or_rewriting_text() -> None:
    source = "# A\n\nOK\n\n# Return policy\n\nHowever, it is excluded unless support approves it.\n"
    doc, chunks, issues = process_upload("audit.md", source.encode("utf-8"), hard_limit=500)
    assert not issues
    original_texts = [chunk.text for chunk in chunks]

    audited = audit_chunks(chunks)
    assert [chunk.text for chunk in audited] == original_texts
    assert len(audited) == len(chunks)
    assert any("low_information" in chunk.flags for chunk in audited)
    assert all("quality" in chunk.audit for chunk in audited)
    payloads = [json.loads(line) for line in chunks_to_jsonl(doc, audited).splitlines()]
    assert any(record["audit"]["quality"]["low_information"]["score_provenance"].startswith("rule:") for record in payloads)
    assert any(record["audit"]["quality"]["reasons"] for record in payloads)


def test_quality_taxonomy_is_user_configurable_bilingual_and_has_explicit_unknown() -> None:
    taxonomy = parse_taxonomy_lines("custom_returns: 반품, return\nsupport: 문의, help\nunknown: ignored\n")
    chunks = [
        Chunk("c0000", 0, "반품 대상 안내", [], SourceSpan(), ["b0000"], ["paragraph"], 20),
        Chunk("c0001", 1, "Plain unrelated sentence with enough words.", [], SourceSpan(), ["b0001"], ["paragraph"], 42),
    ]
    audited = audit_chunks(chunks, QualityAuditConfig(taxonomy=taxonomy))
    assert audited[0].audit["quality"]["taxonomy"]["labels"] == ["custom_returns"]
    assert audited[1].audit["quality"]["taxonomy"]["labels"] == ["unknown"]
    assert audited[1].audit["quality"]["taxonomy"]["unknown"] is True


def test_self_contained_audit_is_conservative_and_explainable() -> None:
    chunks = [
        Chunk("c0000", 0, "However, this depends on the previous answer.", [], SourceSpan(), ["b0000"], ["paragraph"], 45),
        Chunk("c0001", 1, "단, 이전 조건에 따라 달라집니다.", [], SourceSpan(), ["b0001"], ["paragraph"], 45),
    ]
    audited = audit_chunks(chunks)
    assert all(chunk.audit["quality"]["self_contained"]["value"] is False for chunk in audited)
    assert all("self_contained" in chunk.flags for chunk in audited)
    assert all(chunk.audit["quality"]["self_contained"]["score_provenance"].startswith("rule:") for chunk in audited)


def test_quality_audit_does_not_affect_ranking_or_original_text() -> None:
    budget = Utf8ByteBudget()
    chunk = Chunk(
        "c0000",
        0,
        "Customers may request a return within 14 days.",
        ["Return policy"],
        SourceSpan(),
        ["b0001"],
        ["paragraph"],
        43,
    )
    indexed = {"en.md": [chunk]}
    audited_indexed = {"en.md": audit_chunks([chunk])}
    before = _retrieve("return within 14 days", indexed, retrieval_budget=500, budget=budget)
    after = _retrieve("return within 14 days", audited_indexed, retrieval_budget=500, budget=budget)
    assert before == after
    assert audited_indexed["en.md"][0].text == chunk.text


def test_benchmark_uses_span_denominator_and_split_evidence_text_coverage() -> None:
    report = run_synthetic_benchmark(retrieval_budget=2_000, hard_limit=80, guided_request_budget=32)
    metrics = report["conditions"]["structural_screening_off"]
    assert metrics["total_evidence_span_count"] == 7
    assert metrics["ground_truth_evidence_retained_in_index"] == 7
    assert metrics["full_answer_evidence_retained_in_index"] == 5
    split_rows = [
        item
        for item in metrics["queries"]
        if item["evidence_span_count"] > 1
    ]
    assert split_rows
    assert all(item["evidence_retained_in_index"] for item in split_rows)


def test_split_child_id_prefix_alone_is_not_full_evidence_coverage() -> None:
    assert not _evidence_text_covered("Alpha Beta Gamma", ["Alpha"])
    assert _evidence_text_covered("Alpha Beta Gamma", ["Alpha ", "Beta ", "Gamma"])


def test_app_v05_quality_audit_gui_is_opt_in_and_exports_metadata() -> None:
    app_path = Path(__file__).resolve().parents[1] / "chunklab" / "app.py"
    app = AppTest.from_file(app_path)
    app.run()
    assert not app.exception
    assert any("v0.5 선택형 품질 감사" in expander.label for expander in app.expander)
    assert any("청크 품질 감사 활성화" == checkbox.label for checkbox in app.checkbox)

    app.file_uploader[0].upload("audit.md", b"# A\n\nOK\n", "text/markdown").run()
    app.checkbox[0].check().run()
    assert not app.exception
    assert any("품질 감사" in info.value for info in app.info)
