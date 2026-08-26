import logging
from dataclasses import dataclass

from pydantic import ValidationError

from src.config import Config, Reference
from src.constants import (
    CRITERIA_LINE_TEMPLATE,
    ERROR_LLM_INVALID_OUTPUT,
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
    UNKNOWN_MANAGER,
)
from src.errors import StageError
from src.llm import Llm
from src.schema import build_analysis_model

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Analysis:
    call_type: str
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    scores: dict[str, int]


def render_criteria(criteria: list[Reference]) -> str:
    return "\n".join(
        CRITERIA_LINE_TEMPLATE.format(
            label=criterion.label,
            description=criterion.description,
        )
        for criterion in criteria
    )


def analyze(
    config: Config,
    llm: Llm,
    criteria: list[Reference],
    call_types: list[Reference],
    plain: str,
    manager_name: str | None,
) -> Analysis:
    logger.debug(
        "analyzing %s characters against %s criteria and %s call types",
        len(plain),
        len(criteria),
        len(call_types),
    )
    model = build_analysis_model(criteria, call_types, config.llm.output.list_items)
    prompt = config.prompt.user.format(
        **{
            PROMPT_CRITERIA_PLACEHOLDER: render_criteria(criteria),
            PROMPT_MANAGER_PLACEHOLDER: manager_name or UNKNOWN_MANAGER,
            PROMPT_TRANSCRIPT_PLACEHOLDER: plain,
        }
    )
    raw = llm.generate(config.prompt.system, prompt, model.model_json_schema())
    try:
        payload = model.model_validate(raw).model_dump()
    except ValidationError as error:
        raise StageError(
            ERROR_LLM_INVALID_OUTPUT, f"model output does not match the schema: {error}"
        ) from error

    analysis = Analysis(**payload)
    logger.info(
        "call classified as %s, %s of %s criteria met",
        analysis.call_type,
        sum(analysis.scores.values()),
        len(analysis.scores),
    )
    return analysis
