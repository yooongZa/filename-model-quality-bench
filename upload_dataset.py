"""사용 예: python upload_dataset.py evaluation.zip --destination data/evaluation"""
import argparse

from filename_bench.uploads import import_dataset_zip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="팀이 만든 평가 ZIP을 가져옵니다.")
    parser.add_argument("zip_path", help="준비한 사진·프레임 ZIP의 경로")
    parser.add_argument("--destination", default="data/evaluation", help="새로 만들 폴더")
    args = parser.parse_args()
    dataset_root = import_dataset_zip(args.zip_path, args.destination)
    print(f"데이터 준비 완료: {dataset_root}")
    print(f'다음 실행에 --dataset-root "{dataset_root}" 옵션을 붙이세요.')
