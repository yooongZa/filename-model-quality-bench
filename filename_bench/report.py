"""허용 태그 일치 참고값, 사람 평가표, 실행 성능을 저장된 응답으로 정리합니다."""
from __future__ import annotations

import csv
import html
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .common import read_json, read_rows, write_json
from .scoring import SCORING_VERSION, score_tags

HUMAN_FIELDS = ["reviewer", "tag_accuracy_0to2", "filename_usefulness_0to2", "unsupported_claim_0or1",
                "temporal_evidence_0to2", "notes"]


def save_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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
            base.update(place_exact_reference_match=parsed["place_name"] == answer["place_name"])
        else:
            base.update(place_exact_reference_match=None)
        base.update(scoring_version=SCORING_VERSION, tag_score_evaluated=tag_scores is not None,
                    allowed_tag_match_rate=None, output_tag_count=None,
                    allowed_reference_tag_count=None, matched_allowed_tags=None, unmatched_tags=None)
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
                  "raw_output": row.get("raw_output"),
                  "reference_answer": json.dumps({key: answer[key] for key in ("keywords", "reason", "place_name")
                                                  if key in answer} if answer else None, ensure_ascii=False),
                  "allowed_tag_match_rate_auto": base["allowed_tag_match_rate"],
                  "matched_allowed_tags": base["matched_allowed_tags"],
                  "unmatched_tags_to_review": base["unmatched_tags"],
                  "unsupported_claim_examples": json.dumps(note.get("unsupported_claims", []), ensure_ascii=False)}
        review.update({key: old_reviews.get(row["attempt_id"], {}).get(key, "") for key in HUMAN_FIELDS})
        reviews.append(review)
    summaries = []
    for (profile, media), group in groups.items():
        ok = [r for r in group if r["execution_status"] == "ok"]
        latency = [r["request_wall_s"] for r in ok if r.get("request_wall_s") is not None]
        peaks = [r["wave_metrics"]["gpu_peak_mib"] for r in group if r.get("wave_metrics", {}).get("gpu_peak_mib") is not None]
        scored = [r for r in score_groups[(profile, media)] if r["tag_score_evaluated"]]
        match_rates = [r["allowed_tag_match_rate"] for r in scored if r["allowed_tag_match_rate"] is not None]
        summaries.append({"profile": profile, "media_type": media, "attempts": len(group),
                          "unique_jobs": len({r["job_id"] for r in group}), "execution_success_rate": len(ok) / len(group),
                          "json_valid_rate_all_attempts": sum(r["json_valid"] for r in group) / len(group),
                          "schema_valid_rate_all_attempts": sum(r["schema_valid"] for r in group) / len(group),
                          "latency_n": len(latency), "median_request_s": statistics.median(latency) if latency else None,
                          "p95_request_s": percentile(latency, .95), "sampled_gpu_peak_mib": max(peaks) if peaks else None,
                          "tag_scored_attempts": len(scored), "empty_tag_outputs": sum(r["output_tag_count"] == 0 for r in scored),
                          "allowed_tag_match_rate_n": len(match_rates),
                          "mean_allowed_tag_match_rate": statistics.mean(match_rates) if match_rates else None,
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
                      "허용 태그 일치율 평균 · 참고": s["mean_allowed_tag_match_rate"],
                      "평균에 포함한 요청 수": s["allowed_tag_match_rate_n"]} for s in summaries]
    score_details = [{"조건": r["profile"], "샘플": r["case_id"],
                      "허용 태그 일치율 · 참고": r["allowed_tag_match_rate"],
                      "일치 태그": r["matched_allowed_tags"],
                      "미등록 태그 · 사람 확인": r["unmatched_tags"]} for r in metrics if r["tag_score_evaluated"]]
    title = "MOCK · 실행 경로 확인용, 모델 성능 결과 아님" if mock else "filename A/B 실험 결과"
    content = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{max-width:1200px;margin:40px auto;padding:0 24px;font:16px/1.65 system-ui;color:#163047;background:#f7f9fc}}
h1{{font-size:28px}} .notice{{background:#fff2cc;padding:16px;border-radius:8px}}.table{{overflow:auto;background:white}}
table{{border-collapse:collapse;font-size:13px}}td,th{{padding:10px;border:1px solid #dae1e8;white-space:nowrap}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;padding:16px}}details{{margin:12px 0}}a{{color:#1253a4}}</style>
<h1>{title}</h1><div class="notice">계획 측정 요청 {config['planned_requests']}개 · 저장된 시도 {len(rows)}개 · 고유 요청 {len({r['job_id'] for r in rows})}개 · 로드 이벤트 {len(events)}개.
실패·재시도도 비율의 분모에 포함합니다. 계획 대비 누락과 아래 오류를 함께 확인하세요.</div>
<p>참조 답안의 독립 사람 검수: {esc(config.get('reference_human_reviewed'))}. 허용 태그 일치율은 참고값입니다.
최종 품질은 사람이 태그 정확성·파일명 활용도·관찰 근거·행동 변화를 보고 평가합니다.
미등록 표현은 목록에 없는 동의어일 수도 있으므로 사람이 확인합니다.
B의 용량 실험은 의미 품질 평가에서 제외합니다. 모의 실행 수치로 실제 속도·메모리를 판단하지 마세요.</p>
<p><a href="summary.csv">조건별 요약</a> · <a href="metrics.csv">요청별 수치</a> · <a href="review.csv">사람 평가표</a> · <a href="requests.jsonl">응답 원문</a> · <a href="eda.json">데이터 점검</a></p>
<h2>허용 태그 일치율 · 참고값</h2>{table(score_summary)}
<p>범위는 0~1입니다. 일치율 = 허용 목록에 있는 출력 태그 수 / 출력 태그 수.
계산식은 Precision(정밀도)과 같지만 장면 이해나 파일명 유용성의 최종 점수로 사용하지 않습니다.
정답 후보가 100개라도 출력 5개가 모두 목록에 있으면 1입니다.
정상 실행·형식 통과·정답 존재 조건을 만족하는 요청만 채점합니다. 모의 실행·B 용량 실험은 제외합니다.
평균은 계산 가능한 요청별 일치율의 산술평균입니다. 빈 출력은 null이며 평균에서 제외합니다.
빈 출력 수, 평균에 포함한 요청 수, 형식·실행 실패율도 함께 보세요. 계산 버전: {SCORING_VERSION}.</p>
<h2>태그별 매칭 근거</h2>{table(score_details)}
<h2>조건별 실행 결과</h2>{table(summaries)}{chart}
<p>시간은 모델 로드를 제외한 요청 시간이며 첫 요청을 포함합니다. HTTP 방식에서는 대기 시간도 포함합니다.
GPU 메모리는 장치 전체의 표본 측정값이며 동시 요청에서 각 요청의 전용 메모리가 아닙니다. null은 측정 불가입니다.</p>
<h2>시작·오류 기록</h2><pre>{esc(json.dumps(events, ensure_ascii=False, indent=2))}</pre>
<h2>응답 확인</h2>{details}<h2>평가 방법</h2>
<p>review.csv에서 tag_accuracy_0to2는 0=장면과 맞지 않음, 1=일부 오류·모호함, 2=관찰과 일치로 평가합니다.
filename_usefulness_0to2는 0=찾는 데 도움 없음, 1=일부 수정 필요, 2=그대로 활용 가능입니다.
빈 태그 응답의 정확성은 빈칸, 활용도는 0으로 기록합니다. unsupported_claim_0or1은 근거 없는 주장이 있으면 1입니다.
영상 변화는 0=오류·누락, 1=일부, 2=충분히 반영입니다. 사진이나 변화가 없는 영상은 해당 칸을 비웁니다.
사람 평가 입력은 리포트 재생성 시 보존되며, 이 예제는 사람 점수를 자동 합산하지 않습니다.</p>
<p>Based-On: none · project_extension · 실제 결과는 실행 환경과 참조 답안 검수 범위 내에서만 해석하세요.</p></html>"""
    (root / "report.html").write_text(content, encoding="utf-8")
    return root / "report.html"
