"""허용 태그 정밀도·핵심 개념 재현율과 실행 성능을 저장된 응답으로 평가합니다."""
from __future__ import annotations

import csv
import html
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .common import read_json, read_rows, write_json
from .scoring import SCORING_VERSION, score_tags

HUMAN_FIELDS = ["reviewer", "tag_precision_0to1", "core_recall_0to1", "unsupported_claim_0or1",
                "temporal_evidence_0to2", "needs_review_correct_0or1", "notes"]


def save_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def lexical_diagnostic(predicted, answer):
    norm = lambda words: {"".join(x.split()).casefold() for x in words}
    p, a = norm(predicted), norm(answer)
    tp = len(p & a)
    precision = tp / len(p) if p else None
    recall = tp / len(a) if a else None
    return precision, recall


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    ix = (len(values) - 1) * p
    lo = int(ix)
    return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (ix - lo)


def build_report(run_dir, dataset_root):
    root, data = Path(run_dir), Path(dataset_root)
    rows = read_rows(root / "requests.jsonl")
    config = read_json(root / "config.json")
    events = read_rows(root / "events.jsonl")
    mock = config["identity"]["mock"]
    old_reviews = {}
    review_path = root / "review.csv"
    if review_path.exists():
        with review_path.open(encoding="utf-8-sig", newline="") as f:
            old_reviews = {r["attempt_id"]: r for r in csv.DictReader(f)}
    # Use the run's frozen answer snapshot even if the source annotations are later edited.
    snapshot = read_json(root / "references.json") if (root / "references.json").exists() else None
    annotations = data / "reviewer" / "annotation_notes.json"
    note_rows = snapshot["annotations"] if snapshot else read_json(annotations) if annotations.exists() else []
    notes = {r["id"]: r for r in note_rows}
    metrics, reviews, groups = [], [], defaultdict(list)
    score_groups = defaultdict(list)
    for row in rows:
        base = {k: row.get(k) for k in ["attempt_id", "job_id", "profile", "case_id", "media_type", "execution_status",
                "json_valid", "schema_valid", "input_tokens", "output_tokens", "inference_s", "preprocess_s",
                "request_wall_s", "context_occupancy", "context_load_confirmed", "session_id", "reuse_index_this_process_profile"]}
        base.update(row.get("setting", {}))
        base.update(row.get("wave_metrics", {}))
        base.update(mock=mock, capacity_only=row.get("capacity_only", False))
        answer_path = data / "answers" / f"{row['case_id']}.json"
        answer = snapshot["answers"].get(row["case_id"]) if snapshot else read_json(answer_path) if answer_path.exists() else None
        parsed = row.get("parsed")
        # No model or reference claims for mock, capacity, failed, or malformed responses.
        quality = not mock and not row.get("capacity_only") and row["execution_status"] == "ok" and row["schema_valid"]
        tag_scores = None
        if quality and answer:
            tag_scores = score_tags(parsed["keywords"], answer)
            p, r = lexical_diagnostic(parsed["keywords"], answer["keywords"])
            base.update(exact_tag_precision_diagnostic=p, exact_tag_recall_diagnostic=r,
                        needs_review_reference_match=parsed["needs_review"] == answer["needs_review"],
                        place_exact_reference_match=parsed["place_name"] == answer["place_name"])
        else:
            base.update(exact_tag_precision_diagnostic=None, exact_tag_recall_diagnostic=None,
                        needs_review_reference_match=None, place_exact_reference_match=None)
        base.update(scoring_version=SCORING_VERSION, tag_score_evaluated=tag_scores is not None,
                    allowed_tag_precision=None, core_tag_recall=None, output_tag_count=None,
                    allowed_reference_tag_count=None, core_group_count=None,
                    matched_allowed_tags=None, unmatched_tags=None, matched_core_groups=None,
                    missing_core_groups=None)
        if tag_scores is not None:
            # 배열은 CSV에서도 읽을 수 있도록 JSON 문자열로 보관합니다.
            base.update({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                         for key, value in tag_scores.items()})
        metrics.append(base)
        groups[(row["profile"], row.get("media_type", "unknown"))].append(row)
        score_groups[(row["profile"], row.get("media_type", "unknown"))].append(base)
        note = notes.get(row["case_id"], {})
        review = {"attempt_id": row["attempt_id"], "profile": row["profile"], "case_id": row["case_id"],
                  "mock": mock, "capacity_only": row.get("capacity_only"),
                  "execution_status": row["execution_status"], "schema_valid": row["schema_valid"],
                  "selected_paths": json.dumps(row.get("media", {}).get("source_paths", []), ensure_ascii=False),
                  "raw_output": row.get("raw_output"), "reference_answer": json.dumps(answer, ensure_ascii=False),
                  "allowed_tag_precision_auto": base["allowed_tag_precision"],
                  "core_tag_recall_auto": base["core_tag_recall"],
                  "matched_allowed_tags": base["matched_allowed_tags"],
                  "unmatched_tags_to_review": base["unmatched_tags"],
                  "missing_core_groups": base["missing_core_groups"],
                  "core_keyword_groups": json.dumps(answer.get("core_keywords", []) if answer else [], ensure_ascii=False),
                  "core_concepts": json.dumps(note.get("core_concepts", []), ensure_ascii=False),
                  "unsupported_claim_examples": json.dumps(note.get("unsupported_claims", []), ensure_ascii=False)}
        review.update({key: old_reviews.get(row["attempt_id"], {}).get(key, "") for key in HUMAN_FIELDS})
        reviews.append(review)
    summaries = []
    for (profile, media), group in groups.items():
        ok = [r for r in group if r["execution_status"] == "ok"]
        latency = [r["request_wall_s"] for r in ok if r.get("request_wall_s") is not None]
        peaks = [r["wave_metrics"]["gpu_peak_mib"] for r in group if r.get("wave_metrics", {}).get("gpu_peak_mib") is not None]
        scored = [r for r in score_groups[(profile, media)] if r["tag_score_evaluated"]]
        precisions = [r["allowed_tag_precision"] for r in scored if r["allowed_tag_precision"] is not None]
        recalls = [r["core_tag_recall"] for r in scored if r["core_tag_recall"] is not None]
        summaries.append({"profile": profile, "media_type": media, "attempts": len(group),
                          "unique_jobs": len({r["job_id"] for r in group}), "execution_success_rate": len(ok) / len(group),
                          "json_valid_rate_all_attempts": sum(r["json_valid"] for r in group) / len(group),
                          "schema_valid_rate_all_attempts": sum(r["schema_valid"] for r in group) / len(group),
                          "latency_n": len(latency), "median_request_s": statistics.median(latency) if latency else None,
                          "p95_request_s": percentile(latency, .95), "sampled_gpu_peak_mib": max(peaks) if peaks else None,
                          "tag_scored_attempts": len(scored), "empty_tag_outputs": sum(r["output_tag_count"] == 0 for r in scored),
                          "allowed_tag_precision_n": len(precisions), "core_tag_recall_n": len(recalls),
                          "mean_allowed_tag_precision": statistics.mean(precisions) if precisions else None,
                          "mean_core_tag_recall": statistics.mean(recalls) if recalls else None,
                          "scoring_version": SCORING_VERSION})
    metric_fields = list(dict.fromkeys(k for r in metrics for k in r)) or ["attempt_id", "profile", "execution_status"]
    save_csv(root / "metrics.csv", metrics, metric_fields)
    save_csv(root / "summary.csv", summaries, list(summaries[0]) if summaries else ["profile", "attempts"])
    review_fields = list(reviews[0]) if reviews else ["attempt_id", *HUMAN_FIELDS]
    save_csv(review_path, reviews, review_fields)
    write_json(root / "summary.json", summaries)
    chart = ""
    if summaries and not mock:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            points = [s for s in summaries if s["median_request_s"] is not None]
            if points:
                fig, ax = plt.subplots(figsize=(10, max(3, len(points) * .4)))
                ax.barh([s["profile"] + "/" + s["media_type"] for s in points], [s["median_request_s"] for s in points])
                ax.set_xlabel("Median request wall time (s), successful requests only")
                fig.tight_layout()
                fig.savefig(root / "latency.png", dpi=160)
                plt.close(fig)
                chart = '<img alt="실험별 요청 시간" src="latency.png" style="max-width:100%">'
        except ImportError:
            chart = "<p>matplotlib 미설치: 그래프 생략. summary.csv에서 수치를 확인하세요.</p>"
    esc = lambda v: html.escape(str(v))
    def table(records):
        if not records:
            return "<p>기록 없음</p>"
        keys = list(records[0])
        return "<div class='table'><table><thead><tr>" + "".join(f"<th>{esc(k)}</th>" for k in keys) + "</tr></thead><tbody>" + "".join(
            "<tr>" + "".join(f"<td>{esc(round(r[k], 4) if isinstance(r[k], float) else r[k])}</td>" for k in keys) + "</tr>" for r in records) + "</tbody></table></div>"
    details = "".join(f"<details><summary>{esc(r['profile'])} / {esc(r['case_id'])} · {esc(r['execution_status'])} · schema={r['schema_valid']}</summary>"
                      f"<pre>{esc(r.get('raw_output') or r.get('error'))}</pre></details>" for r in rows)
    score_summary = [{"조건": s["profile"], "종류": s["media_type"],
                      "태그 채점 건수": s["tag_scored_attempts"], "빈 태그 응답": s["empty_tag_outputs"],
                      "허용 태그 정밀도 평균": s["mean_allowed_tag_precision"],
                      "정밀도 분모 건수": s["allowed_tag_precision_n"],
                      "핵심 개념 재현율 평균": s["mean_core_tag_recall"],
                      "재현율 분모 건수": s["core_tag_recall_n"]} for s in summaries]
    score_details = [{"조건": r["profile"], "샘플": r["case_id"],
                      "허용 태그 정밀도": r["allowed_tag_precision"], "핵심 개념 재현율": r["core_tag_recall"],
                      "인정된 태그": r["matched_allowed_tags"], "미등록 태그 · 사람 확인": r["unmatched_tags"],
                      "빠진 핵심 개념": r["missing_core_groups"]} for r in metrics if r["tag_score_evaluated"]]
    title = "MOCK · 실행 경로 확인용, 모델 성능 결과 아님" if mock else "filename A/B 실험 결과"
    content = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{max-width:1200px;margin:40px auto;padding:0 24px;font:16px/1.65 system-ui;color:#163047;background:#f7f9fc}}
h1{{font-size:28px}} .notice{{background:#fff2cc;padding:16px;border-radius:8px}}.table{{overflow:auto;background:white}}
table{{border-collapse:collapse;font-size:13px}}td,th{{padding:10px;border:1px solid #dae1e8;white-space:nowrap}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;padding:16px}}details{{margin:12px 0}}a{{color:#1253a4}}</style>
<h1>{title}</h1><div class="notice">계획 측정 요청 {config['planned_requests']}개 · 저장된 시도 {len(rows)}개 · 고유 요청 {len({r['job_id'] for r in rows})}개 · 로드 이벤트 {len(events)}개.
실패·재시도도 비율의 분모에 포함합니다. 계획 대비 누락과 아래 오류를 함께 확인하세요.</div>
<p>참조 답안의 독립 사람 검수: {esc(config.get('reference_human_reviewed'))}. 허용 목록과 핵심 동의어 묶음으로 채점합니다.
미등록 표현은 사람 확인이 필요하며, 곧바로 환각으로 판정하지 않습니다. 관찰 근거·행동 변화는 사람이 평가합니다.
B의 용량 실험은 의미 품질 평가에서 제외합니다. 모의 실행 수치로 실제 속도·메모리를 판단하지 마세요.</p>
<p><a href="summary.csv">조건별 요약</a> · <a href="metrics.csv">요청별 수치</a> · <a href="review.csv">사람 평가표</a> · <a href="requests.jsonl">응답 원문</a> · <a href="eda.json">데이터 점검</a></p>
<h2>태그 평가</h2>{table(score_summary)}
<p>점수 범위는 0~1입니다. 정밀도 = 허용된 출력 태그 수 / 출력 태그 수, 재현율 = 포착한 핵심 묶음 수 / 핵심 묶음 수.
정답 후보가 100개라도 출력 5개가 모두 허용되면 정밀도는 1입니다. 같은 핵심 개념의 동의어를 여러 번 출력해도 재현율은 한 번만 계산합니다.
정상 실행·형식 통과·정답 존재 조건을 만족하는 요청만 채점합니다. 모의 실행·B 용량 실험은 제외합니다.
평균은 채점된 요청별 점수의 산술평균입니다. 빈 출력의 정밀도와 핵심 묶음 미작성 시 재현율은 null이며 각 평균에서 제외합니다.
빈 출력은 핵심 묶음이 있을 때 재현율 0입니다. 분모 건수와 형식·실행 실패율도 함께 보세요. 채점 버전: {SCORING_VERSION}.</p>
<h2>태그별 매칭 근거</h2>{table(score_details)}
<h2>조건별 실행 결과</h2>{table(summaries)}{chart}
<p>시간은 모델 로드를 제외한 요청 시간이며 첫 요청을 포함합니다. HTTP 방식에서는 대기 시간도 포함합니다.
GPU 메모리는 장치 전체의 표본 측정값이며 동시 요청에서 각 요청의 전용 메모리가 아닙니다. null은 측정 불가입니다.</p>
<h2>시작·오류 기록</h2><pre>{esc(json.dumps(events, ensure_ascii=False, indent=2))}</pre>
<h2>응답 확인</h2>{details}<h2>평가 방법</h2>
<p>review.csv에서 tag_precision = 근거 있는 태그 수 / 출력 태그 수, core_recall = 포착한 핵심 개념 수 / 정답 핵심 개념 수를 기록합니다.
출력 태그가 없으면 precision은 빈칸으로 두고 core_recall로 누락을 평가합니다. 영상 변화는 0=오류·누락, 1=일부, 2=핵심 변화 반영입니다.
사람 평가 입력은 리포트 재생성 시 보존되며, 이 예제는 사람 점수를 자동 합산하지 않습니다.</p>
<p>Based-On: none · project_extension · 실제 결과는 실행 환경과 참조 답안 검수 범위 내에서만 해석하세요.</p></html>"""
    (root / "report.html").write_text(content, encoding="utf-8")
    return root / "report.html"
