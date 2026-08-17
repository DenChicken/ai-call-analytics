from typing import Literal

from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig
from pydantic import BaseModel, Field, create_model

from src.config import Criterion

ASCII_PRINTABLE_RANGE = (0x20, 0x7F)
CYRILLIC_RANGE = (0x0410, 0x0450)
CYRILLIC_EXTRA = "Ёё"

SCORES_MODEL_NAME = "CriteriaScores"
ANALYSIS_MODEL_NAME = "CallAnalysis"
ROLES_MODEL_NAME = "SpeakerRoles"
SCORE_NOT_MET = 0
SCORE_MET = 1

ROLE_MANAGER = "manager"
ROLE_CLIENT = "client"
ROLE_FIELD_TEMPLATE = "line_{index}"

ROLES_DESCRIPTION = "Кто произнёс реплику номер {index}"
SUMMARY_DESCRIPTION = "Краткое содержание разговора"
STRENGTHS_DESCRIPTION = "Список сильных сторон менеджера"
WEAKNESSES_DESCRIPTION = "Список слабых сторон менеджера и точек роста"
SCORES_DESCRIPTION = "Оценки менеджера по каждому критерию"


def parser_config() -> CharacterLevelParserConfig:
    alphabet = "".join(chr(code) for code in range(*ASCII_PRINTABLE_RANGE))
    alphabet += "".join(chr(code) for code in range(*CYRILLIC_RANGE))
    return CharacterLevelParserConfig(alphabet=alphabet + CYRILLIC_EXTRA)


def role_field_name(index: int) -> str:
    return ROLE_FIELD_TEMPLATE.format(index=index)


def build_roles_model(segment_count: int) -> type[BaseModel]:
    fields = {
        role_field_name(index): (
            Literal[ROLE_MANAGER, ROLE_CLIENT],
            Field(..., description=ROLES_DESCRIPTION.format(index=index)),
        )
        for index in range(segment_count)
    }
    return create_model(ROLES_MODEL_NAME, **fields)


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
        scores=(scores_model, Field(..., description=SCORES_DESCRIPTION)),
        summary=(str, Field(..., description=SUMMARY_DESCRIPTION)),
        strengths=(list[str], Field(..., description=STRENGTHS_DESCRIPTION)),
        weaknesses=(list[str], Field(..., description=WEAKNESSES_DESCRIPTION)),
    )
