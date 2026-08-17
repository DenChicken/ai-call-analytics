import logging

from src.config import Config, Criterion
from src.constants import (
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
    SCORES_FIELD,
    UNKNOWN_MANAGER,
)
from src.llm import Llm
from src.schema import build_analysis_model, build_roles_model, role_field_name
from src.transcript import (
    Segment,
    render_criteria,
    render_numbered_transcript,
    render_transcript,
    with_roles,
)

logger = logging.getLogger(__name__)


def attribute_roles(
    config: Config, llm: Llm, segments: list[Segment], manager_name: str | None
) -> list[Segment]:
    model = build_roles_model(len(segments))
    prompt = config.roles_prompt.user.format(
        **{
            PROMPT_MANAGER_PLACEHOLDER: manager_name or UNKNOWN_MANAGER,
            PROMPT_TRANSCRIPT_PLACEHOLDER: render_numbered_transcript(segments),
        }
    )
    raw = llm.generate(config.roles_prompt.system, prompt, model.model_json_schema())
    payload = model.model_validate(raw).model_dump()
    roles = [payload[role_field_name(index)] for index in range(len(segments))]
    logger.info("roles attributed: %s", ", ".join(roles))
    return with_roles(segments, roles)


def analyze(
    config: Config,
    llm: Llm,
    criteria: list[Criterion],
    segments: list[Segment],
) -> tuple[dict, dict[str, int]]:
    model = build_analysis_model(criteria)
    prompt = config.analysis_prompt.user.format(
        **{
            PROMPT_CRITERIA_PLACEHOLDER: render_criteria(criteria),
            PROMPT_TRANSCRIPT_PLACEHOLDER: render_transcript(segments),
        }
    )
    raw = llm.generate(config.analysis_prompt.system, prompt, model.model_json_schema())
    payload = model.model_validate(raw).model_dump()
    scores = payload.pop(SCORES_FIELD)
    return payload, scores
