"""A: 이미지 해상도·토큰·프레임 수에 따른 모델 품질을 비교합니다.

처음에는 python a_quality.py --mock 으로 저장·검사 흐름을 확인하세요.
실험값은 configs/a_quality.json, 실제 실행 흐름은 filename_bench/runner.py에 있습니다.
"""
from filename_bench.runner import main

if __name__ == "__main__":
    main("a")
