from typing import Literal

from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig
from pydantic import BaseModel, Field, create_model

from src.config import OutputConfig, Reference

ASCII_PRINTABLE_RANGE = (0x20, 0x7F)
CYRILLIC_RANGE = (0x0410, 0x0450)
CYRILLIC_EXTRA = "Ёё"

SCORES_MODEL_NAME = "CriteriaScores"
ANALYSIS_MODEL_NAME = "CallAnalysis"
SCORE_NOT_MET = 0
SCORE_MET = 1

CALL_TYPE_ITEM_TEMPLATE = "{code} ({label}) — {description}"
CALL_TYPE_SEPARATOR = " "
SCORES_DESCRIPTION = "Оценки менеджера по каждому критерию"
SUMMARY_DESCRIPTION = "Краткое содержание разговора"
STRENGTHS_DESCRIPTION = "Список сильных сторон менеджера"
WEAKNESSES_DESCRIPTION = "Список слабых сторон менеджера и точек роста"
RECOMMENDATIONS_DESCRIPTION = "Что менеджеру сделать иначе в следующий раз"


def parser_config() -> CharacterLevelParserConfig:
    alphabet = "".join(chr(code) for code in range(*ASCII_PRINTABLE_RANGE))
    alphabet += "".join(chr(code) for code in range(*CYRILLIC_RANGE))
    return CharacterLevelParserConfig(alphabet=alphabet + CYRILLIC_EXTRA)


def build_analysis_model(
    criteria: list[Reference], call_types: list[Reference], output: OutputConfig
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
            Field(..., max_length=output.list_items, description=description),
        )

    return create_model(
        ANALYSIS_MODEL_NAME,
        call_type=(
            Literal[tuple(entry.code for entry in call_types)],
            Field(..., description=_call_type_description(call_types)),
        ),
        scores=(scores_model, Field(..., description=SCORES_DESCRIPTION)),
        summary=(str, Field(..., description=SUMMARY_DESCRIPTION)),
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
