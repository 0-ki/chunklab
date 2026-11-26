# ChunkLab roadmap / 로드맵

## 1.0.0 status / 1.0.0 상태

- Stable offline mode is the release scope: local Markdown/HTML/TXT upload, deterministic structural chunking, opt-in deterministic pre-screen/review/restore, opt-in quality audit, provenance preview, JSONL/issue export, offline mock-guided comparison, and installed CLI use outside a checkout.
- 안정 범위는 로컬 Markdown/HTML/TXT 업로드, 결정론적 구조 청킹, opt-in 결정론적 사전 검사/검토/복원, opt-in 품질 감사, provenance preview, JSONL/issue export, 오프라인 mock-guided 비교, checkout 밖 installed CLI 사용입니다.
- All provider paths remain experimental and opt-in. No real provider calls were made for v1.0.0, and no live provider behavior is claimed verified.
- 모든 provider 경로는 실험적이며 opt-in입니다. v1.0.0에서 실제 provider 호출은 하지 않았고 live provider 동작 검증을 주장하지 않습니다.
- Independently tested release evidence is Linux/Python 3.12 only: no-network local-wheelhouse install of the full archive with `.[test]`, `pip check` pass, 65 tests pass, and installed CLI health outside the checkout.
- 독립 테스트 근거는 Linux/Python 3.12 only입니다. Full archive `.[test]` no-network local-wheelhouse 설치, `pip check` 통과, 65 tests 통과, checkout 밖 installed CLI health 확인입니다.

## Completed for 1.0.0 / 1.0.0 완료

- v0.2 boundary comparison: offline structural baseline, opt-in provider comparison path, hard caps, provenance, explicit abstention/error/fallback states, Korean/English tests and quickstarts.
- v0.3 review and classification: deterministic boilerplate screening, quarantine/manual restore, OpenRouter Jev adapter contract tests, no automatic vendor routing.
- v0.5 audit-first quality flags: deterministic local audit with explicit provenance; audit flags do not rewrite text, alter ranking, or silently drop chunks.
- v0.6 experimental live-adapter hardening: OpenAI Chat Completions A/B logprobs path, localhost launcher hardening, protected Streamlit settings, no guessed missing probability, no provider-common threshold.
- v1.0 packaging/docs: MIT license, bilingual README/release notes, dependency notices, Python `>=3.11`, package path curation, measured offline benchmark results and limitations.

## Deferred / 이후로 미룸

- Full boundary optimization and DP search beyond current deterministic structural/offline mock comparison.
- Delimiter-specific chunking features beyond current Markdown/HTML/TXT structural parsing.
- Graph features, hierarchical summaries, vector databases, and retrieval pipeline integrations.
- URL fetching, PDF/OCR, deployment recipes, live-provider validation, and automatic live provider calls.
- Larger validation sets and production retrieval-quality claims.

## Research references / 연구 참고

- OpenRouter Jev remains pinned to `typesafe/jev-1.13` for the experimental adapter. Jev 1.14 documentation is not used as this adapter's contract.
- The upstream Jev/RAG implementation is referenced as inspiration for paragraph verification, query scoring, boundary decisions, and tagging. ChunkLab does not claim to reproduce that research or validate live Jev behavior.
