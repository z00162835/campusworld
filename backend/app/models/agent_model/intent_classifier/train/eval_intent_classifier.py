"""Greedy-eval intent classifier adapters produced by train_intent_classifier.py.

Run inside Conda ``campusworld`` with the same optional ML stack as training
(see ``requirements/ml-intent-classifier.txt`` and ``train/README.md``).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _load_training_cfg(artifact_dir: Path) -> Dict[str, Any]:
    cfg_path = artifact_dir / "training_config.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"missing {cfg_path}; pass --artifact-dir from a training run output")
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Greedy decode evaluation for LoRA intent adapters")
    parser.add_argument(
        "--artifact-dir",
        required=True,
        help="Training output directory containing training_config.json and lora_adapter/",
    )
    parser.add_argument("--data", required=True, help="Labeled jsonl for scoring")
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument(
        "--system-prompt-file",
        default=str(Path(__file__).resolve().parent.parent / "prompts" / "intent_classifier_system_prompt.txt"),
        help="Must match training prompt file for comparable behavior",
    )
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from app.models.agent_model.intent_classifier.train.dataset_builder import (
        VALID_LABELS,
        IntentTrainSample,
        load_jsonl,
    )

    artifact_dir = Path(args.artifact_dir).resolve()
    adapter_dir = artifact_dir / "lora_adapter"
    training_cfg = _load_training_cfg(artifact_dir)
    base_model_id = str(training_cfg.get("base_model_id") or "").strip()
    if not base_model_id:
        raise ValueError("training_config.json missing base_model_id")

    samples = load_jsonl(Path(args.data).resolve())
    system_prompt = Path(args.system_prompt_file).resolve().read_text(encoding="utf-8")

    tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir), trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    if torch.cuda.is_available():
        device = torch.device("cuda")
        torch_dtype = torch.float16
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        device = torch.device("mps")
        torch_dtype = torch.float16
    else:
        device = torch.device("cpu")
        torch_dtype = torch.float32

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        trust_remote_code=True,
        torch_dtype=torch_dtype,
    )
    model = PeftModel.from_pretrained(base_model, str(adapter_dir))
    model.to(device)
    model.eval()

    correct = 0
    parsed_ok = 0
    rows_total = len(samples)

    def score_sample(sample: IntentTrainSample) -> Tuple[bool, Dict[str, Any]]:
        messages = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": sample.text},
        ]
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=int(args.max_new_tokens),
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        generated = output_ids[0][inputs["input_ids"].shape[-1] :]
        text = tokenizer.decode(generated, skip_special_tokens=True).strip()
        obj: Dict[str, Any]
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return False, {"raw": text, "error": "json_decode"}
        intent = str(obj.get("intent") or "").strip()
        ok_label = intent == sample.label and intent in VALID_LABELS
        return ok_label, {"parsed": obj, "raw": text}

    mismatches: List[Dict[str, Any]] = []
    for sample in samples:
        ok, debug = score_sample(sample)
        if "parsed" in debug:
            parsed_ok += 1
        if ok:
            correct += 1
        else:
            mismatches.append({"text": sample.text, "gold": sample.label, **debug})

    report = {
        "rows": rows_total,
        "parsed_json_rate": parsed_ok / rows_total if rows_total else 0.0,
        "intent_accuracy": correct / rows_total if rows_total else 0.0,
        "artifact_dir": str(artifact_dir),
        "adapter_dir": str(adapter_dir),
        "base_model_id": base_model_id,
        "mismatch_preview": mismatches[:5],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
