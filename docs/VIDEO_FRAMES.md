# 영상에서 대표 프레임 추출

`videos/`에 원본 MP4·MOV·M4V·MKV·WEBM·AVI를 넣습니다. FFmpeg와 ffprobe 실행 파일을 사용하므로 추가 Python 영상 패키지는 필요하지 않습니다. 두 실행 파일은 PATH에 있거나 설정에 경로를 지정해야 합니다.

```text
evaluation/
  images/city.jpg
  videos/cycling.mp4
  answers/cycling.json
```

**영상 한 편당 `answers/영상ID.json` 정답 한 개만 작성합니다.** 프레임 파일과 프레임별 정답은 준비하지 않아도 됩니다. 기존 4개 필드(`keywords`, `reason`, `place_name`, `needs_review`)를 영상 전체 기준으로 작성하세요.

기본 설정은 **10초당 1장, 최대 5장**입니다. `N = min(max_frames, ceil(영상 길이 / seconds_per_frame))`로 장수를 정한 다음, 영상을 N개 구간으로 나누어 각 구간의 가운데를 추출합니다. 10초 이하의 정상 영상은 가운데 한 장입니다.

| 영상 길이 | 장수 | 요청 시점 |
|---|---:|---|
| 8초 | 1 | 4초 |
| 20초 | 2 | 5초, 15초 |
| 50초 | 5 | 5초, 15초, 25초, 35초, 45초 |
| 100초 | 5 | 10초, 30초, 50초, 70초, 90초 |

여기서 대표 프레임은 일정한 시간 위치의 이미지입니다. 영상 압축의 I-frame(키프레임)만 고르는 방식과 구분합니다. FFmpeg의 정확한 탐색으로 목표 위치의 프레임을 디코딩합니다. 실제 영상은 이산적인 프레임으로 이루어지므로 요청 시각과 프레임 시각에는 차이가 있을 수 있습니다. 기록한 `timestamps_s`는 **요청 시각**입니다.

## 설정과 실행

`configs/a_quality.json` 또는 `configs/b_local.json`의 `video_extraction`에서 간격·상한·실행 파일 경로를 바꿉니다. 노트북에서는 업로드 셀의 `SECONDS_PER_FRAME`, `MAX_EXTRACTED_FRAMES`를 바꿉니다.

```bash
python a_quality.py --dataset-root data/evaluation --frames all --mock
python b_capacity.py --dataset-root data/evaluation --frames all --mock
```

각 저장소에 있는 해당 명령을 사용합니다. `--frames all`은 추출한 이미지를 모두 모델에 전달합니다. 기존 숫자 설정(예: 3)은 후보 중 3장을 선택합니다. `frames`·`images` 실험은 비교 목록의 장수를 사용하므로, 6·12장 비교에는 충분한 후보와 추출 상한이 필요합니다. 부족한 장수를 복제해서 채우지 않습니다.

`--dry-run`과 `--mock`도 실제 원본 영상에서 대표 프레임을 준비합니다. GPU 모델 추론은 수행하지 않습니다. 추출 PNG는 원본 크기로 저장하고, 모델 입력 해상도 조절은 기존 전처리 단계에서 수행합니다. 원본 사진·영상과 정답은 변경하지 않습니다.

## 비용과 재사용

추출 결과는 데이터 폴더의 `.filename_frames/`에 보관합니다. 원본 해시·간격·장수 상한·FFmpeg 버전이 같으면 완료된 결과를 재사용합니다. 한 번에 한 프레임씩 CPU에서 디코딩하고 PNG로 저장하므로 메모리와 작업량을 제한합니다. 실행 시간과 저장 공간은 코덱·해상도·장수에 따라 달라집니다.

추출 시간·원본 해시·도구 버전은 실행 결과의 `video_extraction.json`에 별도 기록합니다. 모델 추론 시간에는 추출 준비 시간이 포함되지 않습니다. 캐시 재사용 시의 로딩·해시 검사 시간도 모델 추론 시간에서 제외됩니다.

## 쓰기와 재시도 검증

| 경로 | 처리 | 검증 |
|---|---|---|
| 정상 | 고유한 작업 폴더에 PNG를 쓰고 완료 기록 저장 | 실제 짧은 영상 추출, 시점·장수·원본 해시 확인 |
| 실패·시간 초과 | 완료 기록을 남기지 않고 부분 파일 보존 | FFmpeg 실패·시간 초과 주입 |
| 취소 | 현재 자식 프로세스 정리, 완료 기록 없음 | 취소 주입 |
| 재시도 | 새 작업 폴더에서 시작 | 중단 후 정상 추출 |
| 같은 원본·설정 | 완료된 파일 해시를 검사하고 재사용 | 두 번째 추출 호출 없음 |
| 동시 접근 | 같은 캐시에 단일 작성자 잠금 적용 | 잠금 충돌 확인 |
| 설정 변경 | 별도 캐시 생성 | 기존 결과 보존 확인 |

Based-On: none — 직접 대응하는 LMS 영상 추출 예제가 없는 project_extension입니다.

공식 근거: [FFmpeg 탐색과 이미지 추출](https://ffmpeg.org/ffmpeg.html), [ffprobe 메타데이터](https://ffmpeg.org/ffprobe.html).

검증 명령: `python -m unittest discover -s tests -v`. 실제 FFmpeg로 임시 영상의 프레임을 추출하고 Drive 입력·정답 연결·보고서 저장을 검사합니다. 실제 GPU 모델 추론과 Windows FFmpeg 실행은 이번 변경에서 검증하지 않았습니다.
