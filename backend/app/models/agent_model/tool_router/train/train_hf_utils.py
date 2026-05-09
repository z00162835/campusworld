"""HF + PEFT LoRA SFT helpers for tool_router train CLIs (imports torch)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from torch.nn.utils.rnn import pad_sequence
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedTokenizerBase,
    Trainer,
    TrainingArguments,
)


def encode_chat_sft_example(
    tokenizer: PreTrainedTokenizerBase,
    *,
    system: str,
    user: str,
    assistant_text: str,
    max_seq_len: int,
    completion_reserved: int,
) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    eos = tokenizer.eos_token or "</s>"
    completion = assistant_text.strip() + eos
    prompt_budget = max(64, max_seq_len - completion_reserved)
    prompt_enc = tokenizer(prompt_text, add_special_tokens=False, truncation=True, max_length=prompt_budget)
    comp_enc = tokenizer(completion, add_special_tokens=False, truncation=True, max_length=completion_reserved)
    input_ids = prompt_enc["input_ids"] + comp_enc["input_ids"]
    if len(input_ids) > max_seq_len:
        input_ids = input_ids[:max_seq_len]
    prompt_len = len(prompt_enc["input_ids"])
    if prompt_len > len(input_ids):
        prompt_len = 0
    labels = [(-100 if j < prompt_len else tid) for j, tid in enumerate(input_ids)]
    return {"input_ids": input_ids, "labels": labels}


@dataclass
class DataCollatorForCausalSFT:
    tokenizer: PreTrainedTokenizerBase
    pad_id: int

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        input_ids = [torch.tensor(f["input_ids"], dtype=torch.long) for f in features]
        labels = [torch.tensor(f["labels"], dtype=torch.long) for f in features]
        input_ids_t = pad_sequence(input_ids, batch_first=True, padding_value=self.pad_id)
        labels_t = pad_sequence(labels, batch_first=True, padding_value=-100)
        attention_mask = input_ids_t.ne(self.pad_id).long()
        return {"input_ids": input_ids_t, "labels": labels_t, "attention_mask": attention_mask}


def run_lora_training(
    *,
    base_model_id: str,
    output_dir: str,
    train_features: List[Dict[str, Any]],
    tokenizer: Optional[PreTrainedTokenizerBase],
    epochs: float,
    batch_size: int,
    grad_accum: int,
    lr: float,
    lora_r: int,
    lora_alpha: int,
    warmup_ratio: float,
    bf16: bool,
    seed: int,
) -> None:
    torch.manual_seed(seed)
    tok = tokenizer or AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    use_cuda = torch.cuda.is_available()
    if use_cuda:
        dtype = torch.bfloat16 if bf16 and torch.cuda.is_bf16_supported() else torch.float16
        model = AutoModelForCausalLM.from_pretrained(
            base_model_id,
            torch_dtype=dtype,
            trust_remote_code=True,
            device_map="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model_id,
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )

    peft_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, peft_config)

    ds = Dataset.from_list(train_features)
    pad_id = tok.pad_token_id or 0
    collator = DataCollatorForCausalSFT(tokenizer=tok, pad_id=pad_id)

    use_bf16 = bool(use_cuda and bf16 and torch.cuda.is_bf16_supported())
    n_steps = max(1, len(train_features) // max(1, batch_size * grad_accum))
    logging_steps = max(1, n_steps // 20)

    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=lr,
        warmup_ratio=warmup_ratio,
        logging_steps=logging_steps,
        save_strategy="epoch",
        seed=seed,
        bf16=use_bf16,
        fp16=bool(use_cuda and not use_bf16),
        remove_unused_columns=False,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds,
        data_collator=collator,
    )
    trainer.train()
    trainer.save_model(output_dir)
    tok.save_pretrained(output_dir)
