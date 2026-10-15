# 처음 수정할 때 읽는 코드 안내

입력에서 결과까지의 순서는 다음과 같습니다.

```text
팀이 준비한 ZIP
  → upload_dataset.py / 노트북: 업로드·압축 해제
  → data.py: 사진별·영상별로 읽기 → 프레임 선택 → 크기 조절
  → runner.py: 실험 조건을 하나씩 적용
  → backends.py: 실제 모델에 이미지와 프롬프트 전달
  → common.py: 응답 JSON 검사
  → report.py: 원문·CSV·HTML 저장
```

## 먼저 수정할 곳

| 바꾸려는 것 | 수정 위치 | 의미 |
|---|---|---|
| 이미지 해상도 | `baseline.short_edge_px` | 이미지의 짧은 변, 단위 px |
| 이미지 정보량 | `baseline.vision_token_budget` | 이미지 한 장의 시각 토큰 상한 |
| 영상 프레임 수 | `baseline.frames` | 같은 영상에서 한 요청에 넣을 장수 |
| 답변 길이 | `baseline.max_new_tokens` | 출력 토큰 상한 |
| 입력+출력 길이 | `baseline.context_per_request` | 요청당 전체 토큰 상한 |
| 자동 비교 후보 | `sweeps` | 기준 설정에서 한 가지씩 바꿔 볼 값 |
| 데이터 위치 | `dataset_root` 또는 `--dataset-root` | 업로드한 데이터 폴더 |
| 평가 일부만 선택 | `case_ids` | JSON에서는 `null`이면 전체, `["city"]`면 city만 |
| 모델 지시문 | `assets/prompt_v3.txt` | 이미지 해석과 태그 출력 규칙 |
| 출력 검사 규칙 | `assets/schema_v3.json` | 필수 키·자료형·태그 수 |
| B 모델·서버 파일 | `backend` | 실제 파일의 경로 |

A에서는 노트북 **3. 바꿔 볼 설정** 셀을 수정하면 됩니다. JSON 파일은 주석을 허용하지 않으므로 설명은 이 문서에 모았습니다. B는 `configs/b_local.json`을 수정합니다. 개인 경로는 `configs/b_local.local.json`으로 복사해 `--config`로 지정하면 Git에 올라가지 않습니다.

`baseline`은 비교 기준값이고 `sweeps`는 실험 후보입니다. 예를 들어 `resolution` 실험에서는 `sweeps.short_edge_px` 값으로 해상도를 바꾸고, 토큰 수와 프레임 수는 `baseline`대로 유지합니다. `selection` 실험은 선택 방법을 비교하도록 6프레임으로 고정합니다.

B의 `concurrency`는 동시에 보내는 독립 요청 수입니다. 영상 프레임 수와 다릅니다. `engine_token_batch`와 `engine_microbatch`도 이미지 개수가 아닌 서버 내부 토큰 처리 설정입니다.

## 실행을 확인하는 순서

1. `--dry-run`: 데이터와 요청 수만 확인합니다. 모델을 로드하지 않습니다.
2. `--mock`: 고정된 테스트 응답으로 저장·검사·리포트를 확인합니다. 평가 데이터를 생성하지 않습니다.
3. `--suite smoke`: 실제 모델로 작은 실행을 확인합니다.
4. 조건 하나를 바꾸고 새 `--run-dir`로 비교합니다.

같은 결과 폴더에서 중단된 실행을 이어가려면 `--resume`을 사용합니다. 입력·코드·설정이 바뀌면 새 결과 폴더를 사용하세요. 완료한 응답은 JSON 형식이 틀려도 재생성하지 않습니다.

## 내부 코드를 읽어야 할 때

- `data.load_cases`: 사진 한 장은 한 건, 영상 프레임 폴더 하나는 한 건으로 만듭니다.
- `data.prepare`: 원본을 메모리에서 축소하고, 시간순 프레임과 해시를 반환합니다.
- `runner.profiles`: 실험별 설정 목록을 만듭니다. 새 비교 항목을 추가할 때 봅니다.
- `runner.run`: 데이터 읽기부터 결과 저장까지 연결합니다.
- `backends.*.infer`: 모델 호출 뒤 원문·토큰 수·시간을 반환합니다.
- `report.build_report`: 저장한 원문으로 리포트를 다시 만듭니다. 모델을 호출하지 않습니다.

실행 코드에는 자동 파일명 변경 기능이 없습니다. 출력 태그·근거와 사람 평가를 비교하는 단계입니다. `tests/`의 작은 임시 이미지는 프로그램 검사용이며 팀의 평가 데이터와 별개입니다.
