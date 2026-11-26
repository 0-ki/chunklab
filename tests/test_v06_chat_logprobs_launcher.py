from __future__ import annotations

import json
import sys

import pytest

from chunklab import app as chunklab_app
from chunklab.decisions import DecisionRequest, OpenAIChatLogprobsProvider, PredicateQuestion


def _chat_payload(*, content: str = "A", a_logprob: float = -0.2, b_logprob: float = -1.6, finish_reason: str = "stop"):
    return {
        "model": "gpt-4.1-mini",
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"content": content},
                "logprobs": {
                    "content": [
                        {
                            "token": content,
                            "logprob": a_logprob if content == "A" else b_logprob,
                            "bytes": [ord(content)],
                            "top_logprobs": [
                                {"token": "A", "logprob": a_logprob, "bytes": [65]},
                                {"token": "B", "logprob": b_logprob, "bytes": [66]},
                            ],
                        }
                    ]
                },
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 1},
    }


def test_openai_chat_logprobs_adapter_schema_and_relative_token_proxy(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    def transport(req, timeout_s: float):
        captured.append(
            {
                "url": req.full_url,
                "timeout": timeout_s,
                "authorization": req.get_header("Authorization"),
                "body": json.loads(req.data.decode("utf-8")),
            }
        )
        assert "secret-fixture-key" not in req.data.decode("utf-8")
        if len(captured) == 1:
            return 200, json.dumps(_chat_payload(content="A", a_logprob=-0.1, b_logprob=-2.1)).encode("utf-8")
        return 200, json.dumps(_chat_payload(content="B", a_logprob=-1.7, b_logprob=-0.2)).encode("utf-8")

    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")
    response = OpenAIChatLogprobsProvider(transport=transport).decide(
        DecisionRequest(
            input="untrusted evidence",
            questions=(
                PredicateQuestion(name="continues", instructions="fixed one"),
                PredicateQuestion(name="refers_back", instructions="fixed two"),
            ),
        ),
        timeout_s=3.5,
    )

    assert [item["url"] for item in captured] == [
        "https://api.openai.com/v1/chat/completions",
        "https://api.openai.com/v1/chat/completions",
    ]
    assert all(item["authorization"] == "Bearer secret-fixture-key" for item in captured)
    assert all(item["timeout"] == 3.5 for item in captured)
    first_body = captured[0]["body"]
    assert first_body["logprobs"] is True
    assert first_body["top_logprobs"] == 20
    assert first_body["max_completion_tokens"] == 4
    assert "max_tokens" not in first_body
    assert response.status == "ok"
    assert response.answers["continues"].score_kind == "relative_token_proxy"
    assert response.probability("continues") == pytest.approx(0.880797, rel=1e-5)
    assert response.probability("refers_back") == pytest.approx(0.182426, rel=1e-5)
    assert response.usage["chat_completion_requests"] == 2
    assert response.usage["prompt_tokens"] == 22


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        (_chat_payload(finish_reason="length"), "missing"),
        (
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "A"},
                        "logprobs": {
                            "content": [
                                {
                                    "token": "A",
                                    "logprob": -0.1,
                                    "bytes": [65],
                                    "top_logprobs": [{"token": "A", "logprob": -0.1, "bytes": [65]}],
                                }
                            ]
                        },
                    }
                ]
            },
            "missing",
        ),
        (
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "A"},
                        "logprobs": {
                            "content": [
                                {
                                    "token": "A",
                                    "logprob": -0.1,
                                    "bytes": [66],
                                    "top_logprobs": [
                                        {"token": "A", "logprob": -0.1, "bytes": [65]},
                                        {"token": "B", "logprob": -1.0, "bytes": [66]},
                                    ],
                                }
                            ]
                        },
                    }
                ]
            },
            "error",
        ),
        (
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "A"},
                        "logprobs": {
                            "content": [
                                {
                                    "token": "A",
                                    "logprob": -0.1,
                                    "bytes": [65],
                                    "top_logprobs": [
                                        {"token": "A", "logprob": -0.1, "bytes": [65]},
                                        {"token": "A", "logprob": -0.2, "bytes": [65]},
                                        {"token": "B", "logprob": -1.0, "bytes": [66]},
                                    ],
                                }
                            ]
                        },
                    }
                ]
            },
            "error",
        ),
        (_chat_payload(a_logprob=-9999.0, b_logprob=-1.0), "error"),
        ({"choices": [{"finish_reason": "stop", "message": {"refusal": "cannot comply"}}]}, "refusal"),
    ],
)
def test_openai_chat_logprobs_distinguishes_missing_refusal_and_failures(monkeypatch, payload: object, status: str) -> None:
    monkeypatch.setenv("CHUNKLAB_OPENAI_API_KEY", "secret-fixture-key")

    def transport(req, timeout_s: float):
        del req, timeout_s
        return 200, json.dumps(payload).encode("utf-8")

    response = OpenAIChatLogprobsProvider(transport=transport).decide(
        DecisionRequest(input="evidence", questions=(PredicateQuestion(name="continues", instructions="fixed"),)),
        timeout_s=1,
    )
    assert response.status == status
    assert "secret-fixture-key" not in (response.message or "")
    assert "evidence" not in (response.message or "")


def test_console_launcher_binds_localhost_disables_telemetry_and_keeps_port_headless(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_main() -> int:
        captured["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr(chunklab_app.stcli, "main", fake_main)
    monkeypatch.setattr(sys, "argv", ["chunklab", "--server.port=9876", "--server.headless", "true"])

    with pytest.raises(SystemExit):
        chunklab_app.cli()

    assert "--server.address=localhost" in captured["argv"]
    assert "--browser.gatherUsageStats=false" in captured["argv"]
    assert "--server.port=9876" in captured["argv"]
    assert "--server.headless" in captured["argv"]


@pytest.mark.parametrize(
    "args",
    [
        ["--server.address=0.0.0.0"],
        ["--server.address", "0.0.0.0"],
        ["--browser.gatherUsageStats=true"],
        ["--browser.gatherUsageStats", "true"],
    ],
)
def test_console_launcher_rejects_protected_config_overrides(monkeypatch, args: list[str]) -> None:
    def fail_main() -> int:
        raise AssertionError("streamlit main should not run")

    monkeypatch.setattr(chunklab_app.stcli, "main", fail_main)
    monkeypatch.setattr(sys, "argv", ["chunklab", *args])

    with pytest.raises(SystemExit) as exc:
        chunklab_app.cli()

    assert "protects" in str(exc.value)
