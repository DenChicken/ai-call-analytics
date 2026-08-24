from urllib.parse import urlencode

LIST_SEPARATOR = ","
EMPTY_LIST_VALUE = "-"
TRUE_VALUES = ("1", "true", "yes")
FALSE_VALUES = ("0", "false", "no")


def read(params, key: str, default: str = "") -> str:
    return str(params.get(key, default))


def read_choice(params, key: str, allowed, default: str) -> str:
    value = read(params, key)
    return value if value in allowed else default


def read_int(params, key: str, default: int) -> int:
    value = read(params, key)
    return int(value) if value.isdigit() else default


def read_flag(params, key: str, default: bool) -> bool:
    value = read(params, key).lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def read_list(params, key: str, allowed, default: list[str]) -> list[str]:
    value = read(params, key)
    if not value:
        return list(default)
    if value == EMPTY_LIST_VALUE:
        return []
    chosen = {item for item in value.split(LIST_SEPARATOR) if item in allowed}
    return [item for item in allowed if item in chosen]


def write_list(selected, allowed) -> str:
    codes = [str(entry) for entry in selected]
    if len(codes) == len(allowed):
        return ""
    if not codes:
        return EMPTY_LIST_VALUE
    return LIST_SEPARATOR.join(codes)


def read_page(params, key: str, default: int) -> int:
    return max(default, read_int(params, key, default))


def query(path: str, values: dict) -> str:
    present = {key: value for key, value in values.items() if value != ""}
    return f"{path}?{urlencode(present)}" if present else path
