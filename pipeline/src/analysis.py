import logging

from src.config import Config, Reference
from src.constants import (
    CALL_TYPE_FIELD,
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
    SCORES_FIELD,
    UNKNOWN_MANAGER,
)
from src.llm import Llm
from src.schema import build_analysis_model
from src.transcript import render_criteria

logger = logging.getLogger(__name__)


def analyze(
    config: Config,
    llm: Llm,
    criteria: list[Reference],
    call_types: list[Reference],
    plain: str,
    manager_name: str | None,
) -> tuple[dict, dict[str, int]]:
    model = build_analysis_model(criteria, call_types, config.llm.output.list_items)
    prompt = config.prompt.user.format(
        **{
            PROMPT_CRITERIA_PLACEHOLDER: render_criteria(criteria),
            PROMPT_MANAGER_PLACEHOLDER: manager_name or UNKNOWN_MANAGER,
            PROMPT_TRANSCRIPT_PLACEHOLDER: plain,
        }
    )
    raw = llm.generate(config.prompt.system, prompt, model.model_json_schema())
    payload = model.model_validate(raw).model_dump()
    scores = payload.pop(SCORES_FIELD)
    logger.info("call classified as %s", payload[CALL_TYPE_FIELD])
    return payload, scores
