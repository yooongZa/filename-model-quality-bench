"""CPU-only regression checks for experiment boundaries, not model quality."""
import copy
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image

from filename_bench.backends import LlamaBackend, MockBackend
from filename_bench.common import ROOT, BenchError, load_config, read_json, read_rows, validate_output, write_json
from filename_bench.data import load_cases, prepare, select_frames, uniform_indices
from filename_bench.report import build_report
from filename_bench.runner import execute_wave, profiles, run


class ExamplesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        rows = []
        for case, media, count in [("I01", "image", 1), ("V01", "video", 12)]:
            names = []
            for i in range(count):
                name = f"{case}_{i}.png"
                Image.new("RGB", (64, 48), (i * 10, 80, 140)).save(self.data / name)
                names.append(name)
            rows.append({"id": case, "media_type": media, "image_paths": names})
        (self.data / "model_inputs.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        self.cfg = load_config(ROOT / "configs/a_quality.json")
        self.cfg.update(dataset_root=str(self.data), run_dir=str(self.root / "runs"))
        self.schema = read_json(ROOT / "assets/schema_v3.json")
        self.setting = self.cfg["baseline"]


    def tearDown(self):
        self.temp.cleanup()


    def test_strict_output_contract(self):
        good = '{"keywords":["고양이"],"reason":"소파 위 고양이","place_name":null,"needs_review":false}'
        self.assertTrue(validate_output(good, self.schema)["schema_valid"])
        for bad in ["```json\n" + good + "\n```", good.replace('"needs_review":false', '"needs_review":"false"'),
                    good.replace('"고양이"', ','.join('"태그%d"' % i for i in range(6))),
                    good.replace('"place_name":null', '"place_name":null,"title":"제목"'),
                    good.replace('"place_name":null', '"place_name":null,"place_name":"서울"'),
                    good.replace('"place_name":null', '"place_name":NaN')]:
            self.assertFalse(validate_output(bad, self.schema)["schema_valid"], bad)


    def test_frame_selection_and_no_upscale(self):
        cases, _ = load_cases(self.data)
        video = cases[1]
        self.assertEqual(uniform_indices(12, 1), [6])
        for policy in ["uniform", "blur", "dedup", "both"]:
            chosen, _ = select_frames(video["paths"], 6, policy)
            self.assertEqual(chosen, sorted(set(chosen)))
            self.assertEqual(len(chosen), 6)
            for i, n in enumerate(chosen):
                self.assertTrue(i * 2 <= n < (i + 1) * 2)
        _, details = select_frames(video["paths"], 6, "dedup")
        self.assertGreater(details["fallback_count"], 0)
        prepared, meta = prepare(video, {**self.setting, "short_edge_px": 1080, "frames": 3})
        self.assertEqual(meta["prepared_sizes_wh"], [[64, 48]] * 3)
        self.assertEqual(len(prepared), 3)
        with self.assertRaises(BenchError):
            prepare(video, {**self.setting, "frames": 24})


    def test_one_factor_sweeps(self):
        for suite, changed in [("resolution", "short_edge_px"), ("vision", "vision_token_budget"),
                               ("output", "max_new_tokens"), ("frames", "frames")]:
            for p in profiles(self.cfg, "a", suite):
                for key in self.setting:
                    if key != changed:
                        self.assertEqual(p["setting"][key], self.setting[key])


    def test_resume_and_review_preservation(self):
        first = run(self.cfg, "a", mock=True, limit=1)
        second = run(self.cfg, "a", mock=True, resume=True)
        self.assertEqual(first["recorded_attempts"], 1)
        self.assertEqual(second["recorded_attempts"], 3)
        directory = Path(second["run_dir"])
        rows = read_rows(directory / "requests.jsonl")
        self.assertEqual(len({r["job_id"] for r in rows}), 3)
        with (directory / "review.csv").open(encoding="utf-8-sig", newline="") as f:
            reviews = list(csv.DictReader(f))
        reviews[0]["notes"] = "사람 검수 기록 유지"
        with (directory / "review.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(reviews[0]))
            writer.writeheader(); writer.writerows(reviews)
        build_report(directory, self.data)
        self.assertIn("사람 검수 기록 유지", (directory / "review.csv").read_text(encoding="utf-8-sig"))
        self.assertIn("모델 성능 결과 아님", (directory / "report.html").read_text())
        Image.new("RGB", (64, 48), "red").save(self.data / "I01_0.png")
        with self.assertRaisesRegex(ValueError, "changed"):
            run(self.cfg, "a", mock=True, resume=True)


    def jobs(self, n=2):
        return [{"job_id": str(i), "images": (bytes([i]),), "prompt": "test", "setting": copy.deepcopy(self.setting),
                 "seed": i} for i in range(n)]


    def test_cancelled_single_request(self):
        class Cancel(MockBackend):
            def infer(self, *args):
                raise KeyboardInterrupt
        result, _, _ = execute_wave(Cancel({}), self.jobs(1), self.schema)
        self.assertEqual(result["0"]["execution_status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
