"""사용 예: python upload_dataset.py evaluation.zip --destination data/evaluation"""
import argparse

from filename_bench.uploads import import_dataset_zip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="팀이 만든 평가 ZIP을 가져옵니다.")
    parser.add_argument("zip_path", help="준비한 사진·원본 영상·정답 ZIP의 경로")
    parser.add_argument("--destination", default="data/evaluation", help="새로 만들 폴더")
    parser.add_argument("--seconds-per-frame", type=float, default=10, help="몇 초당 한 장을 추출할지")
    parser.add_argument("--max-frames", type=int, default=5, help="원본 영상 한 개의 최대 추출 장수")
    args = parser.parse_args()
    dataset_root = import_dataset_zip(args.zip_path, args.destination, video_options={
        "seconds_per_frame": args.seconds_per_frame, "max_frames": args.max_frames})
    print(f"데이터 준비 완료: {dataset_root}")
    print(f'다음 실행에 --dataset-root "{dataset_root}" 옵션을 붙이세요.')
