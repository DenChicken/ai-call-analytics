from typing import Literal

from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig
from pydantic import BaseModel, Field, create_model

from src.config import Criterion, OutputConfig
from src.constants import CALL_TYPE_NOT_SALES, CALL_TYPE_SALES

ASCII_PRINTABLE_RANGE = (0x20, 0x7F)
CYRILLIC_RANGE = (0x0410, 0x0450)
CYRILLIC_EXTRA = "Ёё"

SCORES_MODEL_NAME = "CriteriaScores"
ANALYSIS_MODEL_NAME = "CallAnalysis"
SCORE_NOT_MET = 0
SCORE_MET = 1

CALL_TYPE_DESCRIPTION = (
    "sales — разговор менеджера с клиентом о товаре или услуге; "
    "not_sales — всё остальное: разговор между сотрудниками, личный разговор, "
    "автоответчик, гудки, обрыв связи"
)
SCORES_DESCRIPTION = "Оценки менеджера по каждому критерию"
SUMMARY_DESCRIPTION = "Краткое содержание разговора"
STRENGTHS_DESCRIPTION = "Список сильных сторон менеджера"
WEAKNESSES_DESCRIPTION = "Список слабых сторон менеджера и точек роста"
RECOMMENDATIONS_DESCRIPTION = "Что менеджеру сделать иначе в следующий раз"


def parser_config() -> CharacterLevelParserConfig:
    alphabet = "".join(chr(code) for code in range(*ASCII_PRINTABLE_RANGE))
    alphabet += "".join(chr(code) for code in range(*CYRILLIC_RANGE))
    return CharacterLevelParserConfig(alphabet=alphabet + CYRILLIC_EXTRA)


def build_analysis_model(criteria: list[Criterion], output: OutputConfig) -> type[BaseModel]:
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
            Literal[CALL_TYPE_SALES, CALL_TYPE_NOT_SALES],
            Field(..., description=CALL_TYPE_DESCRIPTION),
        ),
        scores=(scores_model, Field(..., description=SCORES_DESCRIPTION)),
        summary=(str, Field(..., description=SUMMARY_DESCRIPTION)),
        strengths=text_list(STRENGTHS_DESCRIPTION),
        weaknesses=text_list(WEAKNESSES_DESCRIPTION),
        recommendations=text_list(RECOMMENDATIONS_DESCRIPTION),
    )
