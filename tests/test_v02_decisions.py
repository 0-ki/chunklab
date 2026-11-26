from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from chunklab.decisions import (
    DecisionRequest,
    DecisionResponse,
    OpenAIDecisionsProvider,
    PredicateAnswer,
    PredicateQuestion,
)
from chunklab.guided import GuidedChunkConfig, _boundary_input, compare_model_guided_boundaries
from chunklab.parsers import parse_markdown
from chunklab.token_budget import Utf8ByteBudget


class AbstainingProvider:
    name = "abstain"

    def decide(self, request: DecisionRequest, *, timeout_s: float) -> DecisionResponse:
        del request, timeout_s
        return DecisionResponse(status="refusal", model="fixture", message="fixture refusal")


class CuttingProvider:
    name = "cutting"

    def decide(self, request: DecisionRequest, *, timeout_s: float) -> DecisionResponse:
        del request, timeout_s
        return DecisionResponse(
            status="ok",
            model="fixture",
            answers={
                "continues": PredicateAnswer(
                    name="continues",
                    probability=0.05,
                    score_kind="provider_probability",
                ),
                "refers_back": PredicateAnswer(
                    name="refers_back",
                    probability=0.05,
                    score_kind="provider_probability",
                )
            },
        )


class ProbabilityProvider:
    name = "probability"

    def __init__(self, probability: float) -> None:
        self.probability = probability

    def decide(self, request: DecisionRequest, *, timeout_s: float) -> DecisionResponse:
        del request, timeout_s
        return DecisionResponse(
            status="ok",
            model="fixture",
            answers={
                "continues": PredicateAnswer(
                    name="continues",
                    probability=self.probability,
                    score_kind="provider_probability",
                ),
                "refers_back": PredicateAnswer(
                    name="refers_back",
                    probability=self.probability,
                    score_kind="provider_probability",
                )
            },
        )


class FailingOnceProvider:
    name = "failing"

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, request: DecisionRequest, *, timeout_s: float) -> DecisionResponse:
        del request, timeout_s
        self.calls += 1
        return DecisionResponse(status="error", model="fixture", message="fixture systemic failure")


def test_guided_refusal_falls_back_to_structural() -> None:
    blocks = parse_markdown("# H\n\nAlpha paragraph.\n\nBeta paragraph.\n")
    result = compare_model_guided_boundaries(
        blocks,
        hard_limit=500,
        provider=AbstainingProvider(),
        config=GuidedChunkConfig(max_requests=4),
    )
    assert result.degraded is True
    assert result.guided_chunks == result.structural_chunks
    assert result.decisions[0].status == "abstain"
    assert result.decisions[0].provider_status == "refusal"


def test_guided_cut_adds_in_section_boundary_but_not_heading_override() -> None:
    blocks = parse_markdown("# A\n\nAlpha.\n\nBeta.\n\n# B\n\nGamma.\n\nDelta.\n")
    result = compare_model_guided_boundaries(
        blocks,
        hard_limit=1_000,
        provider=CuttingProvider(),
        config=GuidedChunkConfig(max_requests=10),
    )
    assert [chunk.heading_path for chunk in result.structural_chunks] == [["A"], ["B"]]
    assert len(result.guided_chunks) == 4
    assert all(chunk.budget_count <= 1_000 for chunk in result.guided_chunks)
    assert {tuple(chunk.heading_path) for chunk in result.guided_chunks} == {("A",), ("B",)}


def test_guided_requires_two_independent_predicates_and_abstains_on_missing() -> None:
    blocks = parse_markdown("# H\n\nAlpha.\n\nBeta.\n")

    class MissingRefersBackProvider:
        name = "missing"

        def decide(self, request: DecisionRequest, *, timeout_s: float) -> DecisionResponse:
            del request, timeout_s
            return DecisionResponse(
                status="ok",
                model="fixture",
                answers={
                    "continues": PredicateAnswer(
                        name="continues",
                        probability=0.05,
                        score_kind="provider_probability",
                    )
                },
            )

    result = compare_model_guided_boundaries(
        blocks,
        hard_limit=500,
        provider=MissingRefersBackProvider(),
        config=GuidedChunkConfig(max_requests=2),
    )
    assert result.decisions[0].status == "abstain"
    assert result.degraded is True
    assert result.guided_chunks == result.structural_chunks


def test_openai_decisions_adapter_schema_with_mock_transport(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def transport(req, timeout_s: float):
        captured["url"] = req.full_url
        captured["timeout"] = timeout_s
        captured["authorization"] = req.get_header("Authorization")
        body = req.data.decode("utf-8")
        captured["body"] = json.loads(body)
        assert "secret-fixture-key" not in body
        payload = {
            "model": "gpt-6-luna",
            "answers": [{"type": "predicate", "name": "should_cut_here", "probability": 0.84}],
            "usage": {"input_units": 123},
        }
        return 200, json.dumps(payload).encode("utf-8")

    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")
    provider = OpenAIDecisionsProvider(transport=transport)
    response = provider.decide(
        DecisionRequest(
            input="untrusted evidence",
            questions=(PredicateQuestion(name="should_cut_here", instructions="fixed instruction"),),
        ),
        timeout_s=3.5,
    )
    assert captured["url"] == "https://api.openai.com/v1/decisions"
    assert captured["authorization"] == "Bearer secret-fixture-key"
    assert captured["timeout"] == 3.5
    assert captured["body"] == {
        "model": "gpt-6-luna",
        "input": "untrusted evidence",
        "questions": [{"name": "should_cut_here", "type": "predicate", "instructions": "fixed instruction"}],
    }
    assert response.status == "ok"
    assert response.probability("should_cut_here") == 0.84
    assert response.usage["input_units"] == 123


@pytest.mark.parametrize(
    "answer",
    [
        {"type": "predicate", "name": "should_cut_here", "probability": True},
        {"type": "predicate", "name": "should_cut_here", "probability": -0.01},
        {"type": "predicate", "name": "should_cut_here", "probability": 1.01},
        {"type": "predicate", "name": "should_cut_here", "probability": float("nan")},
    ],
)
def test_openai_rejects_invalid_predicate_probability(monkeypatch, answer: dict[str, object]) -> None:
    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")

    def transport(req, timeout_s: float):
        del req, timeout_s
        return 200, json.dumps({"answers": [answer]}).encode("utf-8")

    response = OpenAIDecisionsProvider(transport=transport).decide(
        DecisionRequest(
            input="evidence",
            questions=(PredicateQuestion(name="should_cut_here", instructions="fixed"),),
        ),
        timeout_s=1,
    )
    assert response.status == "error"
    assert "secret-fixture-key" not in (response.message or "")
    assert "https://api.openai.com" not in (response.message or "")


def test_openai_named_refusal_is_refusal_not_missing(monkeypatch) -> None:
    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")

    def transport(req, timeout_s: float):
        del req, timeout_s
        return 200, json.dumps({"answers": [{"name": "should_cut_here", "refusal": "no"}]}).encode("utf-8")

    response = OpenAIDecisionsProvider(transport=transport).decide(
        DecisionRequest(
            input="evidence",
            questions=(PredicateQuestion(name="should_cut_here", instructions="fixed"),),
        ),
        timeout_s=1,
    )
    assert response.status == "refusal"
    assert "Missing" not in (response.message or "")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"answers": "not-list"},
        {"answers": [{"type": "predicate", "probability": 0.5}]},
        {
            "answers": [
                {"type": "predicate", "name": "should_cut_here", "probability": 0.5},
                {"type": "predicate", "name": "should_cut_here", "probability": 0.6},
            ]
        },
        {"status": "in_progress", "answers": [{"type": "predicate", "name": "should_cut_here", "probability": 0.5}]},
    ],
)
def test_openai_malformed_shapes_fail_closed_without_leak(monkeypatch, payload: object) -> None:
    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")

    def transport(req, timeout_s: float):
        del req, timeout_s
        return 200, json.dumps(payload).encode("utf-8")

    response = OpenAIDecisionsProvider(transport=transport).decide(
        DecisionRequest(
            input="evidence",
            questions=(PredicateQuestion(name="should_cut_here", instructions="fixed"),),
        ),
        timeout_s=1,
    )
    assert response.status == "error"
    message = response.message or ""
    assert "secret-fixture-key" not in message
    assert "api.openai.com" not in message
    assert "evidence" not in message


def test_openai_http_and_malformed_network_fail_closed_without_leak(monkeypatch) -> None:
    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")

    def http_error_transport(req, timeout_s: float):
        del timeout_s
        raise urllib.error.HTTPError(req.full_url, 500, "server leaked raw body", {}, None)

    response = OpenAIDecisionsProvider(transport=http_error_transport).decide(
        DecisionRequest(input="evidence", questions=(PredicateQuestion(name="should_cut_here", instructions="fixed"),)),
        timeout_s=1,
    )
    assert response.status == "error"
    assert response.message == "HTTP error 500"

    def malformed_transport(req, timeout_s: float):
        del req, timeout_s
        return 200, b"{raw response"

    response = OpenAIDecisionsProvider(transport=malformed_transport).decide(
        DecisionRequest(input="evidence", questions=(PredicateQuestion(name="should_cut_here", instructions="fixed"),)),
        timeout_s=1,
    )
    assert response.status == "error"
    assert response.message == "Malformed provider response."


def test_openai_endpoint_must_be_https(monkeypatch) -> None:
    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAIDecisionsProvider(endpoint="http://api.openai.com/v1/decisions", transport=lambda req, timeout_s: (200, b"{}"))


def test_low_probability_keeps_middle_abstains_and_systemic_failure_stops() -> None:
    blocks = parse_markdown("# H\n\nAlpha.\n\nBeta.\n\nGamma.\n")
    low = compare_model_guided_boundaries(
        blocks,
        hard_limit=1_000,
        provider=ProbabilityProvider(0.05),
        config=GuidedChunkConfig(max_requests=2),
    )
    assert low.decisions[0].status == "cut"
    assert low.degraded is False

    middle = compare_model_guided_boundaries(
        blocks,
        hard_limit=1_000,
        provider=ProbabilityProvider(0.5),
        config=GuidedChunkConfig(max_requests=2),
    )
    assert middle.decisions[0].status == "abstain"
    assert middle.degraded is True

    failing = FailingOnceProvider()
    failed = compare_model_guided_boundaries(
        blocks,
        hard_limit=1_000,
        provider=failing,
        config=GuidedChunkConfig(max_requests=2),
    )
    assert failing.calls == 1
    assert failed.request_count == 1
    assert failed.degraded is True


def test_boundary_input_cap_includes_heading_and_marker() -> None:
    blocks = parse_markdown("# " + ("긴제목" * 40) + "\n\n" + ("A" * 500) + "\n\n" + ("B" * 500) + "\n")
    text = _boundary_input(
        blocks[1],
        blocks[2],
        budget=Utf8ByteBudget(),
        config=GuidedChunkConfig(max_serialized_input_units=220, context_units_per_side=200),
    )
    assert len(text.encode("utf-8")) <= 220
    assert "truncated to bounded input" in text


def test_app_model_comparison_is_opt_in_and_warned() -> None:
    app_path = Path(__file__).resolve().parents[1] / "chunklab" / "app.py"
    app = AppTest.from_file(app_path)
    app.run()
    app.file_uploader[0].upload("real.md", b"# A\n\nAlpha\n\nBeta\n", "text/markdown").run()
    assert not app.exception
    assert any("v0.2 선택형 모델 경계 비교" in expander.label for expander in app.expander)
    assert any("명시적 비교 실행" == button.label for button in app.button)
    assert any("선택형 경계 비교 활성화" == checkbox.label for checkbox in app.checkbox)
