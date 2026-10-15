# 검증 기록

- 프로젝트 명칭: filename
- 자동 테스트: 5개 통과
- Python·설정 JSON·공개 업로드 파일 구조: 통과
- 실제 평가 입력을 사용한 모의 실행: 3요청 통과
- 코드·문서·설정에 이전 프로젝트 명칭이 남지 않았는지 확인
- 실제 GPU 추론: 미실행

검증 명령:

```bash
python -m unittest discover -s tests -v
python a_quality.py --config configs/a_quality.local.json --mock
```

로컬 검증에서는 Git에서 제외되는 설정 파일로 평가 데이터 위치를 지정했습니다. 결과·절대 데이터 경로·미디어·모델은 커밋하지 않습니다.

Colab 노트북은 로컬 데이터 경로만 임시 지정한 복사본을 새 커널에서 모의 실행했습니다. 배포 노트북에는 실행 출력이 없습니다.

Based-On: none — 직접 대응하는 LMS 예제가 없어 작성한 project_extension입니다. LMS 원문은 포함하지 않습니다.
