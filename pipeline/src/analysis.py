import logging

from src.config import Config, Criterion
from src.constants import PROMPT_CRITERIA_PLACEHOLDER, PROMPT_TRANSCRIPT_PLACEHOLDER
from src.llm import Llm
from src.schema import build_analysis_model
from src.transcript import Segment, render_criteria, render_transcript, speaker_labels

SCORES_FIELD = "scores"

logger = logging.getLogger(__name__)


def analyze(
    config: Config,
    llm: Llm,
    criteria: list[Criterion],
    segments: list[Segment],
) -> tuple[dict, dict[str, int]]:
    speakers = speaker_labels(segments)
    model = build_analysis_model(criteria, speakers)
    user_prompt = config.prompt.user.format(
        **{
            PROMPT_CRITERIA_PLACEHOLDER: render_criteria(criteria),
            PROMPT_TRANSCRIPT_PLACEHOLDER: render_transcript(segments),
        }
    )

    raw = llm.generate(config.prompt.system, user_prompt, model.model_json_schema())
    analysis = model.model_validate(raw)
    payload = analysis.model_dump()
    scores = payload.pop(SCORES_FIELD)
    logger.info("manager identified as %s", payload["manager_speaker"])
    return payload, scores
