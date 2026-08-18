from typing import Literal

from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig
from pydantic import BaseModel, Field, create_model

from src.config import Criterion
from src.constants import (
    CALL_TYPE_NOT_SALES,
    CALL_TYPE_SALES,
    ROLE_CLIENT,
    ROLE_MANAGER,
)

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


class DialogTurn(BaseModel):
    model_config = {"extra": "forbid"}

    role: Literal[ROLE_MANAGER, ROLE_CLIENT] = Field(
        ..., description="Кто произнёс реплику: manager или client"
    )
    time: str = Field(..., description="Время начала реплики в формате ММ:СС")
    text: str = Field(..., description="Текст реплики целиком")


class Dialog(BaseModel):
    model_config = {"extra": "forbid"}

    dialog: list[DialogTurn] = Field(..., description="Разговор, разбитый на реплики по очереди")


def parser_config() -> CharacterLevelParserConfig:
    alphabet = "".join(chr(code) for code in range(*ASCII_PRINTABLE_RANGE))
    alphabet += "".join(chr(code) for code in range(*CYRILLIC_RANGE))
    return CharacterLevelParserConfig(alphabet=alphabet + CYRILLIC_EXTRA)


def build_analysis_model(criteria: list[Criterion]) -> type[BaseModel]:
    scores_fields = {
        criterion.code: (
            Literal[SCORE_NOT_MET, SCORE_MET],
            Field(..., description=criterion.description),
        )
        for criterion in criteria
    }
    scores_model = create_model(SCORES_MODEL_NAME, **scores_fields)

    return create_model(
        ANALYSIS_MODEL_NAME,
        call_type=(
            Literal[CALL_TYPE_SALES, CALL_TYPE_NOT_SALES],
            Field(..., description=CALL_TYPE_DESCRIPTION),
        ),
        scores=(scores_model, Field(..., description="Оценки менеджера по каждому критерию")),
        summary=(str, Field(..., description="Краткое содержание разговора")),
        strengths=(list[str], Field(..., description="Список сильных сторон менеджера")),
        weaknesses=(
            list[str],
            Field(..., description="Список слабых сторон менеджера и точек роста"),
        ),
        recommendations=(
            list[str],
            Field(..., description="Что менеджеру сделать иначе в следующий раз"),
        ),
    )
