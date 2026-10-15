# 선택 모델과 실행 파일

팀이 선택한 모델은 **`google/gemma-4-12b-qat`**입니다. 이 이름은 [LM Studio의 모델 표시명](https://lmstudio.ai/models/google/gemma-4-12b-qat)입니다. Hugging Face에서 내려받는 저장소 ID는 구분해서 사용합니다.

| 항목 | A: Colab 품질 실험 | B: 로컬 용량 실험 |
|---|---|---|
| 표시명 | `google/gemma-4-12b-qat` | `google/gemma-4-12b-qat` |
| 실제 저장소 | `google/gemma-4-12B-it-qat-q4_0-unquantized` | `lmstudio-community/gemma-4-12B-it-QAT-GGUF` |
| 실행 도구 | Transformers / CUDA | llama-server / CUDA 또는 Metal |
| 실행 정밀도 | BF16, QAT 학습 체크포인트 | Q4_0 GGUF + BF16 mmproj |
| 기록 | 저장소 ID·revision·자료형·모델 종류 | GGUF·mmproj·서버 해시·선언한 양자화 |

QAT(양자화 인지 학습)는 학습 방법입니다. A의 `unquantized` 가중치는 BF16으로 실행하므로 **A 결과를 로컬 Q4 성능으로 해석할 수 없습니다.** A에서 입력 조건을 비교한 뒤, 최종 후보를 B의 실제 파일과 장비로 다시 평가하세요. 두 실험 사이에는 실행 도구 차이도 있습니다.

A는 확인한 모델 revision `b6ed86275a6a5735884e208bfed95b445a684ca2`를 고정합니다. 모델 구조는 `gemma4_unified`입니다. 기존 Transformers 5.9에는 이 구조의 자동 모델 매핑이 없어, 대응 매핑을 확인한 5.19 이상으로 의존성을 올렸습니다. `backend_*.json`에 실제 로드한 버전과 정밀도가 남습니다.

B의 기본 파일 경로는 LM Studio 모델 페이지가 연결하는 아래 파일 이름을 사용합니다. 모델과 mmproj를 같은 저장소에서 준비하고 `configs/b_local.json`의 경로를 실제 위치로 수정하세요.

```text
gemma-4-12B-it-QAT-Q4_0.gguf
mmproj-gemma-4-12B-it-QAT-BF16.gguf
```

B의 양자화 이름과 출처는 사용자가 지정한 값입니다. 파일 내용은 해시로 식별하고, 실제 GPU offload(오프로딩)는 서버 로그에서 확인합니다. 이 저장소는 가중치를 자동 다운로드하지 않습니다. 8GB VRAM에서의 실행 가능 여부는 실제 측정이 필요합니다.

## 공식 출처

- [LM Studio 모델과 연결된 파일 저장소](https://lmstudio.ai/models/google/gemma-4-12b-qat)
- [Google QAT BF16 체크포인트](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-unquantized)
- [LM Studio GGUF 파일](https://huggingface.co/lmstudio-community/gemma-4-12B-it-QAT-GGUF/tree/main)
- [Google 공식 Q4 GGUF 대안](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf)
- [Gemma 4 Unified 전처리와 모델](https://huggingface.co/docs/transformers/model_doc/gemma4_unified)
- [Transformers 5.19 모델 매핑](https://github.com/huggingface/transformers/blob/v5.19.0/src/transformers/models/auto/modeling_auto.py)
