# filename · A — 모델 품질 실험

선택 모델: **`google/gemma-4-12b-qat`**. Colab에서 해상도·시각 토큰·출력 토큰·프레임 수·전처리 조건을 비교합니다.

평가 데이터는 팀이 ZIP으로 업로드합니다. 사진·프레임·정답을 생성하는 기능은 없습니다.

## Colab에서 시작하기

[Colab 노트북 열기](https://colab.research.google.com/github/yooongZa/filename-model-quality-bench/blob/main/notebooks/A_colab_quality.ipynb)

1. 설치 셀을 실행합니다.
2. 팀이 준비한 사진·프레임 ZIP을 업로드합니다.
3. **바꿔 볼 설정** 셀에서 해상도·토큰·프레임 수를 정합니다.
4. `MOCK=True`로 흐름을 확인한 뒤 `False`로 실제 평가합니다.
5. HTML 리포트와 CSV를 확인하고 결과 ZIP을 내려받습니다.

A의 실제 실행은 A100 등 CUDA GPU와 모델 접근 권한이 필요합니다. Google의 QAT 학습 체크포인트를 **BF16**으로 실행합니다. 로컬 Q4의 품질은 B에서 재확인합니다. [모델 구분](docs/MODEL.md)

## 터미널에서 시작하기

Python 3.10 이상을 사용합니다.

```bash
git clone https://github.com/yooongZa/filename-model-quality-bench.git
cd filename-model-quality-bench
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python upload_dataset.py evaluation.zip --destination data/evaluation
```

마지막 명령이 출력한 실제 데이터 경로를 아래 `--dataset-root`에 넣습니다. 폴더 구조는 [데이터 업로드 안내](docs/DATASET.md)를 참고하세요.

```bash
python a_quality.py --dataset-root data/evaluation --dry-run
python a_quality.py --dataset-root data/evaluation --mock --run-dir runs/first_check
```

모의 실행은 고정 응답으로 저장·검사·리포트를 확인합니다. 실제 추론 전 `python -m pip install -r requirements-colab.txt`로 모델 실행 패키지를 준비하세요. `--mock`을 빼면 모델 다운로드·추론이 시작됩니다.

## 코드를 읽고 수정할 때

먼저 [초보자 코드 안내](docs/CODE_GUIDE.md)의 수정 위치 표를 보세요. 입력 설정과 모델 지시문을 바꾸는 데 내부 실행 코드를 수정할 필요는 없습니다.

- [실험 실행 방법](docs/EXPERIMENTS.md): 조건별 실행과 해석
- [평가 방법](docs/EVALUATION.md): 자동 지표와 사람 평가표
- [재개·오류 처리](docs/RELIABILITY.md): 실패·중단·재시도
- [검증 기록](VALIDATION.md): 확인한 범위와 미실행 항목

기본 결과는 `runs/a/<suite>/`에 저장됩니다. `--run-dir`로 바꿀 수 있습니다. JSONL 원문, CSV 지표·사람 평가표, HTML 리포트를 생성합니다. 데이터·모델·결과·개인 설정은 Git에서 제외합니다. 참조 답안 없이도 실행할 수 있습니다.

짝 프로젝트: [yooongZa/filename-local-capacity-bench](https://github.com/yooongZa/filename-local-capacity-bench)

**Based-On: none** — 대응하는 멀티모달 품질·용량 LMS 예제가 없어 별도로 작성한 `project_extension`입니다. LMS 원문은 포함하지 않습니다.
