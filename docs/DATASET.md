# 데이터 준비

이 저장소에는 사진·영상 데이터와 모델 가중치를 포함하지 않습니다. 기존 평가 묶음을 아래 위치에 준비하거나 설정의 dataset_root를 수정하세요. 경로는 설정 파일이 있는 폴더 기준입니다.

```text
data/filename_eval24_1080/
  model_inputs.jsonl
  manifest.json                   # 선택: EDA·프레임 시간·검수 여부
  media/images/I01.png
  frames/V01/F01.png ... F12.png
  answers/I01.json ... V01.json    # 선택: 참조 답안
  reviewer/annotation_notes.json  # 선택: 사람 평가 기준
```

필수 model_inputs.jsonl의 한 줄은 하나의 사진 또는 영상입니다.

```json
{"id":"I01","media_type":"image","image_paths":["media/images/I01.png"]}
{"id":"V01","media_type":"video","image_paths":["frames/V01/F01.png","frames/V01/F02.png","frames/V01/F03.png"]}
```

영상 경로는 시간순으로 넣습니다. 위는 3장 형식 예시이며 기본 A smoke의 12프레임과 프레임 선택 실험에는 실제로 서로 다른 12장이 필요합니다. 부족한 프레임을 복제해 채우지 않습니다. 기본 B 설정에는 I03도 있으므로 데이터에 맞게 case_ids를 수정하세요. case_ids를 null로 두면 전체 입력을 사용합니다.

참조 답안은 keywords·reason·place_name·needs_review의 4개 필드입니다. 최대 태그 수는 5개입니다. answers와 reviewer 파일은 평가에만 사용하고 모델 입력에 넣지 않습니다.

촬영 묶음·영상 단위로 개발용과 최종 확인용 데이터를 분리하고 정답의 독립 사람 검수 여부를 기록하세요. 입력 파일의 SHA-256 해시를 실험 결과에 기록합니다.
