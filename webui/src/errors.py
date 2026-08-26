from src.constants import (
    ERROR_ASR_EMPTY,
    ERROR_AUDIO_MISSING,
    ERROR_DATABASE,
    ERROR_LLM_INVALID_OUTPUT,
    ERROR_LLM_PROMPT_TOO_LONG,
    ERROR_LLM_TRUNCATED,
    ERROR_NO_CALL_TYPES,
    ERROR_NO_CRITERIA,
    ERROR_OUT_OF_MEMORY,
    ERROR_STALE_CLAIM,
    ERROR_TRANSCRIPT_EMPTY,
    ERROR_UNKNOWN,
)

ERROR_LABELS = {
    ERROR_AUDIO_MISSING: "Файл записи не найден",
    ERROR_ASR_EMPTY: "Расшифровка не дала результата",
    ERROR_TRANSCRIPT_EMPTY: "Расшифровка пуста",
    ERROR_LLM_TRUNCATED: "Модель не уложилась в лимит ответа",
    ERROR_LLM_PROMPT_TOO_LONG: "Разговор не помещается в контекст модели",
    ERROR_LLM_INVALID_OUTPUT: "Модель вернула некорректный ответ",
    ERROR_NO_CRITERIA: "Не заданы активные критерии",
    ERROR_NO_CALL_TYPES: "Не заданы активные типы звонков",
    ERROR_OUT_OF_MEMORY: "Не хватило памяти",
    ERROR_DATABASE: "Ошибка базы данных",
    ERROR_STALE_CLAIM: "Обработка прервалась и не возобновилась",
    ERROR_UNKNOWN: "Не удалось обработать",
}


def describe(code: str | None) -> str:
    if not code:
        return ""
    return ERROR_LABELS.get(code, ERROR_LABELS[ERROR_UNKNOWN])
