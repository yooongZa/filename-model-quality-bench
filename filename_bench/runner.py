"""설정별 실험 계획 → 모델 호출 → 원문 저장 → 리포트 생성 순서로 실행합니다."""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import copy
import json
import time
import uuid
from pathlib import Path

from .backends import classify_error, make_backend
from .common import (ROOT, BenchError, RunLock, append_row, digest, environment,
                     file_hash, load_config, read_json, read_rows, validate_output, write_json)
from .data import eda, load_cases, prepare
from .telemetry import Monitor

FATAL = {"oom", "timeout", "cancelled", "backend_error"}


def profiles(cfg, kind, suite):
    """suite(실험 묶음)에 맞게 기준 설정에서 한 가지 조건씩 바꿉니다."""
    base = cfg["baseline"]
    out = []

    def add(name, changes=None, media=None, n=None, context_probe=False):
        out.append({"name": name, "setting": {**base, **(changes or {})}, "media": media,
                    "requests": n, "context_probe": context_probe})

    if kind == "a":
        if suite == "smoke":
            add("smoke_photo", media="image")
            add("smoke_video", media="video")
        elif suite == "baseline":
            add("baseline")
        elif suite == "resolution":
            for n in cfg["sweeps"]["short_edge_px"]:
                add(f"resolution_{n}", {"short_edge_px": n})
        elif suite == "vision":
            for n in cfg["sweeps"]["vision_token_budget"]:
                add(f"vision_{n}", {"vision_token_budget": n})
        elif suite == "output":
            for n in cfg["sweeps"]["max_new_tokens"]:
                add(f"output_{n}", {"max_new_tokens": n})
        elif suite == "frames":
            for n in cfg["sweeps"]["frames"]:
                add(f"frames_{n}", {"frames": n}, "video")
        elif suite == "selection":
            for policy in ["uniform", "blur", "dedup", "both"]:
                add(f"selection_{policy}", {"frames": 6, "selection": policy}, "video")
        else:
            raise ValueError("A suite: smoke, baseline, resolution, vision, output, frames, selection")
    else:
        repeats = cfg.get("rounds_per_profile", 3)
        if suite == "smoke":
            add("local_photo", {"frames": 1}, "image", 1)
            add("local_video", media="video", n=1)
        elif suite == "context":
            for ctx in cfg["sweeps"]["context_per_request"]:
                add(f"context_{ctx}", {"context_per_request": ctx, "frames": 1}, "image", repeats, True)
        elif suite == "images":
            for n in cfg["sweeps"]["frames"]:
                add(f"images_{n}", {"frames": n}, "video", repeats)
        elif suite == "concurrency":
            for c in cfg["sweeps"]["concurrency"]:
                add(f"concurrency_{c}", {"concurrency": c}, None, repeats * c)
        elif suite == "soak":
            add("reuse", {"concurrency": 1}, None, cfg["reuse_requests"])
        else:
            raise ValueError("B suite: smoke, context, images, concurrency, soak")
    return out


def safe_call(backend, images, prompt, setting, seed, schema):
    started = time.perf_counter()
    try:
        response = backend.infer(images, prompt, setting, seed)
        fmt = validate_output(response["raw_output"], schema)
        finish = response.get("finish_reason")
        status = "timeout" if finish == "timeout" else "truncated" if finish == "length" else "ok"
        if response.get("input_truncated_reported"):
            status = "truncated"
        return {**response, **fmt, "execution_status": status,
                "request_wall_s": time.perf_counter() - started}
    except Exception as e:
        return {"execution_status": e.status if isinstance(e, BenchError) else classify_error(str(e)),
                "error": f"{type(e).__name__}: {e}", "raw_output": None, "parsed": None,
                "json_valid": False, "schema_valid": False, "request_wall_s": time.perf_counter() - started}


def execute_wave(backend, jobs, schema, gpu_index=0):
    """All requests are immutable copies. On fatal failure, stop owned work before returning."""
    results = {}
    # Keep single-request CUDA generation on the calling thread so Ctrl+C unwinds
    # inference before the model is released. Concurrency applies only to B/mock.
    if len(jobs) == 1:
        job = jobs[0]
        start = time.perf_counter()
        monitor = Monitor(backend, gpu_index=gpu_index)
        try:
            with monitor:
                results[job["job_id"]] = safe_call(backend, job["images"], job["prompt"], job["setting"], job["seed"], schema)
        except KeyboardInterrupt:
            results[job["job_id"]] = {"execution_status": "cancelled", "raw_output": None,
                                      "json_valid": False, "schema_valid": False, "parsed": None}
        if results[job["job_id"]]["execution_status"] in FATAL:
            backend.close()
        return results, {"wave_wall_s": time.perf_counter() - start, "wave_request_count": 1,
                         **monitor.summary()}, monitor.samples
    pool = cf.ThreadPoolExecutor(max_workers=len(jobs))
    futures = {}
    start = time.perf_counter()
    monitor = Monitor(backend, gpu_index=gpu_index)
    try:
        with monitor:
            for job in jobs:
                futures[pool.submit(safe_call, backend, job["images"], job["prompt"],
                                    copy.deepcopy(job["setting"]), job["seed"], schema)] = job
            for future in cf.as_completed(futures):
                job = futures[future]
                row = future.result()
                results[job["job_id"]] = row
                if row["execution_status"] in FATAL:
                    # Aborting a client alone does not cancel work on a model server.
                    backend.close()
    except KeyboardInterrupt:
        backend.close()
        for future in futures:
            future.cancel()
        for job in jobs:
            results.setdefault(job["job_id"], {"execution_status": "cancelled", "raw_output": None,
                                               "json_valid": False, "schema_valid": False, "parsed": None})
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return results, {"wave_wall_s": time.perf_counter() - start, "wave_request_count": len(jobs),
                     **monitor.summary()}, monitor.samples


def make_jobs(profile, cases, cfg, run_key, kind):
    selected = [c for c in cases if profile["media"] is None or c["media_type"] == profile["media"]]
    if not selected:
        raise ValueError(f"No cases available for {profile['name']}")
    jobs = []
    if kind == "a":
        inputs = [(case, seed, rep) for rep in range(cfg.get("repeats", 1))
                  for seed in cfg.get("seeds", [42]) for case in selected]
    else:
        inputs = [(selected[i % len(selected)], cfg.get("seeds", [42])[0], i)
                  for i in range(profile["requests"])]
    for case, seed, rep in inputs:
        key = {"run": run_key, "profile": profile["name"], "case": case["id"], "hashes": case["sha256"],
               "setting": profile["setting"], "seed": seed, "repeat": rep}
        jobs.append({"job_id": digest(key), "case": case, "case_id": case["id"], "seed": seed,
                     "repeat": rep, "setting": profile["setting"], "profile": profile["name"]})
    return jobs


def run(cfg, kind, suite="smoke", mock=False, resume=False, limit=None, dry_run=False):
    """실험의 전체 흐름입니다. mock=True이면 GPU 없이 저장·검사만 확인합니다."""
    # 1. 입력과 출력 규칙을 읽고, 업로드된 데이터 종류에 맞는 실험을 선택합니다.
    cases, manifest = load_cases(cfg["dataset_root"], cfg.get("case_ids"), cfg.get("video_extraction"))
    prompt = Path(cfg["prompt_path"]).read_text(encoding="utf-8")
    schema = read_json(cfg["schema_path"])
    plan = profiles(cfg, kind, suite)
    available_media = {case["media_type"] for case in cases}
    skipped = [p["name"] for p in plan if p["media"] and p["media"] not in available_media]
    plan = [p for p in plan if p["name"] not in skipped]
    if not plan:
        raise ValueError(f"{suite} 실험에 필요한 종류의 입력이 없습니다. 사진/영상 폴더를 확인하세요.")
    if kind == "a" and any(p["setting"]["concurrency"] != 1 for p in plan):
        raise ValueError("A example supports sample_batch_size=1 and concurrency=1 only")
    for p in plan:
        s = p["setting"]
        if (s["concurrency"] < 1 or (s["frames"] != "all" and (type(s["frames"]) is not int or s["frames"] < 1))
                or s["max_new_tokens"] < 1 or s["short_edge_px"] < 1):
            raise ValueError("Counts and image sizes must be positive")
        if s["vision_token_budget"] not in [70, 140, 280, 560, 1120]:
            raise ValueError("Gemma 4 vision token budget must be 70/140/280/560/1120")
    # 2. 입력·설정·코드의 해시로 이번 실험을 구분합니다. 조건이 달라지면 새 실험입니다.
    data_key = digest([{k: v for k, v in c.items() if k != "paths"} for c in cases])
    code_key = digest({str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT / "filename_bench").glob("*.py"))})
    dataset_root = Path(cfg["dataset_root"])
    reference_paths = [dataset_root / "answers" / f"{c['id']}.json" for c in cases]
    annotation_path = dataset_root / "reviewer/annotation_notes.json"
    references = {"answers": {p.stem: read_json(p) for p in reference_paths if p.exists()},
                  "annotations": read_json(annotation_path) if annotation_path.exists() else [],
                  "human_reviewed": manifest.get("human_reviewed", False)}
    identity = {"kind": kind, "suite": suite, "mock": mock,
                "config": {k: v for k, v in cfg.items() if k != "run_dir"}, "data_key": data_key,
                "prompt_hash": file_hash(cfg["prompt_path"]), "schema_hash": file_hash(cfg["schema_path"]),
                "code_hash": code_key, "reference_hash": digest(references)}
    run_key = digest(identity)
    planned = sum(len(make_jobs(p, cases, cfg, run_key, kind)) for p in plan)
    if dry_run:
        result = {"planned_requests": planned, "context_calibration_requests_extra": sum(p["context_probe"] for p in plan),
                  "profiles": plan, "skipped_profiles_no_media": skipped,
                  "eda": eda(cases, manifest), "mock": mock}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    directory = Path(cfg["run_dir"]) / (suite + ("_mock" if mock else ""))
    directory.mkdir(parents=True, exist_ok=True)
    with RunLock(directory):
        meta_path = directory / "config.json"
        if meta_path.exists():
            if not resume:
                raise ValueError(f"Run already exists: {directory}. Use --resume or a new run_dir.")
            if read_json(meta_path)["run_key"] != run_key:
                raise ValueError("Config, input, prompt, or code changed. Use a new run_dir.")
        else:
            write_json(meta_path, {"run_key": run_key, "identity": identity, "environment": environment(),
                                   "planned_requests": planned, "skipped_profiles_no_media": skipped,
                                   "reference_human_reviewed": manifest.get("human_reviewed", False)})
            write_json(directory / "eda.json", eda(cases, manifest))
            write_json(directory / "references.json", references)
            write_json(directory / "video_extraction.json", {
                c["id"]: {"source_video": c["video_path"], **c["video_extraction"]}
                for c in cases if "video_extraction" in c})
        records_path = directory / "requests.jsonl"
        old = read_rows(records_path)
        # Valid and invalid model responses are completed measurements. Infrastructure errors can retry.
        complete = {r["job_id"] for r in old if r.get("execution_status") in ["ok", "truncated", "input_too_long", "unsupported"]}
        if kind == "b" and suite == "soak" and old and len(complete) < planned:
            raise ValueError("A soak test must use one uninterrupted model process. Use a new run_dir to restart it.")
        # 3. 모델을 준비하고 요청합니다. 원문과 오류를 모두 남겨 실패도 평가에 포함합니다.
        backend = make_backend(cfg["backend"], mock)
        recorded, stop, attempted_in_session = len(old), False, 0
        session_id = uuid.uuid4().hex[:12]
        try:
            for profile in plan:
                jobs = [j for j in make_jobs(profile, cases, cfg, run_key, kind) if j["job_id"] not in complete]
                if limit is not None:
                    jobs = jobs[:max(0, limit - attempted_in_session)]
                if not jobs:
                    continue
                setting = profile["setting"]
                try:
                    backend.start(setting, directory / f"server_{profile['name']}_{session_id}.log")
                except Exception as e:
                    append_row(directory / "events.jsonl", {"profile": profile["name"], "phase": "load",
                        "execution_status": e.status if isinstance(e, BenchError) else classify_error(str(e)), "error": str(e)})
                    print(f"{profile['name']}: load failed: {e}")
                    stop = True
                    break
                stable_info = {k: v for k, v in backend.info.items() if k in [
                    "backend", "model", "resolved_revision", "dtype", "model_sha256", "projector_sha256", "server_sha256"]}
                identity_path = directory / "backend_identity.json"
                if identity_path.exists() and read_json(identity_path) != stable_info:
                    raise ValueError("Resolved model/server changed since prior run. Use a new run_dir.")
                write_json(identity_path, stable_info)
                info_path = directory / f"backend_{profile['name']}_{session_id}.json"
                write_json(info_path, backend.info)
                print(f"{profile['name']}: {len(jobs)} requests", flush=True)
                padded = prompt
                if profile["context_probe"]:
                    first = jobs[0]
                    images, _ = prepare(first["case"], setting)
                    calibration = safe_call(backend, images, prompt, setting, first["seed"], schema)
                    append_row(directory / "calibration.jsonl", {"profile": profile["name"], **calibration})
                    if calibration["execution_status"] != "ok":
                        stop = True
                        break
                    target = min(int(setting["context_per_request"] * cfg.get("context_fill_fraction", 0.75)),
                                 setting["context_per_request"] - setting["max_new_tokens"] - 32)
                    measured = calibration.get("input_tokens")
                    if measured is None and not mock:
                        raise BenchError("unsupported", "Context probe requires actual prompt_tokens from the server")
                    padded = backend.pad_prompt(prompt, max(0, target - (measured or 0)))
                c = setting["concurrency"]
                profile_completed = 0
                for offset in range(0, len(jobs), c):
                    wave, failed_preparation = [], []
                    for job in jobs[offset:offset + c]:
                        start = time.perf_counter()
                        try:
                            images, media = prepare(job["case"], setting)
                            wave.append({**job, "images": images, "media": media, "prompt": padded,
                                         "preprocess_s": time.perf_counter() - start})
                        except Exception as e:
                            failed_preparation.append((job, e))
                    for job, error in failed_preparation:
                        row = {k: v for k, v in job.items() if k != "case"}
                        row.update(attempt_id=uuid.uuid4().hex, session_id=session_id, mode=kind, mock=mock,
                                   phase="prepare", media_type=job["case"]["media_type"],
                                   execution_status=error.status if isinstance(error, BenchError) else "backend_error",
                                   error=str(error), json_valid=False, schema_valid=False, parsed=None,
                                   raw_output=None, capacity_only=kind == "b")
                        append_row(records_path, row)
                        recorded += 1
                        attempted_in_session += 1
                    if not wave:
                        continue
                    results, metrics, samples = execute_wave(backend, wave, schema, cfg.get("gpu_index", 0))
                    wave_id = uuid.uuid4().hex[:12]
                    append_row(directory / "telemetry.jsonl", {"wave_id": wave_id, "profile": profile["name"],
                                                               "samples": samples, "summary": metrics})
                    for job in wave:
                        result = results[job["job_id"]]
                        info = {k: v for k, v in job.items() if k not in ["case", "images", "prompt"]}
                        n_input = result.get("input_tokens")
                        effective = backend.info.get("effective_context", setting["context_per_request"])
                        occupancy = n_input / effective if n_input is not None and effective else None
                        profile_completed += 1
                        row = {**info, **result, "attempt_id": uuid.uuid4().hex, "session_id": session_id,
                               "mode": kind, "mock": mock, "media_type": job["case"]["media_type"],
                               "backend_metadata": info_path.name, "wave_id": wave_id, "wave_metrics": metrics,
                               "prompt_hash_actual": digest(padded), "effective_context": effective,
                               "context_occupancy": occupancy,
                               "context_load_confirmed": bool(profile["context_probe"] and not mock and occupancy is not None
                                    and occupancy >= cfg.get("context_fill_fraction", .75) - .05
                                    and result["execution_status"] == "ok"
                                    and n_input + setting["max_new_tokens"] <= effective),
                               "capacity_only": kind == "b", "reuse_index_this_process_profile": profile_completed,
                               "sample_batch_size": 1, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
                        append_row(records_path, row)
                        recorded += 1
                        attempted_in_session += 1
                        print(f"  {recorded}: {job['case_id']} {row['execution_status']} schema={row['schema_valid']}", flush=True)
                    if any(r["execution_status"] in FATAL for r in results.values()):
                        stop = True
                        break
                if kind == "b":
                    backend.close()
                if stop or (limit is not None and attempted_in_session >= limit):
                    break
        finally:
            backend.close()
            from .report import build_report
            build_report(directory, cfg["dataset_root"])
        print(f"Report: {directory / 'report.html'}", flush=True)
        return {"run_dir": str(directory), "recorded_attempts": recorded, "stopped_on_error": stop}


def main(kind):
    """터미널 옵션을 읽는 곳입니다. 실험값은 configs/ 또는 옵션에서 바꾸세요."""
    parser = argparse.ArgumentParser(description=f"filename {kind.upper()} benchmark example")
    parser.add_argument("--config", default=str(ROOT / "configs" / ("a_quality.json" if kind == "a" else "b_local.json")))
    parser.add_argument("--suite", default="smoke")
    parser.add_argument("--dataset-root", help="업로드 또는 압축 해제한 평가 데이터 폴더")
    parser.add_argument("--run-dir", help="새 결과 폴더. 조건을 바꾸면 이 경로도 바꾸세요.")
    parser.add_argument("--frames", help="모델 입력 프레임 수. all이면 준비된 프레임을 모두 사용")
    parser.add_argument("--seconds-per-frame", type=float, help="원본 영상에서 몇 초당 한 장을 추출할지")
    parser.add_argument("--max-frames", type=int, help="원본 영상 한 개의 최대 추출 장수")
    parser.add_argument("--mock", action="store_true", help="GPU 없이 고정 응답으로 저장·검사·리포트 확인")
    parser.add_argument("--resume", action="store_true", help="같은 조건에서 완료한 요청을 건너뛰고 재개")
    parser.add_argument("--dry-run", action="store_true", help="모델 로드 없이 데이터와 요청 수만 확인")
    parser.add_argument("--limit", type=int, help="이번 실행의 최대 측정 요청 수. 컨텍스트 보정 요청은 별도")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    config = load_config(args.config)
    if args.frames:
        try:
            config["baseline"]["frames"] = "all" if args.frames == "all" else int(args.frames)
        except ValueError:
            parser.error("--frames에는 양의 정수 또는 all을 입력하세요.")
    for key in ("seconds_per_frame", "max_frames"):
        value = getattr(args, key)
        if value is not None:
            config.setdefault("video_extraction", {})[key] = value
    if args.dataset_root:
        config["dataset_root"] = str(Path(args.dataset_root).resolve())
    if args.run_dir:
        config["run_dir"] = str(Path(args.run_dir).resolve())
    result = run(config, kind, args.suite, args.mock, args.resume, args.limit, args.dry_run)
    if result.get("stopped_on_error"):
        raise SystemExit(1)
