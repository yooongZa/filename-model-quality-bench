# 실험 실행 방법


`notebooks/A_colab_quality.ipynb`를 Colab에 열고 팀이 준비한 ZIP을 업로드합니다. 기본값은 `MOCK=True`입니다. 경로 확인 후 실제 추론으로 바꿉니다.

터미널에서는 다음 순서로 실행합니다.

```bash
python -m pip install -r requirements-colab.txt
python a_quality.py --suite smoke
python a_quality.py --suite resolution
python a_quality.py --suite vision
python a_quality.py --suite output
python a_quality.py --suite frames
python a_quality.py --suite selection
```

기본 `case_ids=null`은 업로드한 전체 입력을 사용합니다. 일부만 먼저 확인하려면 데이터의 실제 ID를 목록으로 지정하세요. 전체 실행 전에 `--dry-run`으로 요청 수와 입력 크기를 확인하세요. `--limit 2`는 이번 실행의 측정 요청 수를 제한합니다. B의 컨텍스트 보정 요청은 별도입니다.

| suite(실험 묶음) | 바꾸는 값 | 고정하는 값 |
|---|---|---|
| `smoke` | 사진별 1장, 영상별 기본 3프레임 | 기준 설정 |
| `baseline` | 바꾸지 않음 | 설정의 `baseline` |
| `resolution` | 이미지 짧은 변 1080/720/480/360/240px | 시각 토큰·프레임 수 |
| `vision` | 시각 토큰 상한 1120/560/280/140/70 | 원본 해상도·프레임 수 |
| `output` | 최대 출력 토큰 512/256/128 | 입력 이미지·시각 토큰 |
| `frames` | 영상 1/3/6/12프레임 | 해상도·시각 토큰 |
| `selection` | 균등/선명도/중복 억제/조합 | 업로드한 후보 중 6장 선택 |

기준값은 1080px·시각 토큰 상한 1120·영상 3프레임·출력 256토큰입니다. 성공이 확인된 운영 설정이 아니라 비교의 출발점입니다. 기준값에서 출력이 잘리면 출력 예산을 먼저 조정한 뒤 새 결과 폴더에서 실험하세요.

Gemma의 processor(전처리기)는 내부적으로 크기를 다시 조절합니다. 따라서 파일 해상도가 작아졌다고 입력 토큰도 같은 비율로 줄어드는 것은 아닙니다. `input_tokens`, `vision_tokens_actual`, `prepared_sizes_wh`를 함께 확인하세요. `vision_tokens_actual`은 processor가 확장한 이미지 토큰 ID 개수입니다.

프레임 전처리는 다음 규칙을 따릅니다.

- 항상 업로드한 원본에서 축소하고 확대하지 않습니다. 이미지 정규화는 모델의 processor에 맡깁니다.
- 1프레임은 가운데 이미지, 나머지는 시간순입니다. 여러 프레임은 독립 사진 묶음이 아닌 같은 영상 하나로 전달합니다.
- 선명도는 동일 분석 크기에서 Laplacian variance(라플라시안 분산), 중복은 dHash(차분 해시)로 비교합니다.
- 시간 구간마다 한 장을 선택해 영상의 앞·중간·끝이 유지되게 합니다. 중복 기준을 만족하는 후보가 없으면 같은 구간에서 대체하고 `fallback_count`에 기록합니다.
- 선택 범위는 업로드한 후보 프레임입니다. 원본 영상 전체에 대한 최적 프레임 탐색은 검증하지 않습니다. 사진의 흐림을 복원하는 기능도 포함하지 않습니다.

모델은 `google/gemma-4-12B-it-qat-q4_0-unquantized`, BF16, CUDA 0에 고정 로드합니다. LM Studio 표시명과 로컬 Q4 파일의 차이는 [모델 안내](MODEL.md)를 참고하세요. Colab 모델 접근 권한이 필요하면 Hugging Face의 모델 약관·로그인을 먼저 완료하세요. 실제 로드한 revision(리비전), 패키지 버전, 장치를 저장합니다. 기본 설정은 확인한 모델 revision을 고정하며, 실제 로드한 `resolved_revision`도 기록합니다.

Temperature(생성 무작위성)는 0, thinking(추론 모드)은 꺼짐, JSON 강제 출력은 꺼짐입니다. A는 `sample_batch_size=1`입니다. 시드를 바꿔도 greedy decoding(탐욕적 생성)의 다양성이 생기지는 않으므로 반복 실행은 주로 시간·안정성 확인에 사용합니다.
