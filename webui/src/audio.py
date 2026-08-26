import logging
from pathlib import Path

import reflex as rx
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var, VarData

from src.config import StorageConfig
from src.constants import AUDIO_ROUTE

BACKEND_URL_HELPER = "getBackendURL"
BACKEND_URL_MODULE = "$/utils/state"
BACKEND_ENV_MODULE = "$/env.json"
BACKEND_ENV_TAG = "env"
BACKEND_ORIGIN_EXPRESSION = f"{BACKEND_URL_HELPER}({BACKEND_ENV_TAG}.PING).origin"

logger = logging.getLogger(__name__)


def call_audio_url(call_id: rx.Var) -> Var:
    route = rx.config.get_config().prepend_backend_path(AUDIO_ROUTE)
    return Var(
        _js_expr=f"{BACKEND_ORIGIN_EXPRESSION} + `{route}/${{{call_id}}}`",
        _var_type=str,
        _var_data=VarData(
            imports={
                BACKEND_URL_MODULE: (ImportVar(tag=BACKEND_URL_HELPER, install=False),),
                BACKEND_ENV_MODULE: (
                    ImportVar(tag=BACKEND_ENV_TAG, is_default=True, install=False),
                ),
            }
        ),
    ).to(str)


class AudioStore:
    def __init__(self, config: StorageConfig):
        self._data_dir = config.data_dir

    def locate(self, audio_path: str | None) -> Path | None:
        if not audio_path:
            return None

        path = self._data_dir / audio_path
        if path.is_file():
            return path

        logger.debug("audio file not found: %s", path)
        return None
