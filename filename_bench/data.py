"""Deterministic frame selection and resizing from originals. Never edits source media."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .common import BenchError, file_hash, read_json, read_rows


def load_cases(root, ids=None):
    root = Path(root)
    rows = read_rows(root / "model_inputs.jsonl")
    if not rows:
        raise ValueError(f"No model_inputs.jsonl rows: {root}")
    all_ids = [r["id"] for r in rows]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Duplicate sample IDs")
    if ids and set(ids) - set(all_ids):
        raise ValueError(f"Unknown case IDs: {set(ids) - set(all_ids)}")
    manifest = read_json(root / "manifest.json") if (root / "manifest.json").exists() else {}
    frame_meta = {f["path"]: f for row in manifest.get("files", []) for f in row.get("frames", [])}
    cases = []
    for row in rows:
        if ids and row["id"] not in ids:
            continue
        paths = [(root / p).resolve() for p in row["image_paths"]]
        if not paths or any(not p.is_relative_to(root.resolve()) or not p.is_file() for p in paths):
            raise ValueError(f"Missing or out-of-root input: {row['id']}")
        if row["media_type"] not in ["image", "video"]:
            raise ValueError(f"Unknown media_type: {row['id']}")
        if row["media_type"] == "image" and len(paths) != 1:
            raise ValueError("A photo case must have one image")
        hashes = [file_hash(p) for p in paths]
        cases.append({**row, "paths": paths, "sha256": hashes,
                      "timestamps_s": [frame_meta.get(p, {}).get("requested_time_s") for p in row["image_paths"]]})
    return cases, manifest


def uniform_indices(n, k):
    if k < 1 or k > n:
        raise BenchError("unsupported", f"Requested {k} distinct frames; only {n} available")
    return [n // 2] if k == 1 else [round(i * (n - 1) / (k - 1)) for i in range(k)]


def frame_features(path):
    with Image.open(path) as image:
        gray = ImageOps.grayscale(ImageOps.exif_transpose(image))
        # Fixed analysis resolution makes blur scores comparable between candidates.
        gray.thumbnail((256, 256), Image.Resampling.LANCZOS)
        a = np.asarray(gray, dtype=np.float32)
        lap = -4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
        tiny = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS))
        bits = (tiny[:, 1:] > tiny[:, :-1]).reshape(-1)
        dhash = sum(int(b) << i for i, b in enumerate(bits))
        return float(lap.var()), dhash


def select_frames(paths, count, policy="uniform", duplicate_distance=6):
    anchors = uniform_indices(len(paths), count)
    if policy == "uniform":
        return anchors, {"policy": policy, "fallback_count": 0}
    if policy not in ["blur", "dedup", "both"]:
        raise ValueError(f"Unknown selection policy: {policy}")
    features = [frame_features(p) for p in paths]
    chosen, fallback = [], 0
    # One choice per time bin: filtering cannot remove the entire middle/end of a clip.
    for b in range(count):
        candidates = list(range(b * len(paths) // count, (b + 1) * len(paths) // count))
        center = (candidates[0] + candidates[-1]) / 2
        if policy in ["dedup", "both"]:
            eligible = [i for i in candidates if all(
                (features[i][1] ^ features[j][1]).bit_count() > duplicate_distance for j in chosen)]
            if not eligible:
                eligible, fallback = candidates, fallback + 1
        else:
            eligible = candidates
        if policy in ["blur", "both"]:
            pick = max(eligible, key=lambda i: (features[i][0], -abs(i - center), -i))
        else:
            pick = min(eligible, key=lambda i: (abs(i - center), i))
        chosen.append(pick)
    return chosen, {"policy": policy, "fallback_count": fallback,
                    "blur_scores": [round(x[0], 4) for x in features],
                    "dhash": [hex(x[1]) for x in features], "duplicate_distance": duplicate_distance}


def prepare(case, setting):
    count = 1 if case["media_type"] == "image" else setting["frames"]
    idx, selection = select_frames(case["paths"], count, setting["selection"])
    images, sizes, hashes = [], [], []
    for i in idx:
        with Image.open(case["paths"][i]) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            scale = min(1.0, setting["short_edge_px"] / min(image.size))
            size = tuple(max(1, round(x * scale)) for x in image.size)
            if size != image.size:
                image = image.resize(size, Image.Resampling.LANCZOS)
            stream = io.BytesIO()
            image.save(stream, format="PNG")
        content = stream.getvalue()
        import hashlib
        images.append(content)
        sizes.append(list(size))
        hashes.append(hashlib.sha256(content).hexdigest())
    meta = {"frame_indices_0based": idx, "timestamps_s": [case["timestamps_s"][i] for i in idx],
            "source_paths": [case["image_paths"][i] for i in idx], "source_sha256": [case["sha256"][i] for i in idx],
            "prepared_sha256": hashes, "prepared_sizes_wh": sizes, "selection_details": selection,
            "images_per_request": len(images)}
    return tuple(images), meta


def eda(cases, manifest):
    sizes = []
    for case in cases:
        for path in case["paths"]:
            with Image.open(path) as im:
                sizes.append(list(im.size))
    hashes = [h for c in cases for h in c["sha256"]]
    return {"cases": len(cases), "images": sum(c["media_type"] == "image" for c in cases),
            "videos": sum(c["media_type"] == "video" for c in cases), "input_pngs": len(hashes),
            "exact_duplicate_pngs": len(hashes) - len(set(hashes)), "sizes_wh": sizes,
            "case_ids": [c["id"] for c in cases], "condition_counts_full_dataset": manifest.get("condition_counts"),
            "reference_human_reviewed": manifest.get("human_reviewed", False)}
