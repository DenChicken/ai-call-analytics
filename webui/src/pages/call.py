import reflex as rx

from src.audio import call_audio_url
from src.components.common import (
    breadcrumbs,
    empty_state,
    not_found,
    section_card,
    status_badge,
    truncated,
)
from src.components.layout import page_layout, sticky_header
from src.constants import (
    AUDIO_ELEMENT_ID,
    CRM_ICON_SIZE,
    ROUTE_CALLS,
    ROUTE_MANAGER,
    SECTION_CALLS,
)
from src.state.call import CallState

TITLE = "Разговор"
NOT_FOUND = "Звонок не найден"
SCORES_TITLE = "Оценки по критериям"
TRANSCRIPT_TITLE = "Стенограмма"
AUDIO_TITLE = "Запись"
SUMMARY_TITLE = "Итог разговора"
STRENGTHS_TITLE = "Сильные стороны"
WEAKNESSES_TITLE = "Слабые стороны"
RECOMMENDATIONS_TITLE = "Рекомендации"
METADATA_TITLE = "Метаданные анализа"
CRM_LABEL = "Открыть в CRM"
NO_AUDIO = "Запись недоступна"
NO_TRANSCRIPT = "Расшифровка ещё не готова"
NO_ANALYSIS = "Анализ ещё не выполнен"
DISABLED_LABEL = "отключён"

FIELD_MANAGER = "Менеджер"
FIELD_CLIENT = "Клиент"
FIELD_DATE = "Дата"
FIELD_DURATION = "Длительность"
FIELD_TYPE = "Тип"
FIELD_SCORE = "Балл"

META_ASR = "Модель ASR"
META_ANALYSIS = "Модель анализа"
META_PROMPT = "Версия промпта"
META_PROCESSING = "Время обработки"
META_ANALYZED = "Проанализирован"

MARK_ICON_SIZE = 16
NAME_MAX_WIDTH = "12rem"
TRANSCRIPT_HEIGHT = "22rem"
TRANSCRIPT_SCROLLBAR_GUTTER = "0.75rem"
TIME_WIDTH = "3rem"
MET_COLOR = "grass"
UNMET_COLOR = "gray"


def _field(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color_scheme="gray"),
        value if isinstance(value, rx.Component) else rx.text(value, size="2", weight="medium"),
        spacing="1",
        align="start",
    )


def _header() -> rx.Component:
    return sticky_header(
        breadcrumbs((SECTION_CALLS, ROUTE_CALLS), TITLE),
        status_badge(CallState.status_label, CallState.status_color, CallState.error),
        rx.spacer(),
        rx.cond(
            CallState.crm_link != "",
            rx.link(
                rx.hstack(
                    rx.icon("external-link", size=CRM_ICON_SIZE),
                    rx.text(CRM_LABEL, size="1"),
                    spacing="1",
                    align="center",
                ),
                href=CallState.crm_link,
                is_external=True,
                underline="none",
                color_scheme="gray",
            ),
            rx.fragment(),
        ),
    )


def _summary_row() -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.cond(
                CallState.manager_id > 0,
                rx.link(
                    _field(
                        FIELD_MANAGER,
                        truncated(
                            CallState.agent_name,
                            size="2",
                            weight="medium",
                            max_width=NAME_MAX_WIDTH,
                        ),
                    ),
                    href=f"{ROUTE_MANAGER}/{CallState.manager_id}",
                    underline="none",
                    color="inherit",
                ),
                _field(FIELD_MANAGER, CallState.agent_name),
            ),
            _field(FIELD_CLIENT, CallState.client),
            rx.vstack(
                rx.text(FIELD_DATE, size="1", color_scheme="gray"),
                rx.text(CallState.started_at, size="2", weight="medium"),
                spacing="1",
                align="start",
            ),
            _field(FIELD_DURATION, CallState.duration),
            _field(FIELD_TYPE, CallState.call_type),
            _field(FIELD_SCORE, CallState.score_label),
            spacing="6",
            wrap="wrap",
        ),
        width="100%",
    )


def _score_row(row) -> rx.Component:
    return rx.hstack(
        rx.icon(
            rx.cond(row.met, "circle-check", "circle"),
            size=MARK_ICON_SIZE,
            color=rx.cond(row.met, f"var(--{MET_COLOR}-9)", f"var(--{UNMET_COLOR}-8)"),
        ),
        rx.text(row.label, size="2"),
        rx.cond(
            row.enabled,
            rx.fragment(),
            rx.badge(DISABLED_LABEL, color_scheme="gray", size="1"),
        ),
        spacing="2",
        align="center",
        width="100%",
    )


def _segment_row(segment) -> rx.Component:
    return rx.hstack(
        rx.button(
            segment.time,
            on_click=CallState.seek(segment.seconds),
            variant="ghost",
            size="1",
            color_scheme="gray",
            width=TIME_WIDTH,
            flex_shrink="0",
        ),
        rx.text(segment.text, size="2"),
        spacing="3",
        align="start",
        width="100%",
    )


def _text_list(title: str, items) -> rx.Component:
    return section_card(
        title,
        rx.cond(
            items.length() > 0,
            rx.vstack(
                rx.foreach(
                    items,
                    lambda item: rx.hstack(
                        rx.text("•", size="2", color_scheme="gray"),
                        rx.text(item, size="2"),
                        spacing="2",
                        align="start",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            empty_state(NO_ANALYSIS),
        ),
    )


def _metadata() -> rx.Component:
    return section_card(
        METADATA_TITLE,
        rx.hstack(
            _field(META_ASR, CallState.asr_model),
            _field(META_ANALYSIS, CallState.analysis_model),
            _field(META_PROMPT, CallState.prompt_label),
            _field(META_PROCESSING, CallState.processing_seconds),
            _field(META_ANALYZED, CallState.analyzed_at),
            spacing="6",
            wrap="wrap",
        ),
    )


def _found_view() -> rx.Component:
    return rx.vstack(
        _summary_row(),
        rx.hstack(
            section_card(
                SCORES_TITLE,
                rx.cond(
                    CallState.scores.length() > 0,
                    rx.vstack(
                        rx.foreach(CallState.scores, _score_row),
                        spacing="2",
                        width="100%",
                    ),
                    empty_state(NO_ANALYSIS),
                ),
            ),
            rx.vstack(
                section_card(
                    AUDIO_TITLE,
                    rx.cond(
                        CallState.has_audio,
                        rx.el.audio(
                            src=call_audio_url(CallState.current_call_id),
                            id=AUDIO_ELEMENT_ID,
                            controls=True,
                            preload="metadata",
                            width="100%",
                        ),
                        empty_state(NO_AUDIO),
                    ),
                ),
                section_card(
                    TRANSCRIPT_TITLE,
                    rx.cond(
                        CallState.segments.length() > 0,
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(CallState.segments, _segment_row),
                                spacing="2",
                                width="100%",
                                padding_right=TRANSCRIPT_SCROLLBAR_GUTTER,
                            ),
                            height=TRANSCRIPT_HEIGHT,
                            type="auto",
                            scrollbars="vertical",
                        ),
                        empty_state(NO_TRANSCRIPT),
                    ),
                ),
                spacing="3",
                width="100%",
            ),
            spacing="3",
            width="100%",
            align="start",
        ),
        section_card(
            SUMMARY_TITLE,
            rx.cond(
                CallState.summary != "",
                rx.text(CallState.summary, size="2"),
                empty_state(NO_ANALYSIS),
            ),
        ),
        rx.hstack(
            _text_list(STRENGTHS_TITLE, CallState.strengths),
            _text_list(WEAKNESSES_TITLE, CallState.weaknesses),
            _text_list(RECOMMENDATIONS_TITLE, CallState.recommendations),
            spacing="3",
            width="100%",
            align="start",
        ),
        _metadata(),
        spacing="4",
        width="100%",
    )


def call_page() -> rx.Component:
    return page_layout(
        rx.cond(
            CallState.found,
            _found_view(),
            not_found(NOT_FOUND, (SECTION_CALLS, ROUTE_CALLS)),
        ),
        header=_header(),
        on_mount=CallState.load,
    )
