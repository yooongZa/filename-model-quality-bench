# 결과와 평가 방법


결과는 `runs/a/<suite>/` 또는 `runs/b/<suite>/`에 저장됩니다. 모의 실행 폴더에는 `_mock`이 붙습니다.

| 파일 | 내용 |
|---|---|
| `report.html` | 조건별 결과, 오류, 원문, CSV 링크 |
| `config.json`, `backend_*.json` | 설정·환경·로드 시간·해시·서버 속성 |
| `eda.json` | 샘플 수, 사진/영상 비율, 크기, 파일 중복 |
| `references.json` | 실행 당시의 답안·검수 기준 복사본. 모델에는 전달하지 않음 |
| `requests.jsonl` | 요청별 설정·프레임·응답·형식 검사·시간 |
| `summary.csv`, `metrics.csv` | 조건별 요약·요청별 수치 |
| `review.csv` | 사람 평가 입력란과 답안·관찰 기준 |
| `telemetry.jsonl` | 그룹별 시간·메모리·활성 슬롯 표본 |
| `calibration.jsonl` | 컨텍스트 채우기 전 보정 요청 |
| `events.jsonl`, `server_*.log` | 시작 오류 및 서버 로그; 해당 이벤트가 있을 때 생성 |

정답은 팀이 업로드한 `answers/샘플ID.json`에서 읽습니다. 정답을 자동 생성하지 않습니다. 정답이 없으면 문자열 일치 진단값은 빈칸이고, JSON 검사·시간·오류와 사람 평가를 사용할 수 있습니다. 출력 규칙은 **v3 최대 태그 5개·4필드**입니다. 사람 검수 여부는 `manifest.json`의 `human_reviewed`로 기록합니다.

자동 검사는 원문을 고치지 않고 JSON을 파싱한 뒤 필수 키·자료형·태그 개수·문자 길이·추가 키를 확인합니다. 코드 블록 제거, JSON 복구, 임의 태그 삭제를 적용하지 않습니다. `json_valid`와 `schema_valid`는 실행 오류와 별개로 기록합니다. 실패도 전체 시도의 비율 분모에 들어갑니다. 모델 로드 실패는 요청이 실행되지 않았으므로 별도 이벤트와 계획 대비 누락으로 표시합니다.

`review.csv`의 사람 평가 기준:

| 필드 | 입력 기준 |
|---|---|
| `tag_precision_0to1` | 화면 근거가 있는 태그 수 ÷ 출력 태그 수. 태그가 없으면 빈칸 |
| `core_recall_0to1` | 포착한 정답 핵심 개념 수 ÷ 정답 핵심 개념 수 |
| `unsupported_claim_0or1` | 태그·근거·지명 중 관찰로 뒷받침되지 않는 주장이 있으면 1 |
| `temporal_evidence_0to2` | 영상 핵심 변화: 오류·누락 0, 일부 1, 충분히 반영 2. 사진은 빈칸 |
| `needs_review_correct_0or1` | 검토 필요 판단이 정답 기준과 맞으면 1 |
| `notes` | 판단 이유·모호한 동의어·개선할 사례 |

문자열 일치 precision/recall은 `metrics.csv`의 진단용 값입니다. 동의어를 자동으로 이해하지 못하므로 모델의 최종 의미 점수로 사용하지 않습니다. 사람 입력은 리포트 재생성 시 유지됩니다. 이 예제는 사람 평가 점수를 자동 합산하거나 종합 순위를 만들지 않습니다.

```bash
python make_report.py runs/a/resolution --dataset-root data/evaluation
```
