import gc
import json
import logging
import threading
import time

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

from src.config import LlmConfig
from src.constants import (
    ERROR_LLM_INVALID_OUTPUT,
    ERROR_LLM_PROMPT_TOO_LONG,
    ERROR_LLM_TRUNCATED,
)
from src.errors import StageError
from src.schema import parser_config

ROLE_SYSTEM = "system"
ROLE_USER = "user"
QUANTIZATION_DTYPE = "bfloat16"
QUANTIZATION_TYPE = "nf4"
TENSOR_FORMAT = "pt"
CUDA_DEVICE = "cuda"

logger = logging.getLogger(__name__)


class Llm:
    def __init__(self, config: LlmConfig):
        if not config.local_dir.is_dir():
            raise FileNotFoundError(
                f"llm directory not found: {config.local_dir}, run scripts/fetch_models.py"
            )
        self._config = config
        self._tokenizer = None
        self._model = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._config.repo_id

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        logger.info("loading llm from %s on %s", self._config.local_dir, self._config.device)
        self._tokenizer = AutoTokenizer.from_pretrained(str(self._config.local_dir))
        self._model = AutoModelForCausalLM.from_pretrained(
            str(self._config.local_dir),
            dtype=getattr(torch, self._config.torch_dtype),
            quantization_config=_quantization_config(self._config),
            device_map=self._config.device,
        )
        self._model.eval()

    def unload(self) -> None:
        with self._lock:
            if self._model is None:
                return
            logger.info("unloading llm %s", self._config.repo_id)
            self._model = None
            self._tokenizer = None
            gc.collect()
            if self._config.device.startswith(CUDA_DEVICE):
                torch.cuda.empty_cache()

    def generate(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        with self._lock:
            self._ensure_loaded()
            messages = [
                {"role": ROLE_SYSTEM, "content": system_prompt},
                {"role": ROLE_USER, "content": user_prompt},
            ]
            text = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self._tokenizer(
                text,
                return_tensors=TENSOR_FORMAT,
                truncation=True,
                max_length=self._config.max_input_tokens,
            ).to(self._model.device)
            prompt_tokens = inputs["input_ids"].shape[1]
            if prompt_tokens >= self._config.max_input_tokens:
                raise StageError(
                    ERROR_LLM_PROMPT_TOO_LONG,
                    f"prompt hit the max_input_tokens limit of {self._config.max_input_tokens} "
                    "and was truncated, raise it in the config",
                )
            logger.info("generating from %s input tokens", prompt_tokens)

            prefix_allowed_tokens_fn = build_transformers_prefix_allowed_tokens_fn(
                self._tokenizer, JsonSchemaParser(schema, config=parser_config())
            )
            sampling = (
                {
                    "do_sample": True,
                    "temperature": self._config.temperature,
                    "top_p": self._config.top_p,
                    "top_k": self._config.top_k,
                }
                if self._config.temperature > 0
                else {"do_sample": False}
            )

            output = self._config.output
            started = time.monotonic()
            with torch.inference_mode():
                generated = self._model.generate(
                    **inputs,
                    max_new_tokens=output.max_new_tokens,
                    prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
                    stopping_criteria=StoppingCriteriaList(
                        [MaxTimeCriteria(output.timeout_seconds)]
                    ),
                    pad_token_id=self._tokenizer.eos_token_id,
                    **sampling,
                )

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
            code = ERROR_LLM_TRUNCATED if cut_off else ERROR_LLM_INVALID_OUTPUT
            reason = (
                f"generation was cut off after {len(produced)} tokens and {elapsed:.0f}s"
                if cut_off
                else "model returned invalid json"
            )
            raise StageError(code, f"{reason}: {error}") from error


def _quantization_config(config: LlmConfig) -> BitsAndBytesConfig | None:
    if not config.load_in_4bit:
        return None
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=getattr(torch, QUANTIZATION_DTYPE),
        bnb_4bit_quant_type=QUANTIZATION_TYPE,
    )
