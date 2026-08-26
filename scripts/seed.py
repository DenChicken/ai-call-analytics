import argparse
import json
import random
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SOURCE_NAME = "synthetic"
DEFAULT_DAYS = 30
DEFAULT_CALLS = 320
DEFAULT_SEED = 20260821

DONE_DIR_TEMPLATE = "done/%Y-%m/%d"
PENDING_DIR = "pending"
AUDIO_SUFFIX = ".mp3"

WORK_START_HOUR = 9
WORK_END_HOUR = 20
MIN_DURATION = 25
MAX_DURATION = 900
SEGMENT_MIN_MS = 900
SEGMENT_MAX_MS = 6000
SEGMENT_GAP_MS = 250
MILLISECONDS_PER_SECOND = 1000

STATUS_PENDING = "pending"
STATUS_TRANSCRIBING = "transcribing"
STATUS_TRANSCRIBED = "transcribed"
STATUS_ANALYZING = "analyzing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

ERROR_CODES = (
    "audio_missing",
    "asr_empty",
    "transcript_empty",
    "llm_truncated",
    "llm_prompt_too_long",
    "llm_invalid_output",
    "out_of_memory",
    "database",
    "stale_claim",
    "unknown",
)

STATUS_WEIGHTS = {
    STATUS_DONE: 74,
    STATUS_PENDING: 9,
    STATUS_FAILED: 8,
    STATUS_TRANSCRIBED: 4,
    STATUS_TRANSCRIBING: 3,
    STATUS_ANALYZING: 2,
}

STORED_STATUSES = (STATUS_TRANSCRIBED, STATUS_ANALYZING, STATUS_DONE, STATUS_FAILED)

FIRST_SEGMENT_MIN_MS = 200
FIRST_SEGMENT_MAX_MS = 1500
SKILL_RANGE = (0.15, 0.8)
LIST_ITEMS_RANGE = (1, 3)
ATTEMPTS_RANGE = (1, 3)
PROCESSING_RANGE = (40, 400)
ANALYSIS_DELAY_RANGE = (1, 30)
QUEUE_DELAY_HOURS = 1
MINUTE_MAX = 59
SECOND_MAX = 59
PHONE_MIN = 100000000
PHONE_MAX = 999999999
DEAL_MIN = 1000
DEAL_MAX = 9999

AGENTS = (
    ("10637", "Ефименко Александр Николаевич", "a.efimenko"),
    ("11885", "Голышев Александр Денисович", "a.golyshev"),
    ("17126", "Ханин Андрей Дмитриевич", "a.hanin"),
    ("5662", "Юдин Андрей Леонидович", "a.yudin"),
    ("9165", "Кириллов Виктор Юрьевич", "v.kirillov"),
    ("6643", "Боже Сергей Янович", "s.bozhe"),
    ("11369", "Чистяков Дмитрий Андреевич", "d.chistyakov"),
    ("14002", "Северова Анастасия Игоревна", "a.severova"),
    ("15530", "Мамедов Тимур Русланович", "t.mamedov"),
    ("16110", "Войтенко Ольга Сергеевна", "o.voytenko"),
)

CALL_TYPES = (
    ("sales", "Продажа", "Разговор с клиентом об условиях покупки."),
    ("not_sales", "Не продажа", "Автоответчик, тишина или разговор коллег."),
    ("support", "Поддержка", "Клиент обращается по действующему заказу."),
    ("callback", "Перезвон", "Короткий возврат к прошлому разговору."),
    ("spam", "Спам", "Нецелевой входящий звонок."),
)

CRITERIA = (
    ("contact_initiation", "Контакт и начало разговора", "Менеджер поздоровался и представился."),
    ("client_qualification", "Квалификация клиента", "Менеджер уточнил город, бюджет или сферу."),
    ("request_understanding", "Понимание запроса", "Менеджер уточнил характеристики товара."),
    ("client_pain", "Понимание боли клиента", "Менеджер спросил о целях и срочности."),
    ("quality_presentation", "Качественная презентация", "Менеджер описал выгоды и условия."),
    ("objection_handling", "Отработка возражений", "Менеджер ответил на сомнения клиента."),
    ("purchase_offer", "Предложение о покупке", "Менеджер предложил оформить заказ."),
    ("call_closing", "Закрытие звонка", "Менеджер зафиксировал следующий шаг."),
    ("cross_selling", "Кросс-продажа", "Менеджер предложил сопутствующие товары."),
    ("hover_offer", "Предложение Ховера", "Менеджер предложил бренд Ховер."),
    ("conversation_management", "Управление разговором", "Менеджер держал инициативу."),
    ("meeting_invitation", "Приглашение на встречу", "Менеджер позвал в офис или шоурум."),
    ("price_justification", "Обоснование цены", "Менеджер объяснил, из чего складывается цена."),
    ("delivery_terms", "Условия доставки", "Менеджер проговорил сроки и стоимость доставки."),
    ("competitor_handling", "Работа с конкурентами", "Менеджер отстроился от конкурентов."),
    ("script_following", "Следование скрипту", "Менеджер придерживался структуры разговора."),
)

DISABLED_CRITERIA = ("hover_offer", "script_following")
LATE_CRITERIA = {"price_justification": 12, "delivery_terms": 8, "competitor_handling": 4}

PHRASES = (
    "Алло, добрый день.",
    "Меня зовут {name}, компания Винил Раша.",
    "Подскажите, вам плёнку для авто или для интерьера?",
    "У нас сейчас есть в наличии глянец и мат.",
    "Смотрите, по цене выходит от тридцати пяти тысяч за рулон.",
    "Это дороговато, если честно.",
    "Понимаю, но здесь гарантия три года и монтаж входит.",
    "А сколько по срокам доставки получится?",
    "До Москвы три дня, до регионов до недели.",
    "Мне надо подумать, посоветоваться.",
    "Конечно, давайте я скину коммерческое на почту.",
    "Да, скиньте, посмотрю вечером.",
    "Хорошо, тогда наберу вас в четверг после обеда.",
    "Договорились, спасибо.",
    "Всего доброго, до связи.",
    "Скажите, а вы раньше с плёнкой работали?",
    "Да, брали у других, но качество не понравилось.",
    "У нас как раз с этим строго, каждая партия проверяется.",
    "Можем отправить образец, чтобы вы посмотрели.",
    "Это было бы отлично.",
)

SUMMARIES = (
    "Менеджер {name} представился и выяснил потребность клиента. Обсудили наличие и цену, "
    "клиент взял паузу на решение. Договорились о повторном звонке.",
    "Менеджер {name} провёл разговор о поставке плёнки. Клиент возразил по цене, "
    "менеджер обосновал стоимость гарантией. Итог не зафиксирован.",
    "Менеджер {name} принял входящий звонок по действующему заказу. Уточнили сроки доставки "
    "и передали вопрос в логистику.",
    "Короткий разговор без продвижения по сделке. Клиент попросил перезвонить позже.",
)

STRENGTHS = (
    "Установил контакт и назвал компанию",
    "Уточнил потребность клиента",
    "Отработал возражение по цене",
    "Проговорил условия доставки",
    "Зафиксировал следующий шаг",
    "Держал инициативу в разговоре",
)

WEAKNESSES = (
    "Не выяснил бюджет клиента",
    "Не предложил сопутствующие товары",
    "Перешёл к цене раньше времени",
    "Не пригласил в шоурум",
    "Оставил разговор без договорённости",
    "Не уточнил сроки принятия решения",
)

RECOMMENDATIONS = (
    "Уточнять бюджет до презентации",
    "Предлагать образец при сомнениях",
    "Фиксировать дату следующего контакта",
    "Проговаривать состав цены заранее",
    "Задавать открытые вопросы о задаче",
)

ASR_MODEL = "Systran/faster-whisper-large-v3"
ANALYSIS_MODELS = ("Qwen/Qwen3-1.7B", "Qwen/Qwen3-4B-Instruct-2507")
PROMPT_LABELS = ("v2", "v3")
LANGUAGE = "ru"
PORTAL_URL = "https://b24.vinylrussia.ru"
EMAIL_DOMAIN = "vinylrussia.ru"
DIRECTIONS = ("outbound", "inbound", "callback")
SUBJECTS = ("Исходящий звонок", "Входящий звонок", "Перезвон по заявке", None)


CONFIRM_WARNING = (
    "about to delete every call, transcript and analysis, then fill the database "
    "with synthetic data\nusers, sessions, criteria and call types are kept"
)
CONFIRM_PROMPT = "type 'yes' to continue: "
CONFIRM_ANSWER = "yes"


class SeedError(Exception):
    pass


def read_dsn(path: Path) -> str:
    if not path.is_file():
        raise SeedError(f"dsn file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        dsn = handle.readline().strip()
    if not dsn:
        raise SeedError(f"dsn file is empty: {path}")
    return dsn


def pick_status(chance: random.Random) -> str:
    return chance.choices(
        list(STATUS_WEIGHTS), weights=list(STATUS_WEIGHTS.values())
    )[0]


def build_segments(chance: random.Random, duration_seconds: int, name: str) -> list[dict]:
    segments = []
    position = chance.randint(FIRST_SEGMENT_MIN_MS, FIRST_SEGMENT_MAX_MS)
    limit = duration_seconds * MILLISECONDS_PER_SECOND
    while position < limit:
        length = chance.randint(SEGMENT_MIN_MS, SEGMENT_MAX_MS)
        end = min(position + length, limit)
        segments.append(
            {
                "start_ms": position,
                "end_ms": end,
                "text": chance.choice(PHRASES).format(name=name.split()[1]),
            }
        )
        position = end + chance.randint(0, SEGMENT_GAP_MS)
    return segments


def active_criteria(day_offset: int) -> list[tuple]:
    active = []
    for code, label, description in CRITERIA:
        if code in DISABLED_CRITERIA:
            continue
        introduced = LATE_CRITERIA.get(code)
        if introduced is not None and day_offset > introduced:
            continue
        active.append((code, label, description))
    return active


def seed(connection, root: Path, audio_files: list[Path], days: int, calls: int, seed_value: int):
    chance = random.Random(seed_value)
    now = datetime.now(timezone.utc)

    with connection.cursor() as cursor:
        cursor.execute(
            "TRUNCATE calls, processing_jobs, analyses, asr_results, criterion_scores "
            "RESTART IDENTITY CASCADE"
        )
        cursor.execute(
            "INSERT INTO sources (name) VALUES (%s) "
            "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            (SOURCE_NAME,),
        )
        source_id = cursor.fetchone()["id"]

        agents = []
        for external_id, display_name, mailbox in AGENTS:
            last, first = display_name.split()[0], display_name.split()[1]
            cursor.execute(
                """
                INSERT INTO agents (source_id, external_id, display_name, first_name,
                                    last_name, email, profile_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id, external_id) DO UPDATE
                SET display_name = EXCLUDED.display_name RETURNING id
                """,
                (
                    source_id,
                    external_id,
                    display_name,
                    first,
                    last,
                    f"{mailbox}@{EMAIL_DOMAIN}",
                    f"{PORTAL_URL}/company/personal/user/{external_id}/",
                ),
            )
            agents.append((cursor.fetchone()["id"], display_name))

        for position, (code, label, description) in enumerate(CALL_TYPES):
            cursor.execute(
                """
                INSERT INTO call_types (code, label, description, position, enabled)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label
                """,
                (code, label, description, position),
            )

        for position, (code, label, description) in enumerate(CRITERIA):
            cursor.execute(
                """
                INSERT INTO criteria (code, label, description, position, enabled)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label
                """,
                (code, label, description, position, code not in DISABLED_CRITERIA),
            )

        type_codes = [code for code, _, _ in CALL_TYPES]
        stored = 0
        for number in range(calls):
            day_offset = chance.randint(0, days - 1)
            started = (now - timedelta(days=day_offset)).replace(
                hour=chance.randint(WORK_START_HOUR, WORK_END_HOUR),
                minute=chance.randint(0, MINUTE_MAX),
                second=chance.randint(0, SECOND_MAX),
                microsecond=0,
            )
            duration = chance.randint(MIN_DURATION, MAX_DURATION)
            agent_id, display_name = chance.choice(agents)
            status = pick_status(chance)
            call_id = number + 1

            source_audio = audio_files[number % len(audio_files)]
            if status == STATUS_DONE:
                target_dir = root / started.strftime(DONE_DIR_TEMPLATE)
            else:
                target_dir = root / PENDING_DIR
            target_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"{call_id}_{started:%Y%m%d%H%M%S}{AUDIO_SUFFIX}"
            target = target_dir / file_name
            if not target.exists():
                shutil.copyfile(source_audio, target)
            audio_path = target.relative_to(root).as_posix()

            cursor.execute(
                """
                INSERT INTO calls (id, source_id, external_id, agent_id, started_at,
                                   duration_seconds, direction, client_number, subject,
                                   crm_link, audio_path, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    call_id,
                    source_id,
                    f"synthetic.{call_id}",
                    agent_id,
                    started,
                    duration,
                    chance.choice(DIRECTIONS),
                    f"+79{chance.randint(PHONE_MIN, PHONE_MAX)}",
                    chance.choice(SUBJECTS),
                    f"{PORTAL_URL}/crm/deal/details/{chance.randint(DEAL_MIN, DEAL_MAX)}/",
                    audio_path,
                    json.dumps({"CALL_ID": f"synthetic.{call_id}"}, ensure_ascii=False),
                ),
            )

            error_code = chance.choice(ERROR_CODES) if status == STATUS_FAILED else None
            last_error = f"synthetic failure: {error_code}" if error_code else None
            attempts = (
                chance.randint(*ATTEMPTS_RANGE) if status == STATUS_FAILED else 0
            )
            cursor.execute(
                """
                INSERT INTO processing_jobs (call_id, status, attempts, error_code,
                                             last_error, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (call_id, status, attempts, error_code, last_error, started + timedelta(hours=QUEUE_DELAY_HOURS)),
            )

            if status in STORED_STATUSES:
                segments = build_segments(chance, duration, display_name)
                if segments:
                    plain = " ".join(segment["text"] for segment in segments)
                    cursor.execute(
                        """
                        INSERT INTO asr_results (call_id, model, language, duration_ms, plain, raw)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            call_id,
                            ASR_MODEL,
                            LANGUAGE,
                            duration * MILLISECONDS_PER_SECOND,
                            plain,
                            json.dumps({"segments": segments}, ensure_ascii=False),
                        ),
                    )

            if status != STATUS_DONE:
                continue

            analyzed_at = started + timedelta(
                hours=chance.randint(*ANALYSIS_DELAY_RANGE)
            )
            cursor.execute(
                """
                INSERT INTO analyses (call_id, call_type, summary, strengths, weaknesses,
                                      recommendations, asr_model, analysis_model, prompt_label,
                                      processing_seconds, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    call_id,
                    chance.choice(type_codes),
                    chance.choice(SUMMARIES).format(name=display_name),
                    json.dumps(chance.sample(STRENGTHS, chance.randint(*LIST_ITEMS_RANGE)), ensure_ascii=False),
                    json.dumps(chance.sample(WEAKNESSES, chance.randint(*LIST_ITEMS_RANGE)), ensure_ascii=False),
                    json.dumps(
                        chance.sample(RECOMMENDATIONS, chance.randint(*LIST_ITEMS_RANGE)),
                        ensure_ascii=False,
                    ),
                    ASR_MODEL,
                    chance.choice(ANALYSIS_MODELS),
                    chance.choice(PROMPT_LABELS),
                    chance.randint(*PROCESSING_RANGE),
                    analyzed_at,
                ),
            )

            skill = chance.uniform(*SKILL_RANGE)
            for code, _, _ in active_criteria(day_offset):
                cursor.execute(
                    "INSERT INTO criterion_scores (call_id, criterion_code, score) "
                    "VALUES (%s, %s, %s)",
                    (call_id, code, 1 if chance.random() < skill else 0),
                )
            stored += 1

        cursor.execute("SELECT setval(pg_get_serial_sequence('calls', 'id'), %s)", (calls,))

    connection.commit()
    return stored


def _confirm() -> bool:
    print(CONFIRM_WARNING)
    try:
        return input(CONFIRM_PROMPT).strip().lower() == CONFIRM_ANSWER
    except (EOFError, KeyboardInterrupt):
        print("aborted", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill the database with synthetic call data")
    parser.add_argument("-d", "--dsn-file", required=True, type=Path, help="path to the dsn file")
    parser.add_argument("-r", "--data-dir", required=True, type=Path, help="data directory")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="how far back to spread")
    parser.add_argument("--calls", type=int, default=DEFAULT_CALLS, help="how many calls")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed")
    parser.add_argument(
        "--yes", action="store_true", help="skip the confirmation prompt"
    )
    args = parser.parse_args()

    if not args.yes and not _confirm():
        return 1

    try:
        root = args.data_dir.resolve()
        sources = sorted((root / PENDING_DIR).glob(f"*{AUDIO_SUFFIX}"))
        if not sources:
            raise SeedError(f"no audio files in {root / PENDING_DIR}")

        with psycopg.connect(read_dsn(args.dsn_file), row_factory=dict_row) as connection:
            analyzed = seed(connection, root, sources, args.days, args.calls, args.seed)
    except SeedError as error:
        print(error, file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(f"seeding failed: {error}", file=sys.stderr)
        return 1

    print(f"seeded {args.calls} calls over {args.days} days, {analyzed} of them analysed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
