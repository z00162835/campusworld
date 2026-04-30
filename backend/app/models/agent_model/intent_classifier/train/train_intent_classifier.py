"""Fine-tune the campusworld intent classifier (optional HF + PEFT stack).

Use the repository-standard Conda env **campusworld** (``conda activate campusworld``,
``cd backend``) before installing PyTorch and ``requirements/ml-intent-classifier.txt``.
Without PyTorch/transformers this script still supports ``--stub-metadata-only``
for artifact/metadata smoke checks in CI.

Typical training (after activating campusworld and installing PyTorch + ml-intent-classifier extras;
defaults assume ~10k labeled JSONL and ``Qwen/Qwen3-4B-Instruct-2507`` — override via CLI/YAML):

    conda activate campusworld
    cd backend
    pip install -r requirements/ml-intent-classifier.txt
    python -m app.models.agent_model.intent_classifier.train.train_intent_classifier \\
      --data app/models/agent_model/intent_classifier/data/seed/intent_seed_v1.jsonl \\
      --output-dir app/models/agent_model/intent_classifier/artifacts/run001 \\
      --model-version intent-classifier-v0 \\
      --data-version intent-seed-v1
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import yaml

from app.models.agent_model.intent_classifier.train.dataset_builder import (
    IntentTrainSample,
    build_chat_turns,
    load_jsonl,
    split_samples,
)


def _defaults_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "intent_classifier_system_prompt.txt"


def load_training_defaults(path: Optional[Path] = None) -> Mapping[str, Any]:
    cfg_path = path or _defaults_path()
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    training = raw.get("training") or {}
    if not isinstance(training, dict):
        raise ValueError(f"{cfg_path}: training section must be a mapping")
    return training


def merge_training_dict(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base)
    for k, v in overlay.items():
        if v is None:
            continue
        merged[k] = v
    return merged


def train_stub(samples: Sequence[IntentTrainSample]) -> Dict[str, object]:
    label_counts: Dict[str, int] = {}
    for s in samples:
        label_counts[s.label] = label_counts.get(s.label, 0) + 1
    total = len(samples)
    majority = max(label_counts, key=label_counts.get) if label_counts else "informational"
    return {
        "total_samples": total,
        "label_counts": label_counts,
        "majority_label": majority,
        "note": "stub summary only",
    }


def _trim_lists(input_ids: List[int], labels: List[int], max_length: int) -> Tuple[List[int], List[int]]:
    if max_length <= 0:
        raise ValueError("max_seq_length must be positive")
    if len(input_ids) <= max_length:
        return input_ids, labels
    overflow = len(input_ids) - max_length
    return input_ids[overflow:], labels[overflow:]


def run_supervised_training(
    *,
    samples: Sequence[IntentTrainSample],
    system_prompt: str,
    training_cfg: Mapping[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    """Lazy-import HF to keep imports cheap when unused."""

    import random

    import numpy as np
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    seed = int(training_cfg.get("seed") or 42)
    set_seed(seed)
    random.seed(seed)
    np.random.seed(seed)

    base_model_id = str(training_cfg.get("base_model_id") or "Qwen/Qwen3-4B-Instruct-2507")
    val_ratio = float(training_cfg.get("val_ratio") or 0.2)

    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    probe_turns = build_chat_turns(system_prompt, samples[0])
    probe_prompt = tokenizer.apply_chat_template(
        probe_turns[:-1],
        tokenize=True,
        add_generation_prompt=True,
        return_tensors=None,
    )
    probe_completion = tokenizer.apply_chat_template(
        probe_turns[-1:],
        tokenize=True,
        add_generation_prompt=False,
        return_tensors=None,
    )
    if not isinstance(probe_prompt, list) or not isinstance(probe_completion, list):
        raise TypeError("tokenizer.apply_chat_template(tokenize=True) must return token id lists")

    max_seq_length = int(training_cfg.get("max_seq_length") or 512)

    def row_dict(idx: int) -> Dict[str, Any]:
        s = samples[idx]
        return {
            "text": s.text,
            "label": s.label,
            "reason_tokens": list(s.reason_tokens),
            "conflict_case": s.conflict_case,
            "has_execute_confirmation": s.has_execute_confirmation,
        }

    def tok_batch(examples: Dict[str, List[Any]]) -> Dict[str, List[List[int]]]:
        input_ids_batch: List[List[int]] = []
        labels_batch: List[List[int]] = []
        batch_n = len(examples["text"])
        for i in range(batch_n):
            rt_raw = examples["reason_tokens"][i]
            reason_tokens = tuple(str(x) for x in rt_raw) if isinstance(rt_raw, list) else ()
            sample = IntentTrainSample(
                text=str(examples["text"][i]),
                label=str(examples["label"][i]),
                reason_tokens=reason_tokens,
                conflict_case=examples["conflict_case"][i],
                has_execute_confirmation=examples["has_execute_confirmation"][i],
            )
            turns = build_chat_turns(system_prompt, sample)
            p_ids = tokenizer.apply_chat_template(
                turns[:-1],
                tokenize=True,
                add_generation_prompt=True,
                return_tensors=None,
            )
            c_ids = tokenizer.apply_chat_template(
                turns[-1:],
                tokenize=True,
                add_generation_prompt=False,
                return_tensors=None,
            )
            if not isinstance(p_ids, list) or not isinstance(c_ids, list):
                raise TypeError("tokenizer.apply_chat_template(tokenize=True) must return token id lists")
            input_ids = p_ids + c_ids
            labels = [-100] * len(p_ids) + c_ids
            input_ids, labels = _trim_lists(input_ids, labels, max_seq_length)
            input_ids_batch.append(input_ids)
            labels_batch.append(labels)
        return {"input_ids": input_ids_batch, "labels": labels_batch}

    train_idx, val_idx = split_samples(samples, val_ratio=val_ratio, seed=seed)

    train_ds = Dataset.from_list([row_dict(i) for i in train_idx])
    eval_ds = Dataset.from_list([row_dict(i) for i in val_idx]) if val_idx else None

    train_ds = train_ds.map(tok_batch, batched=True, remove_columns=train_ds.column_names)
    if eval_ds is not None:
        eval_ds = eval_ds.map(tok_batch, batched=True, remove_columns=eval_ds.column_names)

    torch_dtype = torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        trust_remote_code=True,
        torch_dtype=torch_dtype,
    )

    target_modules = training_cfg.get("lora_target_modules") or [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]
    if not isinstance(target_modules, list) or not all(isinstance(x, str) for x in target_modules):
        raise ValueError("training.lora_target_modules must be a list of strings")

    lora_config = LoraConfig(
        r=int(training_cfg.get("lora_r") or 16),
        lora_alpha=int(training_cfg.get("lora_alpha") or 32),
        lora_dropout=float(training_cfg.get("lora_dropout") or 0.05),
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=target_modules,
    )
    model = get_peft_model(model, lora_config)

    if bool(training_cfg.get("gradient_checkpointing")):
        model.enable_input_require_grads()
        model.gradient_checkpointing_enable()

    collator = DataCollatorForCausalPad(tokenizer)
    train_kw: Dict[str, Any] = dict(
        output_dir=str(output_dir / "hf_trainer"),
        num_train_epochs=float(training_cfg.get("num_train_epochs") or 3),
        per_device_train_batch_size=int(training_cfg.get("per_device_train_batch_size") or 1),
        per_device_eval_batch_size=int(training_cfg.get("per_device_eval_batch_size") or 1),
        gradient_accumulation_steps=int(training_cfg.get("gradient_accumulation_steps") or 4),
        learning_rate=float(training_cfg.get("learning_rate") or 2e-4),
        weight_decay=float(training_cfg.get("weight_decay") or 0.01),
        warmup_ratio=float(training_cfg.get("warmup_ratio") or 0.03),
        logging_steps=int(training_cfg.get("logging_steps") or 1),
        save_strategy="epoch",
        bf16=bool(training_cfg.get("bf16")),
        fp16=bool(training_cfg.get("fp16")),
        seed=seed,
        report_to=[],
        save_total_limit=2,
    )
    if eval_ds is not None:
        train_kw["eval_strategy"] = "epoch"
        train_kw["load_best_model_at_end"] = True
        train_kw["metric_for_best_model"] = "eval_loss"
        train_kw["greater_is_better"] = False
    try:
        training_args = TrainingArguments(**train_kw)
    except TypeError:
        train_kw.pop("eval_strategy", None)
        if eval_ds is not None:
            train_kw["evaluation_strategy"] = "epoch"
        training_args = TrainingArguments(**train_kw)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
        tokenizer=tokenizer,
    )

    train_result = trainer.train()
    metrics = dict(train_result.metrics or {})
    if eval_ds is not None:
        metrics.update(trainer.evaluate())

    adapter_dir = output_dir / "lora_adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    training_cfg_dump = dict(training_cfg)
    training_cfg_dump["base_model_id"] = base_model_id
    (output_dir / "training_config.json").write_text(
        json.dumps(training_cfg_dump, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "metrics": metrics,
        "adapter_dir": str(adapter_dir.resolve()),
        "train_examples": len(train_idx),
        "eval_examples": len(val_idx),
        "base_model_id": base_model_id,
    }


class DataCollatorForCausalPad:
    """Pads variable-length causal LM batches and masks pad labels."""

    def __init__(self, tokenizer):  # type: ignore[no-untyped-def]
        self.tokenizer = tokenizer

    def __call__(self, features: List[MutableMapping[str, Any]]) -> Dict[str, Any]:
        import torch

        pad_id = int(self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)
        max_len = max(len(f["input_ids"]) for f in features)
        input_batch: List[List[int]] = []
        label_batch: List[List[int]] = []
        attn_batch: List[List[int]] = []
        for f in features:
            ids = list(f["input_ids"])
            labs = list(f["labels"])
            pad_len = max_len - len(ids)
            input_batch.append(ids + [pad_id] * pad_len)
            label_batch.append(labs + [-100] * pad_len)
            attn_batch.append([1] * len(ids) + [0] * pad_len)
        batch = {
            "input_ids": torch.tensor(input_batch, dtype=torch.long),
            "labels": torch.tensor(label_batch, dtype=torch.long),
            "attention_mask": torch.tensor(attn_batch, dtype=torch.long),
        }
        return batch


def main() -> int:
    parser = argparse.ArgumentParser(description="CampusWorld intent classifier trainer")
    parser.add_argument("--data", required=True, help="Path to labeled jsonl dataset")
    parser.add_argument("--output-dir", required=True, help="Directory for model artifacts")
    parser.add_argument("--model-version", default="intent-classifier-v0")
    parser.add_argument("--data-version", default="intent-seed-v1")
    parser.add_argument("--config", default=None, help="Optional YAML overlay for training.* keys")
    parser.add_argument(
        "--system-prompt-file",
        default=str(_prompt_path()),
        help="System prompt path used during SFT",
    )
    parser.add_argument(
        "--stub-metadata-only",
        action="store_true",
        help="Skip HF training; emit export_meta.json summary only",
    )
    parser.add_argument("--base-model-id", default=None, help="Override training.base_model_id")
    parser.add_argument("--epochs", type=float, default=None, help="Override training.num_train_epochs")
    parser.add_argument("--lr", type=float, default=None, help="Override training.learning_rate")
    parser.add_argument("--seed", type=int, default=None, help="Override training.seed")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    samples = load_jsonl(data_path)
    summary_stub = train_stub(samples)

    base_training = dict(load_training_defaults())
    if args.config:
        overlay_path = Path(args.config).resolve()
        overlay_raw = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
        overlay_training = overlay_raw.get("training") or {}
        if not isinstance(overlay_training, dict):
            raise ValueError(f"{overlay_path}: training must be a mapping when present")
        base_training = merge_training_dict(base_training, overlay_training)

    cli_overlay: Dict[str, Any] = {}
    if args.base_model_id:
        cli_overlay["base_model_id"] = args.base_model_id
    if args.epochs is not None:
        cli_overlay["num_train_epochs"] = args.epochs
    if args.lr is not None:
        cli_overlay["learning_rate"] = args.lr
    if args.seed is not None:
        cli_overlay["seed"] = args.seed
    training_cfg = merge_training_dict(base_training, cli_overlay)

    system_prompt = Path(args.system_prompt_file).resolve().read_text(encoding="utf-8")

    export_meta: Dict[str, Any] = {
        "model_version": args.model_version,
        "data_version": args.data_version,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "data_path": str(data_path),
        "system_prompt_file": str(Path(args.system_prompt_file).resolve()),
        "stub_summary": summary_stub,
    }

    if args.stub_metadata_only:
        export_meta["training_mode"] = "stub_metadata_only"
        (out_dir / "export_meta.json").write_text(json.dumps(export_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(export_meta, ensure_ascii=False))
        return 0

    try:
        train_report = run_supervised_training(
            samples=samples,
            system_prompt=system_prompt,
            training_cfg=training_cfg,
            output_dir=out_dir,
        )
    except ImportError as exc:
        print(
            "Missing ML dependencies. Use Conda env campusworld (conda activate campusworld; cd backend), "
            "install PyTorch for your platform, then:\n"
            "  pip install -r requirements/ml-intent-classifier.txt\n",
            f"Original error: {exc}",
        )
        return 2
    export_meta["training_mode"] = "peft_lora_sft"
    export_meta["training_report"] = train_report
    (out_dir / "export_meta.json").write_text(json.dumps(export_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(export_meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
