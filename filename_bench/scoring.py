"""허용 태그 일치율을 참고값으로 계산합니다. 최종 품질은 사람이 평가합니다."""
from __future__ import annotations

import unicodedata

SCORING_VERSION = "allowed-tags-reference-v2"


def normalize_tag(tag):
    """한글 조합형·공백·영문 대소문자 차이만 정리합니다. 의미를 추측하지 않습니다."""
    return "".join(unicodedata.normalize("NFC", tag).split()).casefold()


def reference_tags(answer):
    """사람이 작성한 3개 필드를 검사합니다. 허용 태그 수에는 제한이 없습니다.

    과거 정답에 추가 필드가 있어도 읽을 수 있지만 평가에는 사용하지 않습니다.
    """
    if not isinstance(answer, dict):
        raise ValueError("정답은 JSON 객체여야 합니다.")

    def check_tags(tags, label):
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not normalize_tag(tag) for tag in tags):
            raise ValueError(f"{label}에는 비어 있지 않은 문자열 배열을 넣으세요.")

    check_tags(answer.get("keywords"), "keywords")
    if not isinstance(answer.get("reason"), str) or not answer["reason"].strip():
        raise ValueError("reason에 관찰 근거를 작성하세요.")
    if "place_name" not in answer or (answer["place_name"] is not None and
            (not isinstance(answer["place_name"], str) or not answer["place_name"].strip())):
        raise ValueError("place_name은 지명 문자열 또는 null이어야 합니다.")
    return {normalize_tag(tag) for tag in answer["keywords"]}


def score_tags(predicted, answer):
    """목록에 포함된 출력 태그 수 / 출력 태그 수. 장면 이해나 유용성 점수는 아닙니다."""
    allowed = reference_tags(answer)
    normalized = [normalize_tag(tag) for tag in predicted]
    matched = [tag for tag, value in zip(predicted, normalized) if value in allowed]
    unmatched = [tag for tag, value in zip(predicted, normalized) if value not in allowed]
    return {
        "allowed_tag_match_rate": len(matched) / len(predicted) if predicted else None,
        "output_tag_count": len(predicted),
        "allowed_reference_tag_count": len(allowed),
        "matched_allowed_tags": matched,
        "unmatched_tags": unmatched,
    }
