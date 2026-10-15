# Colab에서 Google Drive로 데이터와 결과 보관하기

## 처음 실행하기

1. Google Drive의 **내 드라이브**에 `filename/datasets` 폴더를 만듭니다.
2. 팀의 사진·영상 프레임·정답을 묶은 `evaluation.zip`을 그 폴더에 업로드합니다. [데이터 구조](DATASET.md)를 따릅니다.
3. [Colab 노트북](https://colab.research.google.com/github/yooongZa/filename-model-quality-bench/blob/main/notebooks/A_colab_quality.ipynb)을 열고 설치 셀을 실행합니다.
4. Drive 연결 셀을 실행하고 Google 계정 접근을 허용합니다.
5. 데이터 읽기 → 설정 → 실행 전 확인 → 실행 → 결과 확인 순서로 진행합니다.

기본 경로는 아래와 같습니다. 폴더 이름을 바꿨다면 노트북의 두 경로도 바꾸세요.

```python
DRIVE_ROOT = Path("/content/drive/MyDrive/filename")
DRIVE_ZIP = DRIVE_ROOT / "datasets" / "evaluation.zip"
```

내 드라이브 밖의 공유 드라이브를 사용하려면 마운트 후 Colab 파일 목록에 표시되는 실제 경로를 넣습니다. 인터넷 공유 URL은 파일 경로로 사용할 수 없습니다.

## 어디에 저장되나요?

```text
내 드라이브/filename/
├── datasets/
│   └── evaluation.zip                 # 직접 올린 원본, 코드에서 변경하지 않음
└── runs/
    └── 20261015_210000_123456/         # 실행마다 새 이름
        ├── smoke_mock/               # 실제 모델이면 smoke/
        │   ├── config.json
        │   ├── references.json
        │   ├── requests.jsonl
        │   ├── telemetry.jsonl
        │   ├── report.html
        │   ├── summary.csv
        │   └── review.csv
        └── smoke_mock_report.zip      # 마지막 ZIP 셀 실행 후 생성
```

- **원본:** Drive의 ZIP을 읽기만 합니다. GitHub로 업로드하지 않습니다.
- **분석용 복사본:** ZIP을 Colab의 `data/drive_cache/<ZIP 해시>/`로 복사하고 풉니다. 동일한 ZIP은 같은 경로를 쓰며, 복사와 검사가 끝난 데이터만 재사용합니다.
- **실행 기록:** 요청 한 건이 끝날 때마다 Drive에 원문과 측정값을 기록합니다. 기록할 수 없으면 오류를 표시합니다.
- **HTML·CSV:** 정상 완료 또는 코드가 처리할 수 있는 중단 시 생성합니다. 런타임이 갑자기 사라지면 최신 보고서가 없을 수 있습니다.
- **결과 ZIP:** 마지막 셀에서 Drive에 저장합니다. 원본 사진·영상·추출 프레임은 제외하고 응답·점수·설정·정답 스냅샷을 포함합니다. `DOWNLOAD_TO_PC=True`이면 PC로도 받습니다.

이미지는 로컬 복사본에서 읽어 Drive의 반복 읽기를 줄입니다. 결과 쓰기와 보고서 생성은 Drive I/O 시간이 들며, 전체 실행 시간에는 이 시간이 포함될 수 있습니다. [Colab 공식 저장 안내](https://research.google.com/colaboratory/faq.html)

## 중단한 실험 이어서 실행하기

같은 실행 셀을 다시 실행하면 완료된 요청은 건너뜁니다. 노트북을 다시 열었다면 Drive를 연결하고 같은 ZIP을 준비한 뒤, 설정 셀에 이전 폴더 이름을 넣습니다.

```python
RESUME_RUN_NAME = "20261015_210000_123456"
```

데이터·정답·프롬프트·실험 조건·코드·모델이 같아야 합니다. 다른 조건은 빈 문자열로 되돌려 새 실험을 만드세요. 원본 영상의 프레임을 다시 추출해 입력 기록이 달라진 경우에도 새 실험이 필요할 수 있습니다.

한 실험 폴더는 한 노트북에서만 사용하세요. 강제 종료 후 `Run is locked`가 나오면 이전 런타임이 완전히 종료되었는지 확인합니다. 다른 실행이 없음을 확인한 경우에만 해당 결과 폴더의 `.running.lock`을 수동 제거하고 재개합니다. 코드는 잠금을 자동 제거하지 않습니다.

Drive에 저장됐다고 해서 마지막 쓰기의 동기화까지 보장되지는 않습니다. 갑작스러운 종료 시 마지막 요청이 누락되거나 JSONL 기록이 불완전할 수 있습니다. 이 경우 오류가 표시되며 기존 기록을 자동으로 버리지 않습니다. 원본 결과를 보관하고 새 실험 이름으로 실행하세요.

## PC에서 직접 업로드하기

`USE_DRIVE=False`이면 기존 업로드 창을 사용합니다. 로컬 Python에서는 `LOCAL_ZIP`에 ZIP 경로를 넣습니다. 이 모드의 결과는 저장소의 `runs/`에 기록되며 Drive에 자동 저장되지 않습니다.

## 변경 범위와 검증

Based-On: none — LMS 색인에 Drive 파일 입출력에 직접 대응하는 예제가 없어 project_extension으로 작성했습니다. 모델 설정·전처리 순서·평가지표는 변경하지 않습니다.

Drive에 결과를 직접 쓰므로 기존 요청별 저장·잠금·재개 검사를 그대로 사용합니다. 별도의 백그라운드 복사 작업은 없습니다.

| 경로 | 확인할 동작 |
|---|---|
| 정상 | ZIP을 로컬에 복사하고 지정한 결과 폴더에 원문·리포트를 생성 |
| 복사 실패·취소 | Drive 원본과 기존 결과를 유지하고 미완성 복사본을 재사용하지 않음 |
| 재시도 | 동일한 ZIP의 경로를 재사용하고 완료한 평가 요청을 건너뜀 |
| 데이터 변경 | 새 ZIP 해시의 경로 사용, 이전 실험에 혼합하지 않음 |
| 저장 실패 | 예외를 표시하고 임시 디스크로 조용히 전환하지 않음 |

CPU 테스트는 임시 폴더로 저장·재개를 검증합니다. 실제 Google 계정 연결과 Drive 동기화는 Colab에서 별도로 확인해야 합니다.
