import reflex as rx

from src.components.common import section_card
from src.components.layout import page_layout
from src.constants import ROUTE_DASHBOARD, ROUTE_MANAGER
from src.state.call import CallState

TITLE = "Разговор"
BACK_LABEL = "К дашборду"
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

BACK_ICON_SIZE = 16
MARK_ICON_SIZE = 16
TRANSCRIPT_HEIGHT = "22rem"
AUDIO_HEIGHT = "3rem"
TIME_WIDTH = "3rem"
MET_COLOR = "grass"
UNMET_COLOR = "gray"


def _field(label: str, value: rx.Var | str) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color_scheme="gray"),
        rx.text(value, size="2", weight="medium"),
        spacing="1",
        align="start",
    )


def _header() -> rx.Component:
    return rx.vstack(
        rx.link(
            rx.hstack(
                rx.icon("arrow-left", size=BACK_ICON_SIZE),
                rx.text(BACK_LABEL, size="2"),
                spacing="2",
                align="center",
            ),
            href=ROUTE_DASHBOARD,
            underline="none",
            color_scheme="gray",
        ),
        rx.hstack(
            rx.heading(TITLE, size="7"),
            rx.badge(CallState.status_label, color_scheme=CallState.status_color),
            rx.spacer(),
            rx.cond(
                CallState.crm_link != "",
                rx.link(
                    rx.button(CRM_LABEL, variant="soft", size="2"),
                    href=CallState.crm_link,
                    is_external=True,
                ),
                rx.fragment(),
            ),
            width="100%",
            align="center",
            spacing="3",
        ),
        rx.cond(
            CallState.error != "",
            rx.callout(CallState.error, color_scheme="red", size="1", width="100%"),
            rx.fragment(),
        ),
        spacing="3",
        width="100%",
        align="start",
    )


def _summary_row() -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.link(
                _field(FIELD_MANAGER, CallState.agent_name),
                href=f"{ROUTE_MANAGER}/{CallState.manager_id}",
                underline="none",
                color="inherit",
            ),
            _field(FIELD_CLIENT, CallState.client),
            _field(FIELD_DATE, CallState.started_at),
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
            rx.badge("выключен", color_scheme="gray", size="1"),
        ),
        spacing="2",
        align="center",
        width="100%",
    )


def _segment_row(segment) -> rx.Component:
    return rx.hstack(
        rx.text(segment.time, size="1", color_scheme="gray", width=TIME_WIDTH, flex_shrink="0"),
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
            rx.text(NO_ANALYSIS, size="2", color_scheme="gray"),
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
        _header(),
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
                    rx.text(NO_ANALYSIS, size="2", color_scheme="gray"),
                ),
            ),
            rx.vstack(
                section_card(
                    AUDIO_TITLE,
                    rx.cond(
                        CallState.audio_url != "",
                        rx.audio(src=CallState.audio_url, width="100%", height=AUDIO_HEIGHT),
                        rx.text(NO_AUDIO, size="2", color_scheme="gray"),
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
                            ),
                            height=TRANSCRIPT_HEIGHT,
                            type="auto",
                        ),
                        rx.text(NO_TRANSCRIPT, size="2", color_scheme="gray"),
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
                rx.text(NO_ANALYSIS, size="2", color_scheme="gray"),
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
            rx.vstack(
                _header(),
                rx.text(NOT_FOUND, size="3", color_scheme="gray"),
                spacing="4",
                width="100%",
            ),
        ),
        on_mount=CallState.load,
    )
