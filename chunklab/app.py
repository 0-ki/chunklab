from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from streamlit.web import cli as stcli

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chunklab.audit import QualityAuditConfig, audit_chunks, parse_taxonomy_lines, taxonomy_to_text
from chunklab.decisions import FakeDecisionProvider, OpenAIChatLogprobsProvider, OpenAIDecisionsProvider, OpenRouterJevProvider
from chunklab.export import chunks_to_jsonl, issues_to_report, process_upload, process_upload_screened
from chunklab.guided import GuidedChunkConfig, compare_model_guided_boundaries
from chunklab.parsers import parse_upload
from chunklab.screening import prescreen_blocks


def _source_preview(original: str, line_start: int | None, line_end: int | None, radius: int = 3) -> str:
    lines = original.splitlines()
    if not lines or line_start is None or line_end is None:
        return "원문 line/span 매핑이 없습니다."
    start = max(1, line_start - radius)
    end = min(len(lines), line_end + radius)
    rendered = []
    for line_no in range(start, end + 1):
        marker = "▶" if line_start <= line_no <= line_end else " "
        rendered.append(f"{marker} {line_no:>4}: {lines[line_no - 1]}")
    return "\n".join(rendered)


def _restore_multiselect_key(document_sha256: str) -> str:
    return f"restore_block_ids_{document_sha256}"


def main() -> None:
    st.set_page_config(page_title="ChunkLab", layout="wide")
    st.title("ChunkLab — 오프라인 구조 청킹")
    st.caption("Markdown / HTML / TXT 파일을 로컬에서 파싱하고 JSONL로 내보냅니다. HTML은 실행하지 않습니다.")

    uploaded = st.file_uploader("파일 업로드", type=["md", "markdown", "html", "htm", "txt"])
    hard_limit = st.number_input(
        "하드 예산 제한 (utf8_bytes, 보수적 오프라인 모드)",
        min_value=32,
        max_value=200_000,
        value=2_000,
        step=100,
    )
    with st.expander("v0.5 선택형 품질 감사", expanded=False):
        st.warning(
            "기본값은 품질 감사 없음입니다. 감사는 low_information/self_contained/taxonomy 메타데이터만 추가하며 "
            "약한 청크를 자동 삭제하거나 순위를 바꾸지 않습니다."
        )
        enable_quality_audit = st.checkbox("청크 품질 감사 활성화")
        taxonomy_text = st.text_area(
            "Taxonomy (category: keyword, keyword)",
            taxonomy_to_text(),
            help="unknown은 항상 명시적 fallback으로 남겨두며 사용자 taxonomy 이름으로 사용하지 않습니다.",
        )
        max_categories = st.number_input("청크당 taxonomy label 상한", min_value=1, max_value=8, value=3, step=1)
        max_reasons = st.number_input("청크당 감사 reason 상한", min_value=1, max_value=12, value=6, step=1)
    with st.expander("v0.3 선택형 결정론적 사전 검사", expanded=False):
        st.warning(
            "기본값은 사전 검사 없음입니다. 이 휴리스틱은 완전한 안전 보장이 아니며, "
            "명시적인 AI 대상 지시 의심 블록과 보수적인 구조 상용구 후보만 분리합니다."
        )
        enable_screening = st.checkbox("청킹 전 사전 검사 활성화")
        st.caption("일반 JSONL export에는 격리/제거 사유 상세를 넣지 않습니다. 아래 검토 목록에서 명시적으로 복원할 수 있습니다.")
    with st.expander("v0.2 선택형 모델 경계 비교", expanded=False):
        st.warning(
            "기본값은 오프라인 구조 청킹입니다. 제한된 경계 판단 비교를 명시적으로 원할 때만 실행하세요. "
            "업로드 텍스트는 신뢰하지 않는 근거로 취급하며 credentials는 요청 데이터에 넣지 않습니다."
        )
        enable_model_compare = st.checkbox("선택형 경계 비교 활성화")
        provider_name = st.selectbox(
            "판단 공급자",
            [
                "deterministic fake (offline)",
                "OpenAI Decisions (experimental live)",
                "OpenAI Chat Completions A/B logprobs (experimental live)",
                "OpenRouter Jev (experimental live)",
            ],
        )
        max_requests = st.number_input("최대 판단 요청 수", min_value=1, max_value=24, value=12, step=1)
        timeout_s = st.number_input("요청별 timeout(초)", min_value=1.0, max_value=20.0, value=4.0, step=1.0)
        live_provider_consent = st.checkbox(
            "live provider 요청에 명시적으로 동의",
            help="실험적 live integration은 선택·버튼·동의가 모두 있어야 실행됩니다. 개발/테스트에서는 mock transport만 사용합니다.",
        )
        chat_logprob_predicate_cap = st.number_input(
            "Chat A/B logprobs predicate subrequest 상한",
            min_value=1,
            max_value=2,
            value=2,
            step=1,
            help="OpenAI Chat Completions A/B logprobs 어댑터는 기존 boundary predicate별로 별도 요청하며 fallback/retry하지 않습니다.",
        )
        run_model_compare = st.button(
            "명시적 비교 실행",
            disabled=not enable_model_compare,
            help="OpenAI/OpenRouter 모드는 각각 지정된 CHUNKLAB_* 키만 사용하며 자동 실행되지 않습니다.",
        )

    if not uploaded:
        st.info("파일을 업로드하면 청킹 결과와 원문 연결을 확인할 수 있습니다.")
        return

    data = uploaded.getvalue()
    screen = None
    try:
        if enable_screening:
            initial_doc = parse_upload(uploaded.name, data)
            if not initial_doc.blocks:
                raise ValueError("업로드한 파일에서 청킹할 수 있는 텍스트를 찾지 못했습니다.")
            initial_screen = prescreen_blocks(initial_doc.blocks)
            reviewable = initial_screen.removed
            restore_labels = [
                f"{decision.block_id} · {decision.disposition} · {' / '.join(decision.heading_path) or '(제목 없음)'}"
                for decision in reviewable
            ]
            selected_restore_labels = st.multiselect(
                "명시적으로 복원할 원본 블록 ID 선택",
                restore_labels,
                key=_restore_multiselect_key(initial_doc.sha256),
                help="복원은 이 문서·이 실행에서 선택한 원본 block ID에만 적용됩니다. 자동 복원하지 않습니다.",
            )
            restore_ids = {
                reviewable[restore_labels.index(label)].block_id
                for label in selected_restore_labels
            }
            doc, screen, chunks, issues = process_upload_screened(
                uploaded.name,
                data,
                int(hard_limit),
                restore_block_ids=restore_ids,
            )
        else:
            doc, chunks, issues = process_upload(uploaded.name, data, int(hard_limit))
    except ValueError as exc:
        st.error(str(exc))
        return
    if enable_quality_audit:
        taxonomy = parse_taxonomy_lines(taxonomy_text) or None
        chunks = audit_chunks(
            chunks,
            QualityAuditConfig(
                taxonomy=taxonomy or QualityAuditConfig().taxonomy,
                max_categories=int(max_categories),
                max_reasons=int(max_reasons),
            ),
        )
    jsonl = chunks_to_jsonl(doc, chunks)
    report = issues_to_report(issues)

    st.subheader("요약")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("블록", len(doc.blocks))
    col2.metric("청크", len(chunks))
    col3.metric("이슈", len(issues))
    col4.metric("문서 SHA-256", doc.sha256[:12])
    if screen is not None:
        st.info(
            f"사전 검사 휴리스틱({screen.policy_version}) 적용: "
            f"export/scoring 대상 블록 {len(screen.blocks)} / 원본 {len(doc.blocks)}. 완전한 안전 보장이 아닙니다."
        )
        removed_rows = [
            {
                "원본 ID": decision.block_id,
                "처리": "복원됨" if decision.restored else decision.disposition,
                "이유": decision.reason_ko,
                "출처": (
                    f"lines {decision.source.line_start}-{decision.source.line_end}"
                    if decision.source.line_start is not None
                    else (decision.source.note or "원문 위치 미확정")
                ),
                "제목": " / ".join(decision.heading_path),
                "유형": decision.block_type,
            }
            for decision in screen.decisions
            if decision.disposition in {"drop", "quarantine"} or decision.restored
        ]
        if removed_rows:
            st.subheader("사전 검사 검토 목록")
            st.dataframe(removed_rows, use_container_width=True)

    if enable_quality_audit:
        st.info("품질 감사가 export metadata에 포함되었습니다. 청크 텍스트·순서·검색 순위는 변경하지 않습니다.")
        st.subheader("품질 감사 요약")
        st.dataframe(
            [
                {
                    "chunk": chunk.id,
                    "flags": ", ".join(chunk.flags),
                    "taxonomy": ", ".join(chunk.audit.get("quality", {}).get("taxonomy", {}).get("labels", [])),
                    "low_information": chunk.audit.get("quality", {}).get("low_information", {}).get("value"),
                    "self_contained": chunk.audit.get("quality", {}).get("self_contained", {}).get("value"),
                }
                for chunk in chunks
            ],
            use_container_width=True,
        )

    if issues:
        st.warning("일부 블록은 하드 제한 때문에 내보내기에서 제외되었거나 검토가 필요합니다.")
        st.dataframe(
            [
                {
                    "id": issue.id,
                    "severity": issue.severity,
                    "block": issue.block_id,
                    "type": issue.block_type,
                    "budget": issue.budget_count,
                    "message": issue.message,
                }
                for issue in issues
            ],
            use_container_width=True,
        )

    st.download_button(
        "JSONL 다운로드",
        jsonl,
        file_name=f"{Path(uploaded.name).stem}.chunks.jsonl",
        mime="application/x-jsonlines",
        disabled=not chunks,
    )
    st.download_button(
        "이슈 보고서 다운로드",
        report,
        file_name=f"{Path(uploaded.name).stem}.issues.jsonl",
        mime="application/x-jsonlines",
    )

    if enable_model_compare:
        st.subheader("선택형 structural vs model-guided 비교")
        st.caption(
            "모델 점수는 섹션 내부 컷만 추가할 수 있습니다. heading 경계와 hard size cap은 구조 규칙이 유지합니다."
        )
        compare_source_blocks = screen.blocks if screen is not None else doc.blocks
        candidates = [
            (left, right)
            for left, right in zip(compare_source_blocks, compare_source_blocks[1:])
            if left.heading_path == right.heading_path
            and left.type != "heading"
            and right.type != "heading"
            and not left.indivisible
            and not right.indivisible
        ]
        proxy_units = sum(len((left.text + right.text).encode("utf-8")) for left, right in candidates[: int(max_requests)])
        st.info(
            f"경계 후보: {len(candidates)}; 요청 상한: {int(max_requests)}; "
            f"prompt overhead 전 대략 입력 단위 proxy: {proxy_units} utf8_bytes."
        )
        if run_model_compare:
            if provider_name == "OpenAI Decisions (experimental live)":
                if not live_provider_consent:
                    st.error("실험적 live provider는 별도 명시 동의가 필요합니다.")
                    return
                provider = OpenAIDecisionsProvider()
            elif provider_name == "OpenAI Chat Completions A/B logprobs (experimental live)":
                if not live_provider_consent:
                    st.error("실험적 live provider는 별도 명시 동의가 필요합니다.")
                    return
                provider = OpenAIChatLogprobsProvider(max_predicates_per_decide=int(chat_logprob_predicate_cap))
            elif provider_name == "OpenRouter Jev (experimental live)":
                if not live_provider_consent:
                    st.error("실험적 live provider는 별도 명시 동의가 필요합니다.")
                    return
                provider = OpenRouterJevProvider()
            else:
                provider = FakeDecisionProvider()
            with st.spinner("제한된 경계 판단 실행 중..."):
                guided = compare_model_guided_boundaries(
                    compare_source_blocks,
                    hard_limit=int(hard_limit),
                    provider=provider,
                    config=GuidedChunkConfig(max_requests=int(max_requests), timeout_s=float(timeout_s)),
                )
            if guided.degraded:
                st.warning(f"Degraded 비교입니다. 필요한 곳은 structural fallback을 사용했습니다. {guided.fallback_reason or ''}")
            st.write(
                {
                    "provider_model": guided.provider_model,
                    "requests": guided.request_count,
                    "input_units": guided.input_units,
                    "structural_chunks": len(guided.structural_chunks),
                    "guided_chunks": len(guided.guided_chunks),
                    "max_requests": guided.max_requests,
                    "timeout_s": guided.timeout_s,
                }
            )
            st.dataframe(
                [
                    {
                        "after": decision.after_block_id,
                        "before": decision.before_block_id,
                        "status": decision.status,
                        "probability": decision.probability,
                        "provider_status": decision.provider_status,
                        "reason": decision.reason,
                    }
                    for decision in guided.decisions
                ],
                use_container_width=True,
            )
            left_compare, right_compare = st.columns(2)
            with left_compare:
                st.markdown("#### 구조 청킹")
                for chunk in guided.structural_chunks:
                    st.code(f"{chunk.id} · {chunk.budget_count} bytes\n{chunk.text}", language=None)
            with right_compare:
                st.markdown("#### 모델 기반 추가 컷")
                for chunk in guided.guided_chunks:
                    st.code(f"{chunk.id} · {chunk.budget_count} bytes\n{chunk.text}", language=None)

    st.subheader("청크 검토")
    if not chunks:
        st.error("내보낼 수 있는 청크가 없습니다. 하드 제한을 늘리거나 원문을 조정하세요.")
        return

    labels = [
        f"{chunk.id} · {chunk.budget_count} bytes · {' / '.join(chunk.heading_path) or '(제목 없음)'}"
        for chunk in chunks
    ]
    selected_label = st.selectbox("청크 선택", labels)
    selected = chunks[labels.index(selected_label)]

    left, right = st.columns(2)
    with left:
        st.markdown("#### 청크 텍스트")
        st.code(selected.text, language=None)
        st.json(
            {
                "chunk_id": selected.id,
                "heading_path": selected.heading_path,
                "source": selected.source.to_json(),
                "block_ids": selected.block_ids,
                "flags": selected.flags,
                "audit": selected.audit,
            }
        )
    with right:
        st.markdown("#### 원문 미리보기")
        preview = _source_preview(doc.text, selected.source.line_start, selected.source.line_end)
        if selected.source.note:
            preview = f"{preview}\n\n[{selected.source.note}]"
        st.code(preview, language=None)
        if not selected.source.mapped:
            st.info(selected.source.note or "원문 위치가 미확정입니다.")


if __name__ == "__main__":
    main()


def cli() -> None:
    """Console entry point that launches the Streamlit app."""
    app_path = str(Path(__file__).resolve())
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.address=localhost",
        "--browser.gatherUsageStats=false",
        *_checked_streamlit_args(sys.argv[1:]),
    ]
    raise SystemExit(stcli.main())


def _checked_streamlit_args(args: list[str]) -> list[str]:
    protected = {"--server.address", "--browser.gatherUsageStats"}
    for index, arg in enumerate(args):
        for flag in protected:
            if arg == flag or arg.startswith(f"{flag}="):
                raise SystemExit(f"ChunkLab protects {flag}; do not override it from the console launcher.")
        if index > 0 and args[index - 1] in protected:
            raise SystemExit(f"ChunkLab protects {args[index - 1]}; do not override it from the console launcher.")
    return list(args)
