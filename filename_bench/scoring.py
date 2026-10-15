"""사람이 작성한 허용 태그 목록과 핵심 개념으로 채점합니다. 모델을 호출하지 않습니다."""
from __future__ import annotations

import unicodedata

SCORING_VERSION = "allowed-tags-core-v1"


def normalize_tag(tag):
    """한글 조합형·공백·영문 대소문자 차이만 정리합니다. 의미를 추측하지 않습니다."""
    return "".join(unicodedata.normalize("NFC", tag).split()).casefold()


def reference_tags(answer):
    """정답을 검사하고 허용 목록과 핵심 동의어 묶음을 반환합니다.

    keywords는 개수 제한이 없는 허용 목록입니다. core_keywords의 각 묶음은
    꼭 포착해야 할 개념 하나이며, 그 안의 표현도 허용 목록에 포함됩니다.
    기존 4필드 정답은 그대로 사용하지만 핵심 개념 재현율은 계산하지 않습니다.
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
    if type(answer.get("needs_review")) is not bool:
        raise ValueError("needs_review는 true 또는 false여야 합니다.")

    groups = answer.get("core_keywords", [])
    if not isinstance(groups, list) or len(groups) > 5:
        raise ValueError("core_keywords에는 핵심 개념 묶음을 최대 5개 넣으세요. 모델 출력도 최대 5개입니다.")
    allowed = {normalize_tag(tag) for tag in answer["keywords"]}
    normalized_groups, used = [], set()
    for group in groups:
        check_tags(group, "core_keywords의 각 묶음")
        if not group:
            raise ValueError("핵심 개념 묶음에는 허용 표현을 한 개 이상 넣으세요.")
        normalized = {normalize_tag(tag) for tag in group}
        if used & normalized:
            raise ValueError("같은 표현을 서로 다른 핵심 개념 묶음에 넣을 수 없습니다.")
        used.update(normalized)
        allowed.update(normalized)
        normalized_groups.append(normalized)
    return allowed, groups, normalized_groups


def score_tags(predicted, answer):
    """허용된 출력 태그 비율과 핵심 개념 포함률을 서로 다른 분모로 계산합니다."""
    allowed, groups, normalized_groups = reference_tags(answer)
    normalized = [normalize_tag(tag) for tag in predicted]
    matched = [tag for tag, value in zip(predicted, normalized) if value in allowed]
    unmatched = [tag for tag, value in zip(predicted, normalized) if value not in allowed]
    predicted_set = set(normalized)
    # 같은 개념의 동의어가 여러 번 나와도 이 목록에는 한 번만 들어갑니다.
    matched_core = [group[0] for group, values in zip(groups, normalized_groups) if values & predicted_set]
    missing_core = [group[0] for group, values in zip(groups, normalized_groups) if not values & predicted_set]
    return {
        "allowed_tag_precision": len(matched) / len(predicted) if predicted else None,
        "core_tag_recall": len(matched_core) / len(groups) if groups else None,
        "output_tag_count": len(predicted),
        "allowed_reference_tag_count": len(allowed),
        "core_group_count": len(groups),
        "matched_allowed_tags": matched,
        "unmatched_tags": unmatched,
        "matched_core_groups": matched_core,
        "missing_core_groups": missing_core,
    }
