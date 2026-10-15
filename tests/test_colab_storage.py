"""Drive 대신 임시 폴더를 쓰는 입출력 검사. 실제 모델 평가 데이터는 아닙니다."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from filename_bench.colab_storage import prepare_drive_dataset
from filename_bench.common import ROOT, file_hash, load_config, read_rows
from filename_bench.runner import run


class ColabStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.drive = self.root / "MyDrive" / "filename"
        self.drive.mkdir(parents=True)
        self.archive = self.drive / "evaluation.zip"
        self.cache = self.root / "runtime_cache"
        self.make_zip()

    def tearDown(self):
        self.temp.cleanup()

    def make_zip(self, color="blue"):
        buffer = io.BytesIO()
        Image.new("RGB", (32, 24), color).save(buffer, format="PNG")
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name in ["city", "picnic"]:
                archive.writestr(f"evaluation/images/{name}.png", buffer.getvalue())

    def test_copy_reuse_and_changed_zip(self):
        original_hash = file_hash(self.archive)
        first = prepare_drive_dataset(self.archive, self.cache)
        self.assertEqual(first, prepare_drive_dataset(self.archive, self.cache))
        self.assertEqual(original_hash, file_hash(self.archive))
        self.make_zip("red")
        second = prepare_drive_dataset(self.archive, self.cache)
        self.assertNotEqual(first, second)
        self.assertTrue((first / "images/city.png").exists())

    def test_copy_failure_and_cancel_then_retry(self):
        original_hash = file_hash(self.archive)
        for exception in [OSError("Drive read failed"), KeyboardInterrupt()]:
            with self.subTest(exception=type(exception).__name__):
                with patch("filename_bench.colab_storage.shutil.copyfile", side_effect=exception):
                    with self.assertRaises(type(exception)):
                        prepare_drive_dataset(self.archive, self.cache)
                self.assertEqual(list(self.cache.iterdir()), [])
                self.assertEqual(file_hash(self.archive), original_hash)
        self.assertTrue(prepare_drive_dataset(self.archive, self.cache).is_dir())

    def test_missing_and_invalid_archive(self):
        with self.assertRaises(FileNotFoundError):
            prepare_drive_dataset(self.drive / "missing.zip", self.cache)
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("images/broken.png", b"broken")
        with self.assertRaises(OSError):
            prepare_drive_dataset(self.archive, self.cache)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_results_persist_and_resume_without_duplicates(self):
        dataset = prepare_drive_dataset(self.archive, self.cache)
        config = load_config(ROOT / "configs/a_quality.json")
        config.update(dataset_root=str(dataset), run_dir=str(self.drive / "runs" / "test"))
        first = run(config, "a", mock=True, limit=1)
        second = run(config, "a", mock=True, resume=True)
        directory = Path(second["run_dir"])
        self.assertTrue(directory.is_relative_to(self.drive))
        self.assertEqual(first["recorded_attempts"], 1)
        self.assertEqual(second["recorded_attempts"], 2)
        self.assertEqual(len({r["job_id"] for r in read_rows(directory / "requests.jsonl")}), 2)
        self.assertTrue((directory / "report.html").is_file())
        self.assertTrue((directory / "summary.csv").is_file())

    def test_write_failure_is_visible_and_existing_result_survives(self):
        dataset = prepare_drive_dataset(self.archive, self.cache)
        config = load_config(ROOT / "configs/a_quality.json")
        config.update(dataset_root=str(dataset), run_dir=str(self.drive / "runs" / "failure"))
        first = run(config, "a", mock=True, limit=1)
        directory = Path(first["run_dir"])
        saved = (directory / "requests.jsonl").read_bytes()
        with patch("filename_bench.runner.append_row", side_effect=OSError("Drive write failed")):
            with self.assertRaisesRegex(OSError, "Drive write failed"):
                run(config, "a", mock=True, resume=True)
        self.assertEqual((directory / "requests.jsonl").read_bytes(), saved)
        self.assertFalse((directory / ".running.lock").exists())
        self.assertEqual(run(config, "a", mock=True, resume=True)["recorded_attempts"], 2)


if __name__ == "__main__":
    unittest.main()
