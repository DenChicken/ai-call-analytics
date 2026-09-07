import gc
import json
import logging
import time
from pathlib import Path

import torch
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import (
    build_transformers_prefix_allowed_tokens_fn,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    MaxTimeCriteria,
    StoppingCriteriaList,
)

from src.config import Llm as LlmConfig
from src.constants import (
    ERROR_LLM_INVALID_OUTPUT,
    ERROR_LLM_PROMPT_TOO_LONG,
    ERROR_LLM_TRUNCATED,
)
from src.errors import CallError, FatalError, is_device_failure

ROLE_SYSTEM = "system"
ROLE_USER = "user"
TENSOR_FORMAT = "pt"
ENABLE_THINKING = False

logger = logging.getLogger(__name__)


class Llm:
    def __init__(self, config: LlmConfig, model_dir: Path):
        if not model_dir.is_dir():
            raise FatalError(f"llm not found: {model_dir}, run scripts/fetch_models.py")
        self._config = config
        self._model_dir = model_dir
        self._tokenizer = None
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        logger.info("loading llm from %s on %s", self._model_dir, self._config.device)
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(str(self._model_dir))
            self._model = AutoModelForCausalLM.from_pretrained(
                str(self._model_dir),
                dtype=getattr(torch, self._config.torch_dtype),
                attn_implementation=self._config.attn_implementation,
                quantization_config=_quantization(self._config),
                device_map=self._config.device,
            )
            self._model.eval()
        except Exception as error:
            self.unload()
            raise FatalError(f"llm could not be loaded on {self._config.device}: {error}") from error

    def unload(self) -> None:
        if self._model is None and self._tokenizer is None:
            return
        logger.info("unloading llm")
        self._model = None
        self._tokenizer = None
        gc.collect()
        if torch.accelerator.is_available():
            torch.accelerator.empty_cache()

    def generate(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        self._load()
        text = self._tokenizer.apply_chat_template(
            [
                {"role": ROLE_SYSTEM, "content": system_prompt},
                {"role": ROLE_USER, "content": user_prompt},
            ],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=ENABLE_THINKING,
        )
        inputs = self._tokenizer(text, return_tensors=TENSOR_FORMAT).to(self._model.device)
        prompt_tokens = inputs["input_ids"].shape[1]
        if prompt_tokens > self._config.max_input_tokens:
            raise CallError(
                ERROR_LLM_PROMPT_TOO_LONG,
                f"prompt is {prompt_tokens} tokens, over the max_input_tokens limit "
                f"of {self._config.max_input_tokens}, raise it in the config",
            )

        logger.info("generating from %s input tokens", prompt_tokens)
        output = self._config.output
        started = time.monotonic()
        try:
            with torch.inference_mode():
                generated = self._model.generate(
                    **inputs,
                    max_new_tokens=output.max_new_tokens,
                    prefix_allowed_tokens_fn=build_transformers_prefix_allowed_tokens_fn(
                        self._tokenizer, JsonSchemaParser(schema)
                    ),
                    stopping_criteria=StoppingCriteriaList(
                        [MaxTimeCriteria(output.timeout_seconds)]
                    ),
                    pad_token_id=self._tokenizer.eos_token_id,
                    **_sampling(self._config),
                )
        except Exception as error:
            if not is_device_failure(error):
                raise
            self.unload()
            raise FatalError(f"llm failed on {self._config.device}: {error}") from error

        produced = generated[0][prompt_tokens:]
        elapsed = time.monotonic() - started
        completion = self._tokenizer.decode(produced, skip_special_tokens=True)
        logger.info(
            "generated %s tokens in %.0fs (%.1f tokens/s)",
            len(produced),
            elapsed,
            len(produced) / elapsed if elapsed else 0,
        )

        if self._config.unload_after:
            self.unload()

        try:
            return json.loads(completion)
        except json.JSONDecodeError as error:
            cut_off = len(produced) >= output.max_new_tokens or elapsed >= output.timeout_seconds
            logger.debug("model returned %s chars of invalid json", len(completion))
            raise CallError(
                ERROR_LLM_TRUNCATED if cut_off else ERROR_LLM_INVALID_OUTPUT,
                f"generation was cut off after {len(produced)} tokens and {elapsed:.0f}s"
                if cut_off
                else f"model returned invalid json: {error}",
            ) from error


def _sampling(config: LlmConfig) -> dict:
    if config.temperature <= 0:
        return {"do_sample": False}
    return {
        "do_sample": True,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "top_k": config.top_k,
    }


def _quantization(config: LlmConfig) -> BitsAndBytesConfig | None:
    if not config.load_in_4bit:
        return None
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=getattr(torch, config.torch_dtype),
        bnb_4bit_quant_type=config.quant_type,
    )
