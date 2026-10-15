# 팀 평가 데이터 업로드

팀이 준비한 사진·프레임·원본 영상을 사용합니다. `videos/`의 MP4·MOV 등은 FFmpeg로 대표 프레임을 추출합니다. 기본은 10초당 1장·최대 5장이며, 5장이면 영상의 10%·30%·50%·70%·90% 시점입니다. [추출 설정과 실행](VIDEO_FRAMES.md)을 참고하세요. 평가 사진과 정답을 합성하는 기능은 없습니다. 지원 이미지 형식은 JPG·JPEG·PNG·WEBP·BMP입니다.

## 가장 쉬운 폴더 형식

```text
evaluation/
  images/
    city.jpg
    picnic.jpg
  videos/
    cycling.mp4
  answers/
    city.json
    picnic.json
    cycling.json
```

이 폴더를 `evaluation.zip`으로 압축해 Google Drive의 **내 드라이브/filename/datasets/**에 올리고, Colab 노트북의 **2. Google Drive 연결과 데이터 준비**를 실행합니다. 사진만 또는 영상만 있는 ZIP도 됩니다. 압축 해제 후 기본 상한은 2GB·10,000개 항목입니다. Colab에 올릴 수 있는 자료인지 팀에서 확인하세요.

로컬에서는 다음과 같이 가져옵니다.

```bash
python upload_dataset.py evaluation.zip --destination data/evaluation
```

명령이 출력한 데이터 경로를 실행 시 `--dataset-root "경로"`로 지정하세요. ZIP에 바깥 폴더가 있으면 실제 경로가 `data/evaluation/evaluation`일 수 있습니다. 압축을 직접 풀었다면 `images/`·`videos/` 또는 기존 `frames/`를 포함한 폴더를 지정합니다.

사진과 영상 파일명에서 확장자를 뺀 값(`city`, `cycling`)이 샘플 ID입니다. `videos/cycling.mp4`의 정답은 `answers/cycling.json`입니다. **팀은 영상 전체를 보고 정답 한 개를 작성합니다. 프레임 추출과 프레임별 파일 이름은 코드가 처리합니다.** 기존 프레임을 직접 쓰고 싶을 때만 `frames/영상ID/001.jpg` 형식을 사용하며, 이 경우 영상 폴더 이름이 ID입니다. 같은 영상을 원본과 프레임 폴더 양쪽에 중복 등록하지 마세요. ID는 전체에서 유일해야 합니다. 프레임은 파일명의 숫자 순서로 읽습니다(`1, 2, 10`). `001.jpg`처럼 시간순으로 이름을 맞추세요. 파일 수정 시각으로 촬영 순서를 추정하지 않습니다.

Colab의 기본 `VIDEO_FRAMES="all"`은 자동 추출한 프레임을 모두 한 요청에 넣습니다. 터미널에서도 `--frames all`을 지정하면 됩니다. 숫자 설정은 후보 중 그 장수만 선택합니다. 사진만 올리면 영상 조건을 건너뜁니다. 후보보다 많은 프레임을 요청하면 `unsupported`로 기록합니다. 후보를 복제해 채우지 않습니다. `frames` 비교 목록을 `[1, 3]` 등 보유 수에 맞추거나 최대 12장 이상의 후보를 준비하세요. `selection` 비교는 후보 중 6장을 고릅니다.

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

영상 정답의 `keywords`에는 영상 전체의 핵심 대상·행동·배경을 종합합니다. 추출된 각 프레임에 별도 정답을 만들지 않습니다. `reason`에는 주요 행동 변화가 있으면 짧게 포함합니다.

`keywords`는 최대 5개, `reason`은 1~120자입니다. 파일명은 태그를 조합하므로 모델 출력에 `title`을 요구하지 않습니다. `answers/`는 모델 입력에 전달하지 않습니다. 정답이 없으면 자동 의미 관련 진단값은 빈칸입니다. 정답을 전부 사람이 검수했다면 선택 파일 `manifest.json`에 `{"human_reviewed": true}`를 기록하세요. 사진 수·크기·중복 해시는 입력에서 계산합니다.

같은 영상의 프레임이 개발용과 최종 확인용에 나뉘어 들어가지 않도록 촬영 묶음 단위로 분리하세요.

## 기존 입력 목록을 유지하는 경우

`model_inputs.jsonl`이 있으면 폴더 자동 인식보다 우선합니다. 한 줄이 평가 한 건이며 모든 경로는 데이터 루트 기준입니다. 영상 프레임 순서는 배열 순서를 따릅니다.

```json
{"id":"city","media_type":"image","image_paths":["images/city.jpg"]}
{"id":"cycling","media_type":"video","video_path":"videos/cycling.mp4"}
```

기존의 `manifest.json` 프레임 시간 정보와 `reviewer/annotation_notes.json`도 선택적으로 읽습니다. 저장소는 이미지·정답·가중치를 배포하지 않습니다.
