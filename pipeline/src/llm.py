import json
import logging
import time
from pathlib import Path

from llama_cpp import Llama

from src.config import Llm as LlmConfig
from src.constants import (
    CONTEXT_OVERFLOW_MARKER,
    ERROR_LLM_INVALID_OUTPUT,
    ERROR_LLM_PROMPT_TOO_LONG,
    ERROR_LLM_TRUNCATED,
    FINISH_REASON_LENGTH,
    JSON_RESPONSE_FORMAT,
    KV_CACHE_TYPES,
    ROLE_SYSTEM,
    ROLE_USER,
)
from src.errors import CallError, FatalError, is_device_failure

logger = logging.getLogger(__name__)


class Llm:
    def __init__(self, config: LlmConfig, model_path: Path):
        if not model_path.is_file():
            raise FatalError(f"llm not found: {model_path}, run scripts/fetch_models.py")
        self._config = config
        self._model_path = model_path
        self._model = None

    def _load(self) -> Llama:
        if self._model is None:
            config = self._config
            logger.info(
                "loading llm from %s, %s layers on gpu, context %s tokens",
                self._model_path.name,
                config.gpu_layers,
                config.context_tokens,
            )
            cache_type = KV_CACHE_TYPES[config.kv_cache_type]
            started = time.monotonic()
            try:
                self._model = Llama(
                    model_path=str(self._model_path),
                    n_gpu_layers=config.gpu_layers,
                    n_ctx=config.context_tokens,
                    n_batch=config.batch_tokens,
                    n_threads=config.threads,
                    flash_attn=config.flash_attention,
                    type_k=cache_type,
                    type_v=cache_type,
                    offload_kqv=config.offload_kv_cache,
                    verbose=False,
                )
            except Exception as error:
                raise FatalError(f"llm could not be loaded: {error}") from error
            logger.info("llm loaded in %.0fs", time.monotonic() - started)
            _log_applied(self._model, config, cache_type)
        return self._model

    def unload(self) -> None:
        if self._model is None:
            return
        logger.info("unloading llm")
        self._model.close()
        self._model = None

    def generate(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        model = self._load()
        messages = [
            {"role": ROLE_SYSTEM, "content": system_prompt},
            {"role": ROLE_USER, "content": user_prompt},
        ]

        prompt_tokens = sum(
            len(model.tokenize(message["content"].encode("utf-8"))) for message in messages
        )
        logger.info("generating from %s input tokens", prompt_tokens)
        sampling = self._config.sampling
        started = time.monotonic()
        try:
            completion = model.create_chat_completion(
                messages=messages,
                response_format={"type": JSON_RESPONSE_FORMAT, "schema": schema},
                max_tokens=self._config.output.max_tokens,
                temperature=sampling.temperature,
                top_p=sampling.top_p,
                top_k=sampling.top_k,
                min_p=sampling.min_p,
                repeat_penalty=sampling.repeat_penalty,
                seed=sampling.seed,
            )
        except Exception as error:
            if CONTEXT_OVERFLOW_MARKER in str(error):
                raise CallError(
                    ERROR_LLM_PROMPT_TOO_LONG,
                    f"{error}, raise 'context_tokens' in [llm] or shorten the prompt",
                ) from error
            if not is_device_failure(error):
                raise
            self.unload()
            raise FatalError(f"llm failed: {error}") from error

        elapsed = time.monotonic() - started
        choice = completion["choices"][0]
        produced = completion["usage"]["completion_tokens"]
        text = choice["message"]["content"]

        logger.info(
            "generated %s tokens in %.0fs (%.1f tokens/s)",
            produced,
            elapsed,
            produced / elapsed if elapsed else 0,
        )
        logger.trace("finished as %s, %s chars", choice["finish_reason"], len(text or ""))

        if self._config.unload_after:
            self.unload()

        if choice["finish_reason"] == FINISH_REASON_LENGTH:
            raise CallError(
                ERROR_LLM_TRUNCATED,
                f"generation was cut off after {produced} tokens, "
                "raise 'max_tokens' in [llm.output]",
            )

        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError) as error:
            logger.debug("model returned %s chars of invalid json", len(text or ""))
            raise CallError(
                ERROR_LLM_INVALID_OUTPUT, f"model returned invalid json: {error}"
            ) from error


def _log_applied(model: Llama, config: LlmConfig, cache_type: int) -> None:
    params = model.context_params
    logger.info(
        "llm ready: context %s tokens, batch %s, %s threads",
        model.n_ctx(),
        params.n_batch,
        params.n_threads,
    )
    if params.type_k != cache_type or params.type_v != cache_type:
        logger.warning(
            "kv_cache_type %s was not applied, the model uses another one",
            config.kv_cache_type,
        )
    logger.debug(
        "llm context params: type_k=%s type_v=%s flash_attn=%s offload_kqv=%s",
        params.type_k,
        params.type_v,
        params.flash_attn_type,
        params.offload_kqv,
    )
