import logging

from src.config import Config, Criterion
from src.constants import (
    CALL_TYPE_FIELD,
    CALL_TYPE_SALES,
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
    SCORES_FIELD,
    UNKNOWN_MANAGER,
)
from src.llm import Llm
from src.schema import Dialog, build_analysis_model
from src.transcript import (
    Segment,
    Turn,
    build_turns,
    render_criteria,
    render_dialog,
    render_segments,
)

logger = logging.getLogger(__name__)


def attribute_roles(
    config: Config, llm: Llm, segments: list[Segment], manager_name: str | None
) -> list[Turn]:
    prompt = config.roles_prompt.user.format(
        **{
            PROMPT_MANAGER_PLACEHOLDER: manager_name or UNKNOWN_MANAGER,
            PROMPT_TRANSCRIPT_PLACEHOLDER: render_segments(segments),
        }
    )
    raw = llm.generate(config.roles_prompt.system, prompt, Dialog.model_json_schema())
    turns = build_turns(Dialog.model_validate(raw).dialog, segments[-1].end_ms)
    logger.info("%s segments split into %s turns", len(segments), len(turns))
    return turns


def analyze(
    config: Config,
    llm: Llm,
    criteria: list[Criterion],
    turns: list[Turn],
) -> tuple[dict, dict[str, int]]:
    model = build_analysis_model(criteria)
    prompt = config.analysis_prompt.user.format(
        **{
            PROMPT_CRITERIA_PLACEHOLDER: render_criteria(criteria),
            PROMPT_TRANSCRIPT_PLACEHOLDER: render_dialog(turns),
        }
    )
    raw = llm.generate(config.analysis_prompt.system, prompt, model.model_json_schema())
    payload = model.model_validate(raw).model_dump()
    scores = payload.pop(SCORES_FIELD)
    call_type = payload[CALL_TYPE_FIELD]
    if call_type != CALL_TYPE_SALES:
        logger.info("call classified as %s, scores dropped", call_type)
        scores = {}
    return payload, scores
