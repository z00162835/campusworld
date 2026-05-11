"""LoRA SFT for slot extraction (JSON matching ``tool_router_slot_output.schema.json``)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.models.agent_model.tool_router.train.train_common import SLOT_OUTPUT_SCHEMA_PATH, SLOT_SYSTEM_PROMPT, build_slot_user_content, load_slot_training_rows, schema_validator
from app.models.agent_model.tool_router.train.train_hf_utils import encode_chat_sft_example, run_lora_training

def main() -> None:
    p = argparse.ArgumentParser(description='Slot SLM LoRA SFT (Qwen-style chat models)')
    p.add_argument('--data-jsonl', type=Path, required=True, help='Training JSONL (slot_labels + context)')
    p.add_argument('--output-dir', type=str, required=True, help='Adapter + tokenizer output directory')
    p.add_argument('--base-model', default='Qwen/Qwen2.5-0.5B-Instruct', help='HF model id or local path')
    p.add_argument('--epochs', type=float, default=1.0)
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--grad-accum', type=int, default=8)
    p.add_argument('--lr', type=float, default=0.0002)
    p.add_argument('--max-seq-len', type=int, default=2048)
    p.add_argument('--completion-tokens', type=int, default=384, help='Reserved budget for assistant JSON')
    p.add_argument('--lora-r', type=int, default=16)
    p.add_argument('--lora-alpha', type=int, default=32)
    p.add_argument('--warmup-ratio', type=float, default=0.03)
    p.add_argument('--bf16', action='store_true', help='Use bf16 on CUDA when supported')
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    validator = schema_validator(SLOT_OUTPUT_SCHEMA_PATH)
    rows = load_slot_training_rows(args.data_jsonl, validator=validator)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    features: list = []
    for row in rows:
        assistant = json.dumps(row['slot_labels'], ensure_ascii=False)
        feat = encode_chat_sft_example(tokenizer, system=SLOT_SYSTEM_PROMPT, user=build_slot_user_content(row), assistant_text=assistant, max_seq_len=args.max_seq_len, completion_reserved=args.completion_tokens)
        if any((x != -100 for x in feat['labels'])):
            features.append(feat)
    if not features:
        raise SystemExit('No training rows after encoding; raise max-seq-len or check JSONL.')
    run_lora_training(base_model_id=args.base_model, output_dir=args.output_dir, train_features=features, tokenizer=tokenizer, epochs=args.epochs, batch_size=args.batch_size, grad_accum=args.grad_accum, lr=args.lr, lora_r=args.lora_r, lora_alpha=args.lora_alpha, warmup_ratio=args.warmup_ratio, bf16=args.bf16, seed=args.seed)
    meta = {'task': 'slot_slm', 'base_model': args.base_model, 'schema': 'tool_router_slot_output.schema.json', 'n_rows': len(rows), 'n_features': len(features)}
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.output_dir) / 'train_meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
if __name__ == '__main__':
    main()
