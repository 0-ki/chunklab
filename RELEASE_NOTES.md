# ChunkLab release notes

## 1.0.0

ChunkLab 1.0.0 finalizes the tested local/offline release scope. It was not published, signed, committed, or pushed by this release-prep pass, and no live provider calls were made.

ChunkLab 1.0.0은 테스트된 로컬·오프라인 릴리스 범위를 확정합니다. 이 릴리스 준비 과정에서는 publish, signing, commit, push를 수행하지 않았고 live provider 호출도 하지 않았습니다.

### English

#### Included

- Package and runtime version set to `1.0.0`.
- Python requirement corrected to `>=3.11` because the verified Streamlit 1.67 wheel requires Python 3.11 or newer.
- POSIX and Windows PowerShell quickstarts documented.
- MIT license and third-party notices retained.
- Packaging manifest keeps publishable source/docs/license paths and excludes virtual environments, build outputs, caches, generated metadata, logs, JSONL exports, credentials, tokens, and secret-named files.
- Stable offline scope: local Markdown/HTML/TXT upload, structural chunking, opt-in deterministic pre-screen/review/restore, opt-in quality audit, provenance preview, JSONL/issue export, offline mock-guided comparison, and installed CLI use outside a checkout.
- Experimental scope: all OpenAI/OpenRouter provider paths and provider-derived boundary comparisons remain opt-in and mock-tested only.

#### Independent test evidence

- Independently tested on Linux with Python 3.12 only.
- Fresh isolated Python 3.12 virtual environment installed the full archive with `.[test]` from a local wheelhouse with no network access.
- `pip check` passed.
- 65 tests passed.
- The installed `chunklab` CLI health check passed outside the checkout.

#### Measured offline benchmark results

- Development Korean/English synthetic benchmark: 5/5 full-answer evidence retrieval in each condition.
- Held-out Korean legal-paraphrase benchmark: all 3 required evidence spans found in each condition.
- Conditions used the same deterministic lexical ranker and UTF-8 byte budget.
- No split-quality gain was established for screening or offline mock-guided chunking on these small fixtures.

#### Limits and deferred work

- No production retrieval-quality claim.
- No legal advice; the held-out Korean law case is ChunkLab-authored paraphrase, not copied statutory text.
- No live provider validation; provider schemas/behavior against real network APIs remain unverified.
- URL fetching, PDF/OCR, deployment, automatic live provider calls, full boundary optimization, delimiter-specific chunking, graph features, hierarchical summaries, vector databases, and retrieval pipeline integrations are deferred.
- The upstream Jev/RAG research implementation is referenced as inspiration for paragraph verification, query scoring, boundary decisions, and tagging, without claiming reproduction or live Jev validation.

### 한국어

#### 포함 사항

- Package 및 runtime version을 `1.0.0`으로 설정했습니다.
- 검증된 Streamlit 1.67 wheel이 Python 3.11 이상을 요구하므로 Python 요구사항을 `>=3.11`로 바로잡았습니다.
- POSIX와 Windows PowerShell 빠른 시작을 문서화했습니다.
- MIT license와 third-party notice를 유지했습니다.
- Packaging manifest는 공개 가능한 source/docs/license 경로를 유지하고 virtual environment, build output, cache, generated metadata, log, JSONL export, credential, token, secret 이름 파일을 제외합니다.
- 안정 오프라인 범위: 로컬 Markdown/HTML/TXT 업로드, 구조 청킹, opt-in 결정론적 사전 검사/검토/복원, opt-in 품질 감사, provenance preview, JSONL/issue export, 오프라인 mock-guided 비교, checkout 밖 installed CLI 사용.
- 실험 범위: 모든 OpenAI/OpenRouter provider 경로와 provider-derived 경계 비교는 opt-in이며 mock-tested only입니다.

#### 독립 테스트 근거

- 독립 테스트 환경은 Linux/Python 3.12 only입니다.
- 새 격리 Python 3.12 virtual environment에서 full archive `.[test]`를 local wheelhouse로 no network 설치했습니다.
- `pip check`가 통과했습니다.
- 65개 test가 통과했습니다.
- checkout 밖에서 installed `chunklab` CLI health check가 통과했습니다.

#### 측정된 오프라인 벤치마크 결과

- 개발용 한/영 합성 벤치마크: 모든 조건에서 5/5 full-answer evidence retrieval.
- Held-out 한국어 법령 paraphrase 벤치마크: 모든 조건에서 필요한 evidence span 3/3 발견.
- 모든 조건은 같은 deterministic lexical ranker와 UTF-8 byte budget을 사용했습니다.
- 이 작은 fixture에서는 screening 또는 offline mock-guided chunking의 split-quality 개선이 입증되지 않았습니다.

#### 한계와 deferred work

- Production retrieval-quality claim은 하지 않습니다.
- 법률 자문이 아닙니다. Held-out 한국어 법령 사례는 ChunkLab-authored paraphrase이며 법령 원문 복사가 아닙니다.
- Live provider validation은 하지 않았습니다. 실제 network API에 대한 provider schema/behavior는 미검증입니다.
- URL fetching, PDF/OCR, deployment, automatic live provider calls, full boundary optimization, delimiter-specific chunking, graph features, hierarchical summaries, vector database, retrieval pipeline integration은 deferred입니다.
- 상류 Jev/RAG 연구 구현은 문단 검증, 질의 점수, 경계 결정, 태깅의 inspiration으로만 참조하며 재현이나 live Jev 검증을 주장하지 않습니다.

### References / 참고

- E-Commerce Act effective 2026-07-21: https://www.law.go.kr/LSW/lsInfoP.do?ancNo=21312&ancYd=20260120&efYd=20260721&lsiSeq=282793
- Enforcement Decree effective 2026-07-21: https://www.law.go.kr/LSW/lsInfoP.do?efYd=20260721&lsiSeq=288143
- Jev/RAG inspiration: https://github.com/MersivMedia/jev-rag-retrieval
