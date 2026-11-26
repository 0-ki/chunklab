# ChunkLab 1.0.0

[English README](README.md)

ChunkLab은 문서 청킹 실험을 위한 로컬·오프라인 우선 Streamlit 앱입니다. 로컬 Markdown, HTML, TXT 파일을 업로드하고 기본적으로 결정론적 구조 청킹을 수행하며 provenance를 확인한 뒤 JSONL로 내보냅니다.

## 빠른 시작

아래 저장소를 복제한 뒤 소스 폴더에서 설치하세요.

```sh
git clone https://github.com/0-ki/chunklab.git
cd chunklab
```

PyPI의 `chunklab`은 다른 프로젝트이므로 `pip install chunklab`을 실행하지 마세요.

Python 3.11 이상이 필요합니다. 독립적으로 테스트된 릴리스 환경은 Linux/Python 3.12입니다.

POSIX shell:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
chunklab
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
chunklab
```

개발 중에는 다음으로도 실행할 수 있습니다.

```bash
streamlit run chunklab/app.py
```

테스트와 벤치마크:

```bash
python -m pytest -q
python -m chunklab.benchmark
```

## 사용법

1. 로컬 `.md`, `.markdown`, `.html`, `.htm`, `.txt` 파일을 업로드합니다.
2. UTF-8 byte hard limit을 고릅니다. 이는 결정론적 byte 예산이며 tokenizer/model token 수가 아닙니다.
3. 필요한 경우 결정론적 사전 검사, 품질 감사, 오프라인 fake 경계 비교를 명시적으로 켭니다.
4. 청크, provenance, issue, 사전 검사 결정을 검토합니다.
5. JSONL과 issue report를 다운로드합니다.

설치된 `chunklab` 런처는 Streamlit을 `localhost`에 바인딩하고 Streamlit usage telemetry를 끕니다. 보호 설정 override는 거부하지만 port/headless flag는 사용할 수 있습니다.

## 개인정보와 provider 한계

- 기본 동작은 로컬·오프라인입니다. URL을 가져오지 않고 live provider를 자동 호출하지 않습니다.
- 업로드 텍스트는 신뢰하지 않는 evidence로 취급합니다. provider 어댑터에 도구나 제어권을 주지 않고 credentials를 요청 본문에 넣지 않습니다.
- 모든 provider 경로는 실험적입니다. OpenAI Decisions, OpenAI Chat Completions A/B logprobs, OpenRouter Jev는 GUI에서 provider 선택, 실행 버튼, 별도 live-provider 동의가 모두 있어야 실행됩니다.
- provider 경로는 이 릴리스에서 mock test만 완료했습니다. 실제 provider 호출은 하지 않았고 live provider 동작 검증을 주장하지 않습니다.
- OpenAI Decisions/Chat Completions adapter는 `CHUNKLAB_OPENAI_API_KEY`만 읽고, OpenRouter Jev adapter는 `CHUNKLAB_OPENROUTER_API_KEY`만 읽습니다.
- Chat Completions A/B logprobs 경로는 정확한 한 토큰 `A`/`B` 출력과 첫 토큰 A/B logprob 데이터가 모두 있을 때만 수용합니다. 점수는 `relative_token_proxy`이며 provider의 정답 확률이 아닙니다.
- ChunkLab은 업로드 payload나 secret을 영구 저장하지 않습니다.

## 오프라인 벤치마크

`python -m chunklab.benchmark`는 개발용 한/영 합성 벤치마크와 별도 held-out 한국어 법령 paraphrase 사례를 보고합니다. 두 보고 모두 조건별 동일한 결정론적 lexical ranker와 UTF-8 byte 예산을 사용합니다. Held-out 사례는 원문 인용이 아닌 paraphrase이고 법률 자문이 아니며, 법과 시행령 출처를 인용하고 튜닝에 쓰지 않도록 별도로 보고합니다.

v1.0.0 측정 결과: 개발 벤치마크는 모든 조건에서 5개 질의의 기대 evidence를 예산 안에서 모두 찾았습니다. Held-out 벤치마크는 모든 조건에서 필요한 evidence span 3개를 모두 찾았습니다. 이 작은 오프라인 fixture만으로는 screening 또는 offline mock-guided chunking의 split-quality 개선을 입증하지 못했습니다.

상류 Jev/RAG 연구 구현은 문단 검증, 질의 점수, 경계 결정, 태깅의 참고 inspiration으로 인용합니다. ChunkLab은 그 결과를 재현했다고 주장하지 않으며 live Jev 동작을 검증하지 않았습니다.

## 1.0.0 범위

안정 범위: 로컬 Markdown/HTML/TXT 업로드, 구조 청킹, opt-in 결정론적 사전 검사/검토/복원, opt-in 품질 감사, provenance preview, JSONL/issue export, 오프라인 mock-guided 경계 비교, checkout 밖 package/CLI 실행.

실험 범위: 모든 live-provider 경로와 provider-derived 경계 비교. 모두 opt-in이며 mock-tested only입니다.

제외: URL fetching, PDF/OCR, 배포, 자동 live provider 호출, live provider 검증, 법률 자문, production retrieval-quality claim. Full boundary optimization, delimiter-specific chunking, graph features, hierarchical summaries, vector database, retrieval pipeline integration은 이후로 미룹니다.

## 라이선스와 고지

ChunkLab은 MIT License로 배포됩니다. [LICENSE](LICENSE)를 보세요. 제3자 사용/attribution 고지는 [NOTICE.md](NOTICE.md), release notes는 [RELEASE_NOTES.md](RELEASE_NOTES.md)에 있습니다.
