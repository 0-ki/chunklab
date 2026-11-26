from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from chunklab.benchmark import run_synthetic_benchmark


def test_synthetic_benchmark_is_offline_reproducible_and_bilingual() -> None:
    report = run_synthetic_benchmark(retrieval_budget=1_200, hard_limit=420, guided_request_budget=32)

    assert report["document_count"] == 2
    assert report["query_count"] == 5
    assert report["budget"]["mode"] == "utf8_bytes"
    assert "not a tokenizer/model token count" in report["budget"]["label"]
    assert "offline mock only" in report["provider_comparisons"]
    assert report["holdout"]["benchmark"] == "chunklab.heldout_ko_ecommerce_act_20260721.v1.0.0"
    assert report["holdout"]["separate_from_development_corpus"] is True
    assert report["holdout"]["do_not_tune_on_this_result"] is True
    assert report["holdout"]["not_legal_advice"] is True
    assert report["holdout"]["query_count"] == 1
    assert report["holdout"]["conditions"]["structural_screening_off"]["total_evidence_span_count"] == 3
    assert report["holdout"]["conditions"]["structural_screening_off"]["ground_truth_evidence_found_under_budget"] == 3
    assert {"en", "ko"} == {query["language"] for query in report["queries"]}

    for condition in (
        "structural_screening_off",
        "structural_screening_on",
        "offline_mock_guided_on_cleaned",
    ):
        metrics = report["conditions"][condition]
        assert metrics["document_count"] == 2
        assert metrics["query_count"] == 5
        assert metrics["total_evidence_span_count"] == 7
        assert metrics["ground_truth_evidence_retained_in_index"] == 7
        assert metrics["ground_truth_evidence_found_under_budget"] == 7
        assert metrics["full_answer_evidence_found_under_budget"] == 5
        assert metrics["evidence_span_recall_under_budget"] == 1.0
        assert metrics["complete_multi_span_recall"] == 1.0
        assert metrics["processing_latency_ms"] >= 0

    assert report["conditions"]["offline_mock_guided_on_cleaned"]["request_count"] > 0
    assert report["conditions"]["structural_screening_off"]["request_count"] == 0
    assert report["conditions"]["structural_screening_on"]["request_count"] == 0
    assert report["conditions"]["structural_screening_on"]["screening"]["ko-returns.md"]["removed_blocks"] == 1
    assert report["conditions"]["structural_screening_on"]["screening"]["en-returns.md"]["removed_blocks"] == 1


def test_synthetic_benchmark_cli_outputs_json() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "chunklab.benchmark"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["benchmark"] == "chunklab.synthetic_ko_en.v1.0.0"
    assert payload["development_benchmark"] == "chunklab.synthetic_ko_en.v0.5"
    assert payload["holdout"]["frozen_ranked_query"] is True
    assert payload["instructions"]["en"]
    assert payload["instructions"]["ko"]


def test_app_entry_point_loads_with_apptest() -> None:
    app_path = Path(__file__).resolve().parents[1] / "chunklab" / "app.py"
    app = AppTest.from_file(app_path)
    app.run()
    assert not app.exception
    assert app.title[0].value.startswith("ChunkLab")
