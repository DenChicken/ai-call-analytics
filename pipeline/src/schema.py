from typing import Literal

from pydantic import BaseModel, Field, create_model

from src.config import Reference

SCORES_MODEL_NAME = "CriteriaScores"
ANALYSIS_MODEL_NAME = "CallAnalysis"
SCORE_NOT_MET = 0
SCORE_MET = 1

CALL_TYPE_ITEM_TEMPLATE = "{code} ({label}) — {description}"
CALL_TYPE_SEPARATOR = " "
SCORES_DESCRIPTION = (
    "Оценка по каждому критерию: 1 только если в стенограмме есть прямое подтверждение "
    "словами менеджера, иначе 0"
)
SUMMARY_DESCRIPTION = (
    "Кто с кем говорил, о чём и чем закончилось. Строго 2-3 предложения. "
    "Только то, что прозвучало в разговоре"
)
STRENGTHS_DESCRIPTION = "Что менеджер сделал хорошо, с опорой на прозвучавшие реплики"
WEAKNESSES_DESCRIPTION = "Что менеджер упустил. Не повторять то, что уже указано в strengths"
RECOMMENDATIONS_DESCRIPTION = (
    "Конкретное действие на будущее. Не пересказывать weaknesses другими словами"
)


def build_analysis_model(
    criteria: list[Reference], call_types: list[Reference], list_items: int
) -> type[BaseModel]:
    scores_fields = {
        criterion.code: (
            Literal[SCORE_NOT_MET, SCORE_MET],
            Field(..., description=criterion.description),
        )
        for criterion in criteria
    }
    scores_model = create_model(SCORES_MODEL_NAME, **scores_fields)

    def text_list(description: str) -> tuple:
        return (
            list[str],
            Field(..., max_length=list_items, description=description),
        )

    return create_model(
        ANALYSIS_MODEL_NAME,
        summary=(str, Field(..., description=SUMMARY_DESCRIPTION)),
        call_type=(
            Literal[tuple(entry.code for entry in call_types)],
            Field(..., description=_call_type_description(call_types)),
        ),
        scores=(scores_model, Field(..., description=SCORES_DESCRIPTION)),
        strengths=text_list(STRENGTHS_DESCRIPTION),
        weaknesses=text_list(WEAKNESSES_DESCRIPTION),
        recommendations=text_list(RECOMMENDATIONS_DESCRIPTION),
    )


def _call_type_description(call_types: list[Reference]) -> str:
    return CALL_TYPE_SEPARATOR.join(
        CALL_TYPE_ITEM_TEMPLATE.format(
            code=entry.code, label=entry.label, description=entry.description
        )
        for entry in call_types
    )
