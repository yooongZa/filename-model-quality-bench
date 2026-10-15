"""팀이 준비한 ZIP을 읽습니다. 사진·프레임·정답을 새로 생성하지 않습니다."""
from __future__ import annotations

import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image

from .data import load_cases


def find_dataset_root(folder):
    """ZIP 안에 바깥 폴더가 하나 더 들어 있어도 실제 데이터 위치를 찾습니다."""
    folder = Path(folder)
    while True:
        if any((folder / name).exists() for name in ("model_inputs.jsonl", "images", "frames")):
            return folder
        children = [p for p in folder.iterdir() if p.name != "__MACOSX" and not p.name.startswith(".")]
        if len(children) != 1 or not children[0].is_dir():
            raise ValueError("ZIP에 images/ 또는 frames/ 폴더를 넣어 주세요. docs/DATASET.md를 참고하세요.")
        folder = children[0]


def import_dataset_zip(archive, destination, max_bytes=2 * 1024**3, max_files=10000):
    """새 폴더에 업로드를 풀고 검사한 뒤, 평가에 사용할 경로를 반환합니다.

    archive에는 ZIP 파일 경로 또는 BytesIO를 넣습니다. 기존 폴더는 덮어쓰지
    않습니다. 중단·검사 실패 때 남은 폴더는 보존하고 새 목적지로 재시도합니다.
    """
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(f"이미 있는 폴더입니다. 새 destination을 지정하세요: {destination}")

    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) > max_files or sum(item.file_size for item in entries) > max_bytes:
            raise ValueError("ZIP은 압축 해제 후 2GB, 항목 10,000개 이하로 준비해 주세요.")

        # 압축을 풀기 전에 경로를 검사합니다. ZIP 밖의 파일에 쓰지 않도록 합니다.
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                    or ":" in item.filename or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError(f"허용하지 않는 ZIP 경로입니다: {item.filename}")
            key = path.as_posix().casefold()
            if key in seen:
                raise ValueError(f"중복 ZIP 경로입니다: {item.filename}")
            seen.add(key)
            if item.flag_bits & 1:
                raise ValueError("암호가 걸린 ZIP은 지원하지 않습니다.")

        # exist_ok=False: 이미 있는 사용자 폴더에 데이터를 섞지 않습니다.
        destination.mkdir(parents=True, exist_ok=False)
        for item in entries:
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(item) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)

    dataset_root = find_dataset_root(destination)
    cases, _ = load_cases(dataset_root)
    # 손상된 파일을 GPU 모델 로드 전에 발견합니다. 이미지 내용은 변경하지 않습니다.
    for case in cases:
        for path in case["paths"]:
            with Image.open(path) as image:
                image.verify()
    return dataset_root
