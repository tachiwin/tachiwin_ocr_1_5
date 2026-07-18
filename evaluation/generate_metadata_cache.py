#!/usr/bin/env python3
"""
Generate metadata_cache.json for the OCR eval stats pipeline.

Streams only metadata columns from a HuggingFace dataset — no images,
no PDFs, no aspect-ratio filtering. Output format matches what
per_language_stats.py expects: a dict {idx: {pdf_hash, page_number,
page_id, uncommon_char_score}}.

Usage:
    export HF_KEY=...
    python generate_metadata_cache.py \
        --dataset tachiwin/ocr-test-challenging-3 \
        --min-score 0.3 \
        --max-items 2000 \
        --output metadata_cache_2000.json
"""

import argparse
import json
import os
import sys

import datasets


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Generate metadata cache from HF dataset")
    p.add_argument("--dataset", default="tachiwin/ocr-test-challenging-3",
                   help="HuggingFace dataset name (default: tachiwin/ocr-test-challenging-3)")
    p.add_argument("--min-score", type=float, default=0.3,
                   help="Minimum uncommon_char_score threshold (default: 0.3)")
    p.add_argument("--max-items", type=int, default=2000,
                   help="Maximum number of items to collect (default: 2000)")
    p.add_argument("--output", default="metadata_cache_2000.json",
                   help="Output JSON path (default: metadata_cache_2000.json)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    print(f"Streaming {args.dataset} ...")
    print(f"  min-score: {args.min_score}  max-items: {args.max_items}")
    print(f"  output:    {args.output}")

    ds = datasets.load_dataset(args.dataset, split="train", streaming=True)

    cache = {}
    skipped = 0
    collected = 0

    for idx, row in enumerate(ds):
        score = float(row["uncommon_char_score"])
        if score < args.min_score:
            skipped += 1
            continue

        cache[str(collected)] = {
            "pdf_hash": row["pdf_hash"],
            "page_number": int(row["page_number"]),
            "page_id": row["page_id"],
            "uncommon_char_score": score,
        }
        collected += 1

        if collected % 500 == 0:
            print(f"  collected: {collected:>5}  skipped: {skipped:>5}  "
                  f"(last score: {score:.4f})", end="\r", flush=True)

        if collected >= args.max_items:
            break

    print(f"\n  Done. Collected {collected} items, skipped {skipped}.")

    if collected < args.max_items:
        print(f"  ⚠  Dataset exhausted after {collected} items (requested {args.max_items})",
              file=sys.stderr)

    with open(args.output, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"  Written {args.output}  ({os.path.getsize(args.output):,} bytes)")


if __name__ == "__main__":
    main()
