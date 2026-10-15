# filename · A — 모델 품질 실험

Colab에서 Gemma 4 E4B의 해상도·시각 토큰·출력 토큰·프레임 수·전처리를 비교합니다.

[Colab에서 노트북 열기](https://colab.research.google.com/github/yooongZa/filename-model-quality-bench/blob/main/notebooks/A_colab_quality.ipynb)

## 빠른 시작

Python 3.10 이상을 사용합니다.

```bash
git clone https://github.com/yooongZa/filename-model-quality-bench.git
cd filename-model-quality-bench
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

자동 테스트는 작은 합성 이미지를 임시 생성하므로 모델·평가 데이터가 없어도 실행할 수 있습니다.

평가 데이터 폴더를 `data/filename_eval24_1080/`에 준비한 뒤 실행합니다. 다른 위치를 쓰려면 `configs/a_quality.json`의 `dataset_root`를 변경하세요. 상세 형식은 [데이터 준비](docs/DATASET.md)에 있습니다.

```bash
python a_quality.py --dry-run
python a_quality.py --mock --resume
```

모의 실행은 저장·검사·리포트 경로를 확인하는 고정 응답을 사용합니다. 모의 결과로 모델 품질·GPU 성능을 판단하지 않습니다.

실제 추론 전 `python -m pip install -r requirements-colab.txt`로 의존성을 준비하고 CUDA GPU와 모델 접근 권한을 확인합니다. 노트북의 `MOCK=False` 또는 CLI에서 `--mock`을 빼면 모델 다운로드·추론이 시작됩니다.

## 구성과 결과

- [a_quality.py](a_quality.py): 실행 진입점
- [configs/a_quality.json](configs/a_quality.json): 실험 설정
- [실험 실행 방법](docs/EXPERIMENTS.md): 조건별 실행과 해석
- [평가 방법](docs/EVALUATION.md): 자동 지표와 사람 평가표
- [재개·오류 처리](docs/RELIABILITY.md): 실패·중단·재시도 검증 범위
- [검증 기록](VALIDATION.md): 이 저장소에서 확인한 범위

결과는 `runs/a/<suite>/`에 저장됩니다. JSONL 원문, CSV 지표·사람 평가표, HTML 리포트를 생성합니다. 공통 `filename_bench` 코드는 각 저장소에 포함되어 있어 다른 저장소 설치가 필요하지 않습니다. 모델·미디어·실행 결과·로컬 설정은 Git에서 제외합니다.

## 관련 저장소와 범위

짝 프로젝트: [yooongZa/filename-local-capacity-bench](https://github.com/yooongZa/filename-local-capacity-bench)

실제 A100·Windows 8GB VRAM·Mac Metal 추론은 아직 검증하지 않았습니다. 참조 답안은 독립적인 사람 검수가 필요합니다.

**Based-On: none** — 대응하는 멀티모달 용량·품질 벤치마크 LMS 예제가 없어 별도로 작성한 `project_extension`입니다. LMS 원문은 포함하지 않습니다.

## 공식 참고 자료

- [Gemma 4 E4B](https://huggingface.co/google/gemma-4-E4B-it)
- [Transformers Gemma 4](https://huggingface.co/docs/transformers/model_doc/gemma4)
- [llama-server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
