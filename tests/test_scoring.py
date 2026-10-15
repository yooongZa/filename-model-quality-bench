"""일치율의 분모, 제외 조건, 사람 평가와 원문 보존을 검사합니다."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from filename_bench.common import ROOT, load_config, read_json, write_json
from filename_bench.report import build_report
from filename_bench.runner import run
from filename_bench.scoring import reference_tags, score_tags


def reference():
    return {"keywords": ["자전거", "바다", "해변", "야외", "도로", "자전거 타기",
                         "사이클링", "자전거 라이딩", "해안도로", "바닷가 도로"],
            "reason": "바다가 보이는 도로에서 자전거를 타고 이동합니다.",
            "place_name": None}


class TagScoringTest(unittest.TestCase):
    def test_hundred_allowed_tags_five_matches_is_one(self):
        answer = reference()
        answer["keywords"] = [f"허용태그{i}" for i in range(100)]
        score = score_tags([f"허용태그{i}" for i in range(5)], answer)
        self.assertEqual(score["allowed_reference_tag_count"], 100)
        self.assertEqual(score["allowed_tag_match_rate"], 1)

    def test_registered_variations_match(self):
        score = score_tags(["사이클링", "바닷가도로", "바다", "야외"], reference())
        self.assertEqual(score["allowed_tag_match_rate"], 1)
        self.assertEqual(score["unmatched_tags"], [])

    def test_unregistered_tags_are_listed_for_human_review(self):
        score = score_tags(["사이클링", "기차"], reference())
        self.assertEqual(score["allowed_tag_match_rate"], .5)
        self.assertEqual(score["unmatched_tags"], ["기차"])

    def test_more_reference_tags_do_not_change_denominator(self):
        answer = reference()
        before = score_tags(["사이클링", "해안도로"], answer)
        answer["keywords"] += [f"추가태그{i}" for i in range(100)]
        after = score_tags(["사이클링", "해안도로"], answer)
        self.assertEqual(before["allowed_tag_match_rate"], after["allowed_tag_match_rate"])

    def test_empty_output_is_not_a_perfect_match(self):
        self.assertIsNone(score_tags([], reference())["allowed_tag_match_rate"])
        answer = reference()
        answer["keywords"] = []
        self.assertEqual(score_tags(["바다"], answer)["allowed_tag_match_rate"], 0)

    def test_legacy_extra_fields_are_ignored(self):
        answer = reference()
        answer.update(needs_review=False, core_keywords=[["기차"]])
        self.assertEqual(score_tags(["기차"], answer)["allowed_tag_match_rate"], 0)

    def test_normalization_without_substring_or_semantic_guessing(self):
        import unicodedata
        answer = reference()
        answer["keywords"] += ["MTB"]
        score = score_tags([unicodedata.normalize("NFD", "바다"), "m t b", "바다가 아님", "대양"], answer)
        self.assertEqual(score["allowed_tag_match_rate"], .5)
        self.assertEqual(score["unmatched_tags"], ["바다가 아님", "대양"])

    def test_invalid_reference_fields_are_rejected(self):
        for field, value in [("keywords", [" "]), ("keywords", "바다"), ("keywords", [1]),
                             ("reason", ""), ("place_name", True)]:
            answer = reference()
            answer[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                reference_tags(answer)


class ScoringReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.output = self.root / "run"
        self.output.mkdir()
        write_json(self.output / "config.json", {"identity": {"mock": False}, "planned_requests": 6})
        write_json(self.output / "references.json", {"answers": {"V01": reference()}, "annotations": []})
        rows = []
        # 응답 저장 형식만 흉내 내는 테스트 fixture(고정 입력)입니다. 모델 측정이 아닙니다.
        for index, tags in enumerate([["사이클링", "해안도로", "바다", "야외"], ["사이클링", "기차"], [],
                                      ["사이클링"], ["사이클링"], ["사이클링"]]):
            parsed = {"keywords": tags, "reason": "테스트 응답", "place_name": None}
            rows.append({"attempt_id": str(index), "job_id": str(index), "profile": "baseline",
                         "case_id": "missing" if index == 5 else "V01", "media_type": "video",
                         "execution_status": "timeout" if index == 4 else "ok",
                         "json_valid": True, "schema_valid": index != 3,
                         "raw_output": json.dumps(parsed, ensure_ascii=False), "parsed": parsed,
                         "setting": {}, "wave_metrics": {}})
        self.raw = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        (self.output / "requests.jsonl").write_text(self.raw)

    def tearDown(self):
        self.temp.cleanup()

    def csv_rows(self, name):
        with (self.output / name).open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    def test_summary_denominators_evidence_and_review_preservation(self):
        build_report(self.output, self.data)
        summary = read_json(self.output / "summary.json")[0]
        self.assertEqual(summary["tag_scored_attempts"], 3)
        self.assertEqual(summary["empty_tag_outputs"], 1)
        self.assertEqual(summary["allowed_tag_match_rate_n"], 2)
        self.assertEqual(summary["mean_allowed_tag_match_rate"], .75)
        metrics = self.csv_rows("metrics.csv")
        for field in list(summary) + list(metrics[0]):
            self.assertFalse(any(old in field.split("_") for old in ("precision", "recall", "core")) or "needs_review" in field)
        self.assertEqual(json.loads(metrics[1]["unmatched_tags"]), ["기차"])
        self.assertEqual(metrics[3]["allowed_tag_match_rate"], "")
        self.assertEqual(metrics[4]["allowed_tag_match_rate"], "")
        self.assertEqual(metrics[5]["allowed_tag_match_rate"], "")
        self.assertIn("미등록 태그", (self.output / "report.html").read_text())
        reviews = self.csv_rows("review.csv")
        for field in reviews[0]:
            self.assertFalse(any(old in field.split("_") for old in ("precision", "recall", "core")) or "needs_review" in field)
        reviews[0]["notes"] = "사람 검수 기록"
        reviews[0]["tag_accuracy_0to2"] = "2"
        reviews[0]["filename_usefulness_0to2"] = "1"
        with (self.output / "review.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=reviews[0].keys())
            writer.writeheader()
            writer.writerows(reviews)
        # 실행 후 원본 정답이 바뀌어도 당시 저장한 기준으로 계속 채점합니다.
        changed = reference()
        changed["keywords"] = ["기차"]
        write_json(self.data / "answers/V01.json", changed)
        build_report(self.output, self.data)
        self.assertEqual(read_json(self.output / "summary.json")[0], summary)
        self.assertEqual(self.csv_rows("review.csv")[0]["notes"], "사람 검수 기록")
        self.assertEqual(self.csv_rows("review.csv")[0]["tag_accuracy_0to2"], "2")
        self.assertEqual(self.csv_rows("review.csv")[0]["filename_usefulness_0to2"], "1")
        self.assertEqual((self.output / "requests.jsonl").read_text(), self.raw)

    def test_mock_and_capacity_runs_have_no_tag_scores(self):
        for mock, capacity in [(True, False), (False, True)]:
            write_json(self.output / "config.json", {"identity": {"mock": mock}, "planned_requests": 6})
            rows = [json.loads(line) for line in self.raw.splitlines()]
            for row in rows:
                row["capacity_only"] = capacity
            (self.output / "requests.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
            build_report(self.output, self.data)
            summary = read_json(self.output / "summary.json")[0]
            self.assertEqual(summary["tag_scored_attempts"], 0)
            self.assertIsNone(summary["mean_allowed_tag_match_rate"])

    def test_bad_reference_fails_before_model_loading(self):
        (self.data / "images").mkdir(parents=True)
        Image.new("RGB", (16, 16), "blue").save(self.data / "images/I01.png")
        bad = reference()
        bad["keywords"] = ["바다", "  "]
        write_json(self.data / "answers/I01.json", bad)
        config = load_config(ROOT / "configs/a_quality.json")
        config.update(dataset_root=str(self.data), run_dir=str(self.output / "new"))
        with patch("filename_bench.runner.make_backend") as backend:
            with self.assertRaisesRegex(ValueError, "answers/I01.json"):
                run(config, "a", mock=True)
            backend.assert_not_called()

    def test_large_reference_is_saved_and_resume_keeps_it(self):
        (self.data / "images").mkdir(parents=True)
        Image.new("RGB", (16, 16), "blue").save(self.data / "images/I01.png")
        answer = reference()
        answer["keywords"] += [f"허용표현{i}" for i in range(100)]
        write_json(self.data / "answers/I01.json", answer)
        config = load_config(ROOT / "configs/a_quality.json")
        config.update(dataset_root=str(self.data), run_dir=str(self.output / "new"))
        result = run(config, "a", mock=True)
        directory = Path(result["run_dir"])
        self.assertEqual(read_json(directory / "references.json")["answers"]["I01"], answer)
        self.assertEqual(run(config, "a", mock=True, resume=True)["recorded_attempts"], 1)
        self.assertIsNone(read_json(directory / "summary.json")[0]["mean_allowed_tag_match_rate"])


if __name__ == "__main__":
    unittest.main()
