# 팀 평가 데이터 업로드

팀이 준비한 사진·영상 프레임을 사용합니다. 코드에서 평가 이미지, 프레임 또는 정답을 생성하지 않습니다. 지원 이미지 형식은 JPG·JPEG·PNG·WEBP·BMP입니다. MP4는 직접 입력하지 않으므로, 영상은 미리 추출한 프레임으로 준비하세요.

## 가장 쉬운 폴더 형식

```text
evaluation/
  images/
    city.jpg
    picnic.jpg
  frames/
    cycling/
      001.jpg
      002.jpg
      003.jpg
```

이 폴더를 ZIP으로 묶어 Colab 노트북의 **2. 팀 데이터 업로드**에서 선택합니다. 사진만 또는 영상만 있는 ZIP도 됩니다. 압축 해제 후 기본 상한은 2GB·10,000개 항목입니다. Colab에 올릴 수 있는 자료인지 팀에서 확인하세요.

로컬에서는 다음과 같이 가져옵니다.

```bash
python upload_dataset.py evaluation.zip --destination data/evaluation
```

명령이 출력한 데이터 경로를 실행 시 `--dataset-root "경로"`로 지정하세요. ZIP에 바깥 폴더가 있으면 실제 경로가 `data/evaluation/evaluation`일 수 있습니다. 압축을 직접 풀었다면 `images/`와 `frames/`를 포함한 폴더를 지정합니다.

사진 파일명에서 확장자를 뺀 값(`city`)과 영상 폴더 이름(`cycling`)이 샘플 ID입니다. ID는 전체에서 유일해야 합니다. 프레임은 파일명의 숫자 순서로 읽습니다(`1, 2, 10`). `001.jpg`처럼 시간순으로 이름을 맞추세요. 파일 수정 시각으로 촬영 순서를 추정하지 않습니다.

기본 smoke(간이 실행)는 영상당 3프레임입니다. 사진만 올리면 영상 조건을 건너뜁니다. 후보보다 많은 프레임을 요청하면 `unsupported`로 기록합니다. 후보를 복제해 채우지 않습니다. `frames` 비교 목록을 `[1, 3]` 등 보유 수에 맞추거나 최대 12장 이상의 후보를 준비하세요. `selection` 비교는 후보 중 6장을 고릅니다.

새 업로드는 새 폴더로 가져옵니다. 기존 폴더를 덮어쓰지 않습니다. 가져오기가 중단되거나 이미지 검증에 실패하면 남은 파일은 보존됩니다. 오류를 고친 ZIP을 새 목적지에 올리세요. 이미 성공한 데이터는 출력된 경로를 재사용하면 됩니다.

## 정답은 선택 사항

정답 없이도 JSON 형식·지연 시간·오류를 기록하고 사람이 응답을 검토할 수 있습니다. 태그의 자동 문자열 일치 점수가 필요하면 팀이 `answers/샘플ID.json`을 작성합니다. 예를 들어 `answers/city.json`의 구조는 아래와 같습니다. 아래 내용은 **구조 설명용**이며 실제 사진을 보고 작성해야 합니다.

```json
{
  "keywords": ["실제 관찰한 태그"],
  "reason": "사진에서 확인한 근거",
  "place_name": null,
  "needs_review": false
}
```

`keywords`는 최대 5개, `reason`은 1~120자입니다. 파일명은 태그를 조합하므로 모델 출력에 `title`을 요구하지 않습니다. `answers/`는 모델 입력에 전달하지 않습니다. 정답이 없으면 자동 의미 관련 진단값은 빈칸입니다. 정답을 전부 사람이 검수했다면 선택 파일 `manifest.json`에 `{"human_reviewed": true}`를 기록하세요. 사진 수·크기·중복 해시는 입력에서 계산합니다.

같은 영상의 프레임이 개발용과 최종 확인용에 나뉘어 들어가지 않도록 촬영 묶음 단위로 분리하세요.

## 기존 입력 목록을 유지하는 경우

`model_inputs.jsonl`이 있으면 폴더 자동 인식보다 우선합니다. 한 줄이 평가 한 건이며 모든 경로는 데이터 루트 기준입니다. 영상 프레임 순서는 배열 순서를 따릅니다.

```json
{"id":"city","media_type":"image","image_paths":["images/city.jpg"]}
{"id":"cycling","media_type":"video","image_paths":["frames/cycling/001.jpg","frames/cycling/002.jpg","frames/cycling/003.jpg"]}
```

기존의 `manifest.json` 프레임 시간 정보와 `reviewer/annotation_notes.json`도 선택적으로 읽습니다. 저장소는 이미지·정답·가중치를 배포하지 않습니다.
