from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, create_model

from src.config import Criterion
from src.constants import SCORE_MAX, SCORE_MIN, SPEAKER_AGENT, SPEAKER_CLIENT

SCORES_MODEL_NAME = "CriteriaScores"
ANALYSIS_MODEL_NAME = "CallAnalysis"


@dataclass(frozen=True)
class TranscriptSegment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class AnalysisResult:
    agent_speaker: str
    scores: dict[str, int]
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    recommendations: str


def build_analysis_model(
    criteria: tuple[Criterion, ...], speakers: tuple[str, ...]
) -> type[BaseModel]:
    scores_fields = {
        criterion.code: (
            int,
            Field(..., ge=SCORE_MIN, le=SCORE_MAX, description=criterion.prompt),
        )
        for criterion in criteria
    }
    scores_model = create_model(SCORES_MODEL_NAME, **scores_fields)

    return create_model(
        ANALYSIS_MODEL_NAME,
        agent_speaker=(
            Literal[speakers],
            Field(..., description="Идентификатор говорящего, который является менеджером"),
        ),
        scores=(scores_model, Field(..., description="Оценки по критериям")),
        summary=(str, Field(..., description="Краткое содержание разговора")),
        manager_strengths=(list[str], Field(..., description="Сильные стороны менеджера")),
        manager_weaknesses=(list[str], Field(..., description="Слабые стороны и точки роста")),
        recommendations=(str, Field(..., description="Рекомендации менеджеру по улучшению")),
    )


def to_result(payload: BaseModel) -> AnalysisResult:
    return AnalysisResult(
        agent_speaker=payload.agent_speaker,
        scores=payload.scores.model_dump(),
        summary=payload.summary,
        strengths=payload.manager_strengths,
        weaknesses=payload.manager_weaknesses,
        recommendations=payload.recommendations,
    )


def speaker_labels(segments: list[TranscriptSegment]) -> tuple[str, ...]:
    labels = []
    for segment in segments:
        if segment.speaker not in labels:
            labels.append(segment.speaker)
    return tuple(labels)


def assign_roles(
    segments: list[TranscriptSegment], agent_speaker: str
) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            speaker=SPEAKER_AGENT if segment.speaker == agent_speaker else SPEAKER_CLIENT,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
        )
        for segment in segments
    ]
