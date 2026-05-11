"""LoRA SFT for router-head multi-label tool prediction (supervised JSON ``tool_names``)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.models.agent_model.tool_router.train.train_common import ROUTER_SYSTEM_PROMPT, ROUTER_TRAIN_SCHEMA_PATH, build_router_user_content, load_router_training_rows, schema_validator
from app.models.agent_model.tool_router.train.train_hf_utils import encode_chat_sft_example, run_lora_training

def main() -> None:
    p = argparse.ArgumentParser(description='Router-head LoRA SFT (multi-label tool_names JSON)')
    p.add_argument('--train-jsonl', type=Path, required=True)
    p.add_argument('--val-jsonl', type=Path, default=None, help='Optional; reserved for future eval hook')
    p.add_argument('--output-dir', type=str, required=True)
    p.add_argument('--base-model', default='Qwen/Qwen2.5-0.5B-Instruct', help='HF model id or local path')
    p.add_argument('--epochs', type=float, default=1.0)
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--grad-accum', type=int, default=8)
    p.add_argument('--lr', type=float, default=0.0002)
    p.add_argument('--max-seq-len', type=int, default=2048)
    p.add_argument('--completion-tokens', type=int, default=256)
    p.add_argument('--lora-r', type=int, default=16)
    p.add_argument('--lora-alpha', type=int, default=32)
    p.add_argument('--warmup-ratio', type=float, default=0.03)
    p.add_argument('--bf16', action='store_true')
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    if args.val_jsonl:
        pass
    validator = schema_validator(ROUTER_TRAIN_SCHEMA_PATH)
    rows = load_router_training_rows(args.train_jsonl, validator=validator)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    features: list = []
    for row in rows:
        tools = row.get('gold_tool_names') or []
        assistant = json.dumps({'tool_names': tools}, ensure_ascii=False)
        feat = encode_chat_sft_example(tokenizer, system=ROUTER_SYSTEM_PROMPT, user=build_router_user_content(row), assistant_text=assistant, max_seq_len=args.max_seq_len, completion_reserved=args.completion_tokens)
        if any((x != -100 for x in feat['labels'])):
            features.append(feat)
    if not features:
        raise SystemExit('No training rows after encoding; raise max-seq-len or check JSONL.')
    run_lora_training(base_model_id=args.base_model, output_dir=args.output_dir, train_features=features, tokenizer=tokenizer, epochs=args.epochs, batch_size=args.batch_size, grad_accum=args.grad_accum, lr=args.lr, lora_r=args.lora_r, lora_alpha=args.lora_alpha, warmup_ratio=args.warmup_ratio, bf16=args.bf16, seed=args.seed)
    meta = {'task': 'router_head', 'base_model': args.base_model, 'schema': 'tool_router_train_row.schema.json', 'assistant_format': '{"tool_names": [...]}', 'n_rows': len(rows), 'n_features': len(features)}
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.output_dir) / 'train_meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
if __name__ == '__main__':
    main()
