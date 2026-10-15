"""FFmpeg 전처리 회귀 테스트입니다. 임시 영상은 프로그램 검사용이며 평가 데이터가 아닙니다."""
import io
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from filename_bench.common import ROOT, RunLock, file_hash, load_config, read_json, read_rows
from filename_bench.colab_storage import prepare_drive_dataset
from filename_bench.data import load_cases
from filename_bench.runner import run
from filename_bench.uploads import import_dataset_zip
from filename_bench.video import extract_video, sample_times


class SamplingTest(unittest.TestCase):
    def test_count_cap_and_bin_centers(self):
        for duration, expected in [(8, [4]), (20, [5, 15]),
                                   (50, [5, 15, 25, 35, 45]), (100, [10, 30, 50, 70, 90])]:
            self.assertEqual(sample_times(duration), expected)
        self.assertEqual(sample_times(10), [5])
        self.assertEqual(len(sample_times(10.1)), 2)
        for actual, expected in zip(sample_times(10.1), [2.525, 7.575]):
            self.assertAlmostEqual(actual, expected)

    def test_invalid_settings(self):
        for args in [(0, 10, 5), (float("nan"), 10, 5), (10, 0, 5), (10, 10, 0), (10, 10, 2.5)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                sample_times(*args)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg와 ffprobe가 필요합니다.")
class VideoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_temp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.source_temp.name) / "source.mp4"
        # 모델 품질과 관계없는 작은 움직이는 테스트 패턴을 임시 폴더에 만듭니다.
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
            "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=10:duration=5",
            "-c:v", "mpeg4", "-g", "100", "-threads", "1", str(cls.source),
        ], check=True, timeout=30, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.source_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "videos").mkdir()
        self.video = self.root / "videos/clip.mp4"
        shutil.copy2(self.source, self.video)
        self.options = {"seconds_per_frame": 1, "max_frames": 5}

    def tearDown(self):
        self.temp.cleanup()

    def test_real_extraction_and_cache_reuse(self):
        original = file_hash(self.video)
        cases, _ = load_cases(self.root, video_options=self.options)
        case = cases[0]
        self.assertEqual(case["timestamps_s"], [0.5, 1.5, 2.5, 3.5, 4.5])
        self.assertEqual(len(case["paths"]), 5)
        self.assertGreater(len(set(case["sha256"])), 1)
        self.assertEqual(file_hash(self.video), original)
        with patch("filename_bench.video.video_duration", side_effect=AssertionError("캐시를 재사용해야 합니다.")):
            again, _ = load_cases(self.root, video_options=self.options)
        self.assertEqual(again[0]["paths"], case["paths"])
        self.assertFalse((self.root / "answers").exists())

    def test_setting_change_uses_separate_cache(self):
        first, _ = load_cases(self.root, video_options=self.options)
        second, _ = load_cases(self.root, video_options={"seconds_per_frame": 1, "max_frames": 2})
        self.assertEqual(second[0]["timestamps_s"], [1.25, 3.75])
        self.assertTrue(set(first[0]["paths"]).isdisjoint(second[0]["paths"]))
        self.assertTrue(all(path.exists() for path in first[0]["paths"]))

    def test_failure_cancel_timeout_then_retry(self):
        for index, error in enumerate([RuntimeError("decode failed"), KeyboardInterrupt(),
                                       subprocess.TimeoutExpired("ffmpeg", 1)]):
            cache = self.root / f"cache_{index}"
            from filename_bench import video as module
            real_run = module.run_tool

            def fail(command, timeout):
                if "-frames:v" in command:
                    raise error
                return real_run(command, timeout)

            with patch("filename_bench.video.run_tool", side_effect=fail):
                with self.assertRaises(type(error)):
                    extract_video(self.video, cache, self.options)
            self.assertEqual(list(cache.rglob("completed.json")), [])
            self.assertEqual(list(cache.rglob(".running.lock")), [])
            _, result = extract_video(self.video, cache, self.options)
            self.assertEqual(len(result["frames"]), 5)

    def test_lock_and_changed_cache_are_detected(self):
        directory, result = extract_video(self.video, self.root / "cache", self.options)
        with RunLock(directory):
            with self.assertRaisesRegex(RuntimeError, "locked"):
                extract_video(self.video, self.root / "cache", self.options)
        (directory / result["frames"][0]["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "변경"):
            extract_video(self.video, self.root / "cache", self.options)

    def test_raw_video_zip_to_mock_report_with_all_frames(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.write(self.video, "evaluation/videos/clip.mp4")
        buffer.seek(0)
        dataset = import_dataset_zip(buffer, self.root / "uploaded", video_options=self.options)
        kind = "a" if (ROOT / "a_quality.py").exists() else "b"
        config = load_config(ROOT / "configs" / ("a_quality.json" if kind == "a" else "b_local.json"))
        config.update(dataset_root=str(dataset), run_dir=str(self.root / "runs"), video_extraction=self.options)
        config["baseline"]["frames"] = "all"
        result = run(config, kind, mock=True)
        directory = Path(result["run_dir"])
        row = read_rows(directory / "requests.jsonl")[0]
        self.assertEqual(row["media"]["images_per_request"], 5)
        self.assertEqual(row["media"]["timestamps_s"], [0.5, 1.5, 2.5, 3.5, 4.5])
        self.assertTrue((directory / "report.html").exists())
        self.assertEqual(read_json(directory / "video_extraction.json")["clip"]["duration_s"], 5)
        self.assertEqual(run(config, kind, mock=True, resume=True)["recorded_attempts"], 1)

    def test_drive_video_has_one_answer_and_one_result(self):
        # Drive 연결 대신 임시 폴더를 쓰고, 영상 추출은 실제 FFmpeg로 수행합니다.
        drive = self.root / "MyDrive"
        drive.mkdir()
        archive = drive / "evaluation.zip"
        answer = {"keywords": ["테스트 패턴"], "reason": "움직이는 테스트 패턴입니다.",
                  "place_name": None, "needs_review": False}
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.write(self.video, "evaluation/videos/clip.mp4")
            zipped.writestr("evaluation/answers/clip.json", json.dumps(answer, ensure_ascii=False))
        original_hash = file_hash(archive)
        dataset = prepare_drive_dataset(archive, self.root / "local_cache", video_options=self.options)
        self.assertEqual(dataset, prepare_drive_dataset(archive, self.root / "local_cache",
                                                       video_options=self.options))
        config = load_config(ROOT / "configs/a_quality.json")
        config.update(dataset_root=str(dataset), run_dir=str(drive / "runs"), video_extraction=self.options)
        config["baseline"]["frames"] = "all"
        result = run(config, "a", mock=True)
        directory = Path(result["run_dir"])
        rows = read_rows(directory / "requests.jsonl")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["case_id"], "clip")
        self.assertEqual(rows[0]["media"]["images_per_request"], 5)
        self.assertEqual(read_json(directory / "references.json")["answers"], {"clip": answer})
        self.assertEqual(file_hash(archive), original_hash)
        self.assertTrue((directory / "report.html").is_file())


if __name__ == "__main__":
    unittest.main()
