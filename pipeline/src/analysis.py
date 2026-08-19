import logging

from src.config import Config, Reference
from src.constants import (
    CALL_TYPE_FIELD,
    CRITERIA_LINE_TEMPLATE,
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
    SCORES_FIELD,
    SUMMARY_FIELD,
    TEXT_LIST_FIELDS,
    UNKNOWN_MANAGER,
)
from src.llm import Llm
from src.schema import build_analysis_model

logger = logging.getLogger(__name__)


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
) -> tuple[dict, dict[str, int]]:
    logger.debug(
        "analyzing %s characters against %s criteria and %s call types, manager: %s",
        len(plain),
        len(criteria),
        len(call_types),
        manager_name or UNKNOWN_MANAGER,
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
    payload = model.model_validate(raw).model_dump()
    scores = payload.pop(SCORES_FIELD)
    met = sorted(code for code, score in scores.items() if score)
    logger.info(
        "call classified as %s, %s of %s criteria met: %s",
        payload[CALL_TYPE_FIELD],
        len(met),
        len(scores),
        ", ".join(met) or "none",
    )
    logger.debug("summary: %s", payload[SUMMARY_FIELD])
    for field in TEXT_LIST_FIELDS:
        logger.debug("%s: %s", field, payload[field])
    return payload, scores
