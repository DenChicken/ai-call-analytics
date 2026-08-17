import json
import logging
import threading

import torch
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import (
    build_transformers_prefix_allowed_tokens_fn,
)
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from src.config import LlmConfig
from src.schema import parser_config

ROLE_SYSTEM = "system"
ROLE_USER = "user"
QUANTIZATION_DTYPE = "bfloat16"
QUANTIZATION_TYPE = "nf4"
TENSOR_FORMAT = "pt"
THINKING_ENABLED = False

logger = logging.getLogger(__name__)


class LlmError(Exception):
    pass


def _weights_key(config: LlmConfig) -> tuple:
    return (config.local_dir, config.device, config.torch_dtype, config.load_in_4bit)


class Llm:
    def __init__(self, config: LlmConfig, loaded: "Llm | None" = None):
        self._config = config
        if loaded is not None:
            logger.info("reusing loaded llm %s", config.repo_id)
            self._tokenizer = loaded._tokenizer
            self._model = loaded._model
            self._lock = loaded._lock
            return

        if not config.local_dir.is_dir():
            raise FileNotFoundError(
                f"llm directory not found: {config.local_dir}, run scripts/fetch_models.py"
            )
        logger.info("loading llm from %s on %s", config.local_dir, config.device)
        self._tokenizer = AutoTokenizer.from_pretrained(str(config.local_dir))
        self._model = AutoModelForCausalLM.from_pretrained(
            str(config.local_dir),
            dtype=getattr(torch, config.torch_dtype),
            quantization_config=_quantization_config(config),
            device_map=config.device,
        )
        self._model.eval()
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._config.repo_id

    def shares_weights_with(self, config: LlmConfig) -> bool:
        return _weights_key(config) == _weights_key(self._config)

    def generate(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        messages = [
            {"role": ROLE_SYSTEM, "content": system_prompt},
            {"role": ROLE_USER, "content": user_prompt},
        ]
        text = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=THINKING_ENABLED,
        )
        inputs = self._tokenizer(
            text,
            return_tensors=TENSOR_FORMAT,
            truncation=True,
            max_length=self._config.max_input_tokens,
        ).to(self._model.device)
        logger.info("generating from %s input tokens", inputs["input_ids"].shape[1])

        prefix_allowed_tokens_fn = build_transformers_prefix_allowed_tokens_fn(
            self._tokenizer, JsonSchemaParser(schema, config=parser_config())
        )

        with self._lock:
            with torch.inference_mode():
                generated = self._model.generate(
                    **inputs,
                    max_new_tokens=self._config.max_new_tokens,
                    temperature=self._config.temperature,
                    do_sample=self._config.temperature > 0,
                    prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
                    pad_token_id=self._tokenizer.eos_token_id,
                )

        produced = generated[0][inputs["input_ids"].shape[1] :]
        if len(produced) >= self._config.max_new_tokens:
            raise LlmError(
                f"generation hit the max_new_tokens limit of {self._config.max_new_tokens}, "
                "raise it in the config"
            )

        completion = self._tokenizer.decode(produced, skip_special_tokens=True)
        try:
            return json.loads(completion)
        except json.JSONDecodeError as error:
            raise LlmError(f"model returned invalid json: {error}") from error


def _quantization_config(config: LlmConfig) -> BitsAndBytesConfig | None:
    if not config.load_in_4bit:
        return None
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=getattr(torch, QUANTIZATION_DTYPE),
        bnb_4bit_quant_type=QUANTIZATION_TYPE,
    )
