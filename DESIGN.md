# ChunkLab — RAG 전처리·청킹 실험실 (가칭)

목표: 같은 문서에 서로 다른 청킹 정책을 적용하고, 변경 근거와 검색 성능·비용을 비교한다. 기본 모드는 네트워크 없이 동작한다. 검색 DB나 답변 생성기는 이 프로젝트의 필수 구성요소가 아니다.

## 첫 버전 범위
- 로컬 Markdown / HTML / TXT 업로드, 비교 GUI(Streamlit 후보), JSONL + 별도 심사 보고서 내보내기.
- Markdown은 markdown-it-py의 블록 토큰과 줄 범위 사용. HTML 업로드에는 Trafilatura를 본문 후보 추출기로 사용하되 이를 원문 좌표 파서로 간주하지 않는다. 증거 추적이 필요하면 원본 DOM 경로를 먼저 수집하고 매핑 불명확 시 원문 대비 위치를 미확정으로 표시한다. 추출기가 생략한 영역을 포함해 심사 가능하도록 처리 이력을 남긴다. URL 가져오기·PDF/OCR은 v0 범위 밖; PDF가 필요하면 Docling 검토.
- 문서/블록/청크: 원본 해시·문서 버전·블록 ID·heading path·원문 위치·순서·타입. JSONL에는 포함된 청크만, 격리 내용은 일반 export 및 요약·임베딩·검색 경로에서 제외한다. 미리보기는 텍스트로 렌더링하고 업로드 HTML을 실행하지 않는다.
- 규칙: HTML 구조나 반복 상용구를 활용하고, 추적 링크와 근거 링크를 구분한다. 정확히 확인된 상용구는 내보내지 않되 원본은 보존. AI 지시 의심 블록은 격리하고 근거와 사람이 복구할 수 있는 이력 제공. 인용된 보안 예시나 사람 대상 운영 절차는 유사 오탐 사례로 평가. 탐지기는 보안 보장이 아니다. 판단 모델에 도구·자격증명·제어권을 주지 않는다. 외부 판정은 명시적으로 켠 경우에만 선택한 공급자에게 최소 문맥을 전송한다.

## 경계 실험
1. structural (기본): heading, 단락, 목록, 표와 코드에 따라 묶고 토큰 제한 적용. 지나치게 큰 표는 행 단위/헤더 반복, 코드는 허용된 안전한 경계에서만 분할. 불가능한 입력은 명시적 예외 처리하고, 최종 export에서 설정된 하드 제한을 조용히 초과하지 않는다.
2. selective: 코드가 만든 애매한 경계의 앞뒤 원문과 섹션 제목만 보냄. `continues`와 `refers_back`을 별개로 평가. 구별자도 반복 heading/조항/FAQ/레코드 시작 기호 등 코드가 실제 탐지한 후보 ID만 모델이 선택하거나 기각; 파서가 등장 위치, 범위, 크기 분포, 표/코드 오탐을 검증한 후 적용. 정규식 생성·실행은 하지 않는다.
3. model-guided full: 허용되는 모든 경계에 대해 판정하되 모델은 텍스트/청크를 생성하지 않는다. 규칙이 크기 제한·원문 위치·금지 경계를 적용하고 동적계획법이 전체 컷을 선택한다. 의존성이 높은 경계는 크게 페널티. 비교 대상으로만 두고 실패/예산 소진 시 구조적 결과와 degraded 표시를 남긴다.

청크 단위 검사는 `low_information`과 `self_contained`를 분리한다. 자기완결성이 낮다고 자동 삭제하지 않고 제목, 이웃 관계 또는 상위 섹션 정보를 첨부. 저정보는 초기에 플래그만 부여; 손실 평가 후 필터 opt-in. Taxonomy는 후보 ID·기타/판단보류와 모델값·식별자·정책 버전을 기록한다.

## 공급자와 측정
- provider 공통 기능: predicate / choice / rubric score. 응답엔 score kind(provider probability / token proxy / rule / missing), status, 실제 모델·프롬프트 버전, 사용량·latency. refusal, 미지원, 오류, 낮은 확신을 분리한다.
- OpenAI Decisions 직접 호출(gpt-6-luna), OpenRouter Decisions로 Jev/다른 모델, TypeSafe System One 직접, Chat Completions A/B logprobs. 마지막 경로는 두 정답 후보가 같은 위치에서 단일 토큰임을 확인하고 둘 다 반환될 때만 대비값 산출. 누락/출력 거절을 0점으로 치환하지 않고 보류하며 원래 확률 질량과 후보 조건부 점수를 구분; 검증셋 없이 공급자 공통 임계값 금지. 실제 키 권한/엔드포인트 호출은 이 계획 단계에서 검증하지 않음.
- 클라이언트 캐시는 문서/로컬 문맥 해시, 질문/정책 버전, 공급자/실모델을 구분. 단계별 호출/토큰 예산과 재시도 상한. 공개/합성 데이터만 초기 온라인 테스트에 사용.
- 비교: 최소 고정 토큰 baseline + structural + selective + full. 한국어/영어 혼합 약관·FAQ·매뉴얼 합성/공개 샘플과 정답 원문 span. 같은 임베딩, 검색기, 토큰 예산, 질문 세트 사용. Evidence Recall@k 및 고정된 컨텍스트 토큰 예산 내 근거 재현율, 경계 선호도/정답 근거 보존, 격리 precision/recall·정상 근거 오격리율, 문서당 비용과 p50/p95 latency를 측정. 분할 정책을 고르는 검증셋과 최종 평가셋 분리; 기본모드 승격은 실제 근거 검색 개선 시에만.

## 차별화와 다음 순서
- 차별화 1순위: 동일 문서의 구조/모델 결과를 나란히 놓고 잘린 위치·빠진 근거·격리 사유를 원문에 연결한다. 같은 규칙을 승격하기 전에 다른 문서에 replay한다.
- 2단계: exact/near-duplicate와 섹션 인접 링크, `requires_context` 링크. 그 다음 임베딩 top-k나 클러스터가 후보만 좁히고 판정 모델이 `same_topic`/`adds_evidence`/`contradicts` 등을 비교한다. 근접 주제로 답변 근거를 대체하지 않는다. 요약은 마지막에 선택된 그룹만 만들고 자식 ID·원문 증거 링크를 붙이며 원문 청크는 보존한다. 섹션 부모를 요약 없이 먼저 비교. RAPTOR는 참고 설계, 첫 버전의 필수 의존성 아님.
- 첫 구현 단위: 오프라인 업로드 → 구조 청킹 → 원문 연결 → JSONL 내보내기. 그 다음 mock provider와 단일 Decisions 어댑터를 붙여 A/B 시험한다. 로그인, 배포, 퍼블릭 레포 생성은 범위 밖.

## 근거
- [jev-rag-retrieval](https://github.com/MersivMedia/jev-rag-retrieval): 문단 검증, 질의별 점수, 경계 DP, 태깅을 이미 구현한 MIT 참고 구현; 자체 실험에서 AI 경계가 구조 기반을 이기지 못했다고 보고. 전체를 의존하기보다 추후 가져오는 코드마다 MIT 고지 유지 또는 독립 구현.
- [OpenAI Decisions](https://developers.openai.com/api/docs/guides/decisions) · [OpenRouter Jev](https://openrouter.ai/blog/insights/what-is-jev/) · [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
- [Trafilatura](https://trafilatura.readthedocs.io/en/latest/usage-python.html) · [markdown-it-py](https://markdown-it-py.readthedocs.io/en/latest/using.html) · [Docling](https://docling-project.github.io/docling/concepts/chunking/) · [RAPTOR](https://arxiv.org/abs/2401.18059).
