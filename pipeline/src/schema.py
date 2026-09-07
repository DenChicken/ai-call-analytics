from typing import Literal

from pydantic import BaseModel, Field, create_model

from src.config import Fields, Reference

SCORES_MODEL_NAME = "CriteriaScores"
ANALYSIS_MODEL_NAME = "CallAnalysis"
SCORE_NOT_MET = 0
SCORE_MET = 1

CALL_TYPE_ITEM_TEMPLATE = "{code} ({label}) — {description}"
CALL_TYPE_SEPARATOR = "; "
CALL_TYPE_DESCRIPTION_TEMPLATE = "{description} Возможные значения: {options}."


def build_analysis_model(
    criteria: list[Reference], call_types: list[Reference], fields: Fields, list_items: int
) -> type[BaseModel]:
    scores_model = create_model(
        SCORES_MODEL_NAME,
        **{
            entry.code: (
                Literal[SCORE_NOT_MET, SCORE_MET],
                Field(..., description=entry.description),
            )
            for entry in criteria
        },
    )

    def text_list(description: str) -> tuple:
        return list[str], Field(..., max_length=list_items, description=description)

    return create_model(
        ANALYSIS_MODEL_NAME,
        summary=(str, Field(..., description=fields.summary)),
        call_type=(
            Literal[tuple(entry.code for entry in call_types)],
            Field(..., description=_call_type_description(call_types, fields.call_type)),
        ),
        scores=(scores_model, Field(..., description=fields.scores)),
        strengths=text_list(fields.strengths),
        weaknesses=text_list(fields.weaknesses),
        recommendations=text_list(fields.recommendations),
    )


def _call_type_description(call_types: list[Reference], description: str) -> str:
    return CALL_TYPE_DESCRIPTION_TEMPLATE.format(
        description=description,
        options=CALL_TYPE_SEPARATOR.join(
            CALL_TYPE_ITEM_TEMPLATE.format(
                code=entry.code, label=entry.label, description=entry.description
            )
            for entry in call_types
        ),
    )
