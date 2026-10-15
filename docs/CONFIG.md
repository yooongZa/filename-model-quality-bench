# config로 실험·앱 조건 바꾸기

A는 `configs/a_quality.json`, Colab 노트북은 `configs/a_colab.json`, B는 `configs/b_local.json`을 읽습니다. 앱은 `configs/app.json`의 `profile_path`를 읽습니다.

## 자주 바꾸는 항목

| 위치 | 바꾸는 내용 |
|---|---|
| `baseline.short_edge_px` | 입력 이미지 짧은 변 해상도 |
| `baseline.vision_token_budget` | 이미지 한 장에 요청하는 시각 토큰 상한 |
| `baseline.max_new_tokens` | 답변 토큰 상한 |
| `baseline.context_per_request` | 입력·출력 합계 문맥 길이 |
| `baseline.frames` | 영상 한 요청에 넣을 장수 또는 `all` |
| `baseline.selection` | `uniform`, `blur`, `dedup`, `both` |
| `baseline.temperature`, `seeds` | 생성 무작위성과 실험 시드 |
| `sweeps` | 실험에서 비교할 후보값 목록 |
| `video_extraction` | 후보 프레임 추출 간격·상한·FFmpeg 경로 |
| `backend` | 환경별 모델·실행 도구·배치·GPU 설정 |
| `prompt_path`, `schema_path` | 별도 프롬프트·출력 규칙 파일 |

A의 `selection_frames`, `sweeps.selection`도 config에서 변경합니다. B의 동시 요청·엔진 token batch·microbatch는 서로 다른 설정입니다. 기존 기본 config의 값은 유지하며 새 profile은 명시적으로 선택할 때 적용합니다.

## 같은 입력 조건을 A·B·앱에서 사용하기

공통 예제는 `configs/profiles/gemma4_12b.json`입니다. **720px / 시각 토큰 280 / 출력 512 / 문맥 8192 / 최대 5프레임**을 시작값으로 제공합니다. 검증된 최적값을 뜻하지 않습니다.

```bash
# 각 저장소에서 실행합니다.
python a_quality.py --config configs/a_quality.json --profile configs/profiles/gemma4_12b.json --dry-run
python b_capacity.py --config configs/b_local.json --profile configs/profiles/gemma4_12b.json --dry-run
```

설정 적용 순서: **기본 config → profile → 명시적인 CLI 옵션**. CLI의 `--profile`은 현재 작업 폴더 기준이고, config 안의 `profile_path`는 config 파일 기준입니다.

profile은 `baseline`, `video_extraction`, `prompt_path`, `schema_path`만 담습니다. GPU 백엔드·실험 반복 횟수·결과 경로는 환경별 config에 둡니다. profile의 프롬프트·Schema 경로는 profile 파일 기준입니다. profile과 참조 파일을 같은 상대 구조로 복사하거나 절대 경로를 지정하세요.

프로그램용 v3 파생본은 `assets/prompt_v3_five_tags.txt`이며 태그 5개를 요청합니다. `assets/schema_v3_five_tags.json`이 정확히 5개인지 검사합니다. 기존 0~5개 비교 실험용 v3 파일은 보존했습니다. 실험 사이에는 어느 프롬프트·Schema를 썼는지 함께 기록하세요.

## Colab

Drive 기본 설정 위치는 `내 드라이브/filename/configs/a_colab.json`입니다. 처음 실행할 때만 예제를 복사합니다. 해상도나 후보값을 이 JSON에서 수정하고 데이터 준비 셀부터 다시 실행하세요. 노트북은 더 이상 같은 값을 Python 변수로 덮어쓰지 않습니다.

실행 모드도 JSON 안의 `notebook`에서 설정합니다.

```json
"notebook": {
  "mock": true,
  "suite": "smoke",
  "limit": null,
  "resume_run_name": ""
}
```

`mock: false`일 때 실제 모델을 사용합니다. 결과와 실제 사용한 config는 기존처럼 Drive에 저장됩니다. 기존 실험을 재개할 때는 동일한 데이터·설정·코드·모델을 유지하세요.
