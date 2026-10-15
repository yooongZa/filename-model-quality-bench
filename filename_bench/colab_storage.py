"""Drive의 ZIP을 Colab 디스크로 복사합니다. 원본과 평가 결과는 Drive에 둡니다."""
from pathlib import Path
import shutil
import tempfile

from .common import file_hash, read_json, write_json
from .uploads import import_dataset_zip


def prepare_drive_dataset(archive, cache_root, **import_options):
    """같은 ZIP은 같은 로컬 경로로 가져와 이어서 실행할 수 있게 합니다.

    압축 해제와 입력 검사가 모두 끝난 복사본만 재사용합니다. 복사·검사 중
    오류나 취소가 발생해도 Drive의 원본 ZIP은 변경하지 않습니다.
    import_options는 기존 ZIP 가져오기 함수에 그대로 전달합니다.
    """
    archive = Path(archive).expanduser().resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"Drive에 평가 ZIP을 먼저 올려 주세요: {archive}")
    if archive.suffix.lower() != ".zip":
        raise ValueError("데이터 폴더를 ZIP으로 압축해 지정해 주세요.")

    # 파일명이 같아도 내용이 바뀌면 별도의 복사본을 사용합니다.
    archive_hash = file_hash(archive)
    cache_root = Path(cache_root).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    destination = cache_root / archive_hash
    if destination.exists():
        marker = read_json(destination / "ready.json")
        return destination / marker["dataset_relative_path"]

    # Drive에서 작은 이미지들을 반복해서 읽지 않고 ZIP 한 개만 복사합니다.
    # 임시 폴더는 이 함수가 만든 파일만 담으며, 실패하면 자동 정리됩니다.
    with tempfile.TemporaryDirectory(prefix="import_", dir=cache_root) as temporary:
        staging = Path(temporary) / "ready"
        staging.mkdir()
        local_zip = staging / "source.zip"
        shutil.copyfile(archive, local_zip)
        if file_hash(local_zip) != archive_hash:
            raise ValueError("복사 중 ZIP 내용이 달라졌습니다. 업로드 완료 후 다시 실행하세요.")
        dataset = import_dataset_zip(local_zip, staging / "data", **import_options)
        relative_path = dataset.relative_to(staging).as_posix()
        write_json(staging / "ready.json", {"archive_sha256": archive_hash,
                                           "dataset_relative_path": relative_path})
        # 완성된 로컬 복사본을 한 번에 옮깁니다. Drive 원본은 이동하지 않습니다.
        staging.rename(destination)
    return destination / relative_path
