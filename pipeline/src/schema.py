from typing import Literal

from pydantic import BaseModel, Field, create_model

from src.config import Reference

SCORES_MODEL_NAME = "CriteriaScores"
ANALYSIS_MODEL_NAME = "CallAnalysis"
SCORE_NOT_MET = 0
SCORE_MET = 1


def build_analysis_model(
    criteria: list[Reference], call_types: list[Reference], list_items: int
) -> type[BaseModel]:
    scores_model = create_model(
        SCORES_MODEL_NAME,
        **{
            entry.code: (Literal[SCORE_NOT_MET, SCORE_MET], ...)
            for entry in criteria
        },
    )

    text_list = (list[str], Field(..., max_length=list_items))

    return create_model(
        ANALYSIS_MODEL_NAME,
        summary=(str, ...),
        call_type=(Literal[tuple(entry.code for entry in call_types)], ...),
        strengths=text_list,
        weaknesses=text_list,
        scores=(scores_model, ...),
        recommendations=text_list,
    )
