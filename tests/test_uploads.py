"""작은 임시 이미지로 업로드 코드를 검사합니다. 모델 평가 데이터는 아닙니다."""
import io
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from filename_bench.common import ROOT, load_config, read_json, read_rows
from filename_bench.data import load_cases
from filename_bench.runner import run
from filename_bench.uploads import import_dataset_zip


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        buffer = io.BytesIO()
        Image.new("RGB", (32, 24), "blue").save(buffer, format="PNG")
        self.image = buffer.getvalue()

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, contents in entries:
                archive.writestr(name, contents)
        buffer.seek(0)
        return buffer

    def test_wrapper_and_frame_order_without_generated_answers(self):
        entries = [("evaluation/images/city.png", self.image)]
        entries += [(f"evaluation/frames/cycling/{n}.png", self.image) for n in [10, 2, 1]]
        dataset = import_dataset_zip(self.archive(entries), self.root / "upload")
        cases, _ = load_cases(dataset)
        self.assertEqual([case["id"] for case in cases], ["city", "cycling"])
        self.assertEqual([path.name for path in cases[1]["paths"]], ["1.png", "2.png", "10.png"])
        self.assertEqual((dataset / "images/city.png").read_bytes(), self.image)
        self.assertFalse((dataset / "answers").exists())
        self.assertFalse((dataset / "model_inputs.jsonl").exists())

    def test_photo_only_and_video_only_runs(self):
        kind = "a" if (ROOT / "a_quality.py").exists() else "b"
        config_file = "a_quality.json" if kind == "a" else "b_local.json"
        for media in ["image", "video"]:
            with self.subTest(media=media):
                entries = [("images/city.png", self.image)] if media == "image" else [
                    (f"frames/clip/{n}.png", self.image) for n in range(3)]
                dataset = import_dataset_zip(self.archive(entries), self.root / media)
                config = load_config(ROOT / "configs" / config_file)
                config.update(dataset_root=str(dataset), run_dir=str(self.root / (media + "_run")))
                result = run(config, kind, mock=True)
                directory = Path(result["run_dir"])
                self.assertEqual(result["recorded_attempts"], 1)
                self.assertEqual(read_json(directory / "references.json")["answers"], {})
                self.assertEqual(len(read_json(directory / "config.json")["skipped_profiles_no_media"]), 1)
                self.assertTrue(read_rows(directory / "requests.jsonl")[0]["schema_valid"])
                if media == "image":
                    with self.assertRaisesRegex(ValueError, "필요한 종류"):
                        run(config, kind, suite="frames" if kind == "a" else "images", mock=True)

    def test_unsafe_zip_paths_are_rejected_before_writing(self):
        link = zipfile.ZipInfo("images/link.png")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for i, name in enumerate(["../outside.png", "/absolute.png", "C:/drive.png", "..\\outside.png", link]):
            with self.subTest(name=name):
                destination = self.root / str(i)
                with self.assertRaises(ValueError):
                    import_dataset_zip(self.archive([(name, b"outside")]), destination)
                self.assertFalse(destination.exists())

    def test_case_collision_and_limits(self):
        entries = [("images/CITY.png", self.image), ("images/city.png", self.image)]
        with self.assertRaisesRegex(ValueError, "중복"):
            import_dataset_zip(self.archive(entries), self.root / "duplicates")
        with self.assertRaises(ValueError):
            import_dataset_zip(self.archive(entries[:1]), self.root / "size", max_bytes=1)
        self.assertFalse((self.root / "duplicates").exists())
        self.assertFalse((self.root / "size").exists())

    def test_existing_destination_is_preserved(self):
        destination = self.root / "existing"
        destination.mkdir()
        (destination / "keep.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            import_dataset_zip(self.archive([("images/city.png", self.image)]), destination)
        self.assertEqual(list(destination.iterdir()), [destination / "keep.txt"])
        self.assertEqual((destination / "keep.txt").read_text(), "keep")

    def test_invalid_image_then_retry_in_new_folder(self):
        with self.assertRaises(OSError):
            import_dataset_zip(self.archive([("images/city.png", b"broken")]), self.root / "failed")
        self.assertEqual((self.root / "failed/images/city.png").read_bytes(), b"broken")
        dataset = import_dataset_zip(self.archive([("images/city.png", self.image)]), self.root / "retry")
        self.assertEqual(len(load_cases(dataset)[0]), 1)

    def test_cancel_preserves_partial_file_and_retry_works(self):
        def cancel(source, output):
            output.write(source.read(8))
            raise KeyboardInterrupt

        entries = [("images/city.png", self.image)]
        with patch("filename_bench.uploads.shutil.copyfileobj", side_effect=cancel):
            with self.assertRaises(KeyboardInterrupt):
                import_dataset_zip(self.archive(entries), self.root / "cancelled")
        self.assertEqual((self.root / "cancelled/images/city.png").read_bytes(), self.image[:8])
        dataset = import_dataset_zip(self.archive(entries), self.root / "retry")
        self.assertEqual((dataset / "images/city.png").read_bytes(), self.image)


if __name__ == "__main__":
    unittest.main()
