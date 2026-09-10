import logging

from pydantic import ValidationError

from src.config import Config, Reference
from src.constants import (
    ERROR_LLM_INVALID_OUTPUT,
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
    PROMPT_TYPES_PLACEHOLDER,
    REFERENCE_LINE_TEMPLATE,
    UNKNOWN_MANAGER,
)
from src.errors import CallError
from src.llm import Llm
from src.models import Analysis
from src.schema import build_analysis_model

logger = logging.getLogger(__name__)


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
    prompt = config.user_prompt.format(
        **{
            PROMPT_CRITERIA_PLACEHOLDER: _render(criteria),
            PROMPT_TYPES_PLACEHOLDER: _render(call_types),
            PROMPT_MANAGER_PLACEHOLDER: manager_name or UNKNOWN_MANAGER,
            PROMPT_TRANSCRIPT_PLACEHOLDER: plain,
        }
    )
    raw = llm.generate(config.system_prompt, prompt, model.model_json_schema())

    try:
        payload = model.model_validate(raw).model_dump()
    except ValidationError as error:
        raise CallError(
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


def _render(entries: list[Reference]) -> str:
    return "\n".join(
        REFERENCE_LINE_TEMPLATE.format(
            code=entry.code, label=entry.label, description=entry.description
        )
        for entry in entries
    )
