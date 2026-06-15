#!/usr/bin/env python3
"""
Tachiwin-OCR — Base vs Fine-tuned Evaluation Script
====================================================
Evaluates Tachiwin-OCR-1.5 (fine-tuned) against PaddleOCR-VL-1.5 (base)
on tachiwin/ocr-test-challenging-3.

Both models are served via vLLM.  The script starts the vLLM server itself
as a subprocess (the same "bridge" mechanism used in the original notebook),
waits for it to be ready, runs the evaluation loop, then shuts it down and
repeats for the second model.

Usage
-----
    python tachiwin_ocr_comparison_eval.py

The vLLM server is managed automatically — no separate terminal needed.
"""

# ── Standard library ──────────────────────────────────────────────────────────
import gc
import io
import json
import math
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

# ── Third-party (install before running) ─────────────────────────────────────
#   pip install vllm==0.11.1
#   pip install paddlepaddle-gpu==3.4.1
#   pip install -U "paddleocr[doc-parser]==3.4.1"
#   pip install safetensors openai==2.32.0 huggingface_hub pyyaml tqdm nest_asyncio
#   pip install jiwer datasets Pillow scipy

# =============================================================================
# CONFIGURATION
# =============================================================================

# ── Models ────────────────────────────────────────────────────────────────────
FINETUNED_MODEL_ID  = "tachiwin/Tachiwin-OCR-1.5"
BASE_MODEL_ID       = "PaddlePaddle/PaddleOCR-VL-1.5"  # TODO: confirm exact HF repo slug
FINETUNED_MODEL_DIR = "model_finetuned"
BASE_MODEL_DIR      = "model_base"

# ── Dataset ───────────────────────────────────────────────────────────────────
HF_TOKEN                = ""    # leave empty — repos are public
EVAL_DATASET_ID         = "tachiwin/ocr-test-challenging-3"
UNCOMMON_CHAR_SCORE_MIN = 0.4   # rows below this threshold are skipped
MAX_EVAL_ITEMS          = 1000   # items per model run; set to None for all

# ── Output files ──────────────────────────────────────────────────────────────
JSON_FINETUNED  = "eval_finetuned.json"
JSON_BASE       = "eval_base.json"
JSON_COMPARISON = "eval_comparison.json"

# ── vLLM server params — copied verbatim from original notebook ───────────────
GPU_MEMORY_UTILIZATION = 0.85
VLLM_PORT              = 8000
VLLM_MODEL_NAME        = "PaddleOCR-VL-1.5-0.9B"
DOCLAYOUT_MODEL_PATH   = None

# ── Misc ──────────────────────────────────────────────────────────────────────
TEMP_EVAL_DIR = "temp_eval"
os.makedirs(TEMP_EVAL_DIR, exist_ok=True)


# =============================================================================
# MODEL DOWNLOAD
# =============================================================================

def ensure_model(repo_id, local_dir):
    if os.path.exists(local_dir) and os.listdir(local_dir):
        print(f"  '{local_dir}' already present, skipping download.")
        return
    print(f"  Downloading {repo_id} → {local_dir} ...")
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
    )
    print("  Done.")


# =============================================================================
# vLLM SERVER MANAGEMENT
# =============================================================================

_vllm_proc = None


def start_vllm_server(model_dir):
    """Start the vLLM server as a subprocess — same command as the original notebook."""
    global _vllm_proc

    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_dir,
        "--trust-remote-code",
        "--max-num-batched-tokens", "16384",
        "--no-enable-prefix-caching",
        "--mm-processor-cache-gb", "0",
        "--served-model-name", VLLM_MODEL_NAME,
        "--port", str(VLLM_PORT),
        "--gpu-memory-utilization", str(GPU_MEMORY_UTILIZATION),
    ]

    print(f"  Starting vLLM server: {' '.join(cmd)}")
    _vllm_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    print(f"  vLLM server PID: {_vllm_proc.pid}")


def wait_for_server():
    """Poll until the vLLM server responds — copied verbatim from original notebook."""
    import requests
    url = f"http://localhost:{VLLM_PORT}/v1/models"
    print(f"  Waiting for vLLM server at {url}...")
    while True:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("  vLLM server is ready!")
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(5)


def stop_vllm_server():
    """Terminate the vLLM server and flush GPU memory."""
    global _vllm_proc
    if _vllm_proc is None:
        return
    print("  Stopping vLLM server...")
    os.killpg(os.getpgid(_vllm_proc.pid), signal.SIGTERM)
    _vllm_proc.wait(timeout=30)
    _vllm_proc = None
    time.sleep(3)
    import paddle
    paddle.device.cuda.empty_cache()
    gc.collect()
    print("  vLLM server stopped.\n")


# =============================================================================
# OCR HELPER — copied verbatim from original notebook, global pipeline ref
# =============================================================================

OCR_TIMEOUT_SECONDS = 120  # configurable: max seconds per page before restart+retry


_pipeline = None


def _reinit_pipeline(model_dir):
    """Stop the vLLM server, restart it, and reinitialise _pipeline."""
    global _pipeline
    stop_vllm_server()
    start_vllm_server(model_dir)
    wait_for_server()
    from paddleocr import PaddleOCRVL
    _pipeline = PaddleOCRVL(
        vl_rec_backend="vllm-server",
        vl_rec_server_url=f"http://localhost:{VLLM_PORT}/v1",
        layout_detection_model_name="PP-DocLayoutV2",
        layout_detection_model_dir=DOCLAYOUT_MODEL_PATH,
    )


def _ocr_with_timeout_and_retry(pil_image, item_idx: int,
                                model_dir: str, model_id: str) -> str:
    """
    Run ocr_image_to_text in a daemon thread with a wall-clock timeout.
    The thread receives a local reference to the current pipeline so that
    when we restart the server the stuck vLLM HTTP call unblocks on its own
    (the connection is dropped) without us touching _pipeline from the main
    thread while the stuck thread still holds it.
    On timeout: stop+restart the server, reinitialise _pipeline, retry once.
    Raises TimeoutError if the retry also times out.
    """
    import threading

    def _attempt():
        # Capture pipeline reference locally so the stuck thread keeps a valid
        # (though soon-to-be-defunct) object while main thread rebuilds _pipeline.
        local_pipeline = _pipeline
        result_box = []
        exc_box    = []

        def _run():
            try:
                result_box.append(ocr_image_to_text(pil_image, item_idx))
            except Exception as e:
                exc_box.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=OCR_TIMEOUT_SECONDS)
        if t.is_alive():
            return None  # timed out — server kill will unblock the thread
        if exc_box:
            raise exc_box[0]
        return result_box[0]

    result = _attempt()
    if result is not None:
        return result

    print(f"  [timeout] page {item_idx} exceeded {OCR_TIMEOUT_SECONDS}s — "
          "restarting vLLM server and retrying...")
    # Killing the server drops the TCP connection the stuck thread is waiting
    # on, which unblocks it with a connection error — no thread leak.
    _reinit_pipeline(model_dir)
    print("  [timeout] server restarted. Retrying page...")

    result = _attempt()
    if result is not None:
        return result
    raise TimeoutError(
        f"page {item_idx} timed out twice ({OCR_TIMEOUT_SECONDS}s each)"
    )


def ocr_image_to_text(pil_image, item_idx: int) -> str:
    """
    Run the PaddleOCRVL pipeline on a PIL image and return the extracted text.
    Saves/cleans a temporary PNG for each call.
    Copied verbatim from original notebook Cell 8.
    """
    img_path = os.path.join(TEMP_EVAL_DIR, f"eval_img_{item_idx}.png")
    out_dir  = os.path.join(TEMP_EVAL_DIR, f"paddle_out_{item_idx}")
    os.makedirs(out_dir, exist_ok=True)

    try:
        pil_image.save(img_path)

        output = _pipeline.predict(
            img_path,
            use_ocr_for_image_block=False,
            save_crop_res=False,
            markdown_ignore_labels=[
                'number',
                'header',
                'header_image',
                'footer',
                'footer_image',
            ],
        )

        extracted_parts = []
        for res in output:
            res.save_to_markdown(save_path=out_dir)
            md_files = list(Path(out_dir).glob("*.md"))
            if md_files:
                with open(md_files[0], "r", encoding="utf-8") as f:
                    extracted_parts.append(f.read())
            del res
        del output

        return "\n".join(extracted_parts).strip()

    finally:
        if os.path.exists(img_path):  os.remove(img_path)
        if os.path.exists(out_dir):   shutil.rmtree(out_dir)
        for stale in Path(".").glob("output_*"):
            shutil.rmtree(stale, ignore_errors=True)


# =============================================================================
# METRIC HELPERS
# =============================================================================

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_metrics(reference: str, hypothesis: str) -> dict:
    from jiwer import wer, cer
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    if not ref:
        _wer = 0.0 if not hyp else 1.0
        _cer = 0.0 if not hyp else 1.0
    else:
        _wer = wer(ref, hyp)
        _cer = cer(ref, hyp)
    return {
        "wer":           round(float(_wer), 4),
        "cer":           round(float(_cer), 4),
        "char_accuracy": round(max(0.0, 1.0 - float(_cer)), 4),
        "word_accuracy": round(max(0.0, 1.0 - float(_wer)), 4),
        "ref_len_chars": len(ref),
        "hyp_len_chars": len(hyp),
    }


def aggregate(values):
    if not values:
        return {"mean": None, "median": None, "min": None,
                "max": None, "stdev": None, "n": 0}
    return {
        "mean":   round(statistics.mean(values),   4),
        "median": round(statistics.median(values), 4),
        "min":    round(min(values),               4),
        "max":    round(max(values),               4),
        "stdev":  round(statistics.stdev(values),  4) if len(values) > 1 else 0.0,
        "n":      len(values),
    }


def bucket_stats(results, metric="cer", step=0.1):
    scores = [r["uncommon_char_score"] for r in results]
    if not scores:
        return {}
    lo = math.floor(UNCOMMON_CHAR_SCORE_MIN / step) * step
    hi = math.ceil(max(scores) / step) * step
    edges = [round(lo + i * step, 10) for i in range(int(round((hi - lo) / step)) + 1)]
    buckets = {}
    for i in range(len(edges) - 1):
        label = f"[{edges[i]:.1f}, {edges[i+1]:.1f})"
        vals  = [r[metric] for r in results
                 if edges[i] <= r["uncommon_char_score"] < edges[i+1]]
        buckets[label] = aggregate(vals)
    label = f"[{edges[-2]:.1f}, {edges[-1]:.1f}]"
    vals  = [r[metric] for r in results
             if edges[-2] <= r["uncommon_char_score"] <= edges[-1]]
    if vals:
        buckets[label] = aggregate(vals)
    return buckets


def build_summary(results, model_id):
    metric_keys = ["wer", "cer", "char_accuracy", "word_accuracy"]
    summary = {k: aggregate([r[k] for r in results if r.get(k) is not None])
               for k in metric_keys}
    summary["cer_by_score_bucket"] = bucket_stats(results, "cer")
    summary["wer_by_score_bucket"] = bucket_stats(results, "wer")
    summary["model"]   = model_id
    summary["n_items"] = len(results)
    return summary


_report_file = None


def _tee(line=""):
    """Print to console and to the report file if open."""
    print(line)
    if _report_file is not None:
        _report_file.write(line + "\n")
        _report_file.flush()


def print_summary(summary):
    _tee(f"  Model    : {summary['model']}")
    _tee(f"  N items  : {summary['n_items']}")
    for key in ("wer", "cer", "char_accuracy", "word_accuracy"):
        s = summary[key]
        if s["mean"] is None:
            continue
        _tee(f"  {key.upper():<16} mean={s['mean']:.4f}  median={s['median']:.4f}"
             f"  min={s['min']:.4f}  max={s['max']:.4f}  stdev={s['stdev']:.4f}")
    _tee("  CER by uncommon_char_score bucket:")
    for bucket, agg in summary["cer_by_score_bucket"].items():
        if agg["n"]:
            _tee(f"    {bucket}: n={agg['n']:>4}  mean_cer={agg['mean']:.4f}")


# =============================================================================
# CHECKPOINT
# =============================================================================

def _save_checkpoint(output_path, model_id, results, errors):
    payload = {
        "config": {
            "model":                   model_id,
            "eval_dataset":            EVAL_DATASET_ID,
            "uncommon_char_score_min": UNCOMMON_CHAR_SCORE_MIN,
            "max_eval_items":          MAX_EVAL_ITEMS,
            "n_evaluated":             len(results),
            "n_errors":                len(errors),
        },
        "per_item": results,
        "errors":   errors,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _running_stats(results):
    for key in ("wer", "cer", "char_accuracy", "word_accuracy"):
        vals = [r[key] for r in results]
        if not vals:
            continue
        print(
            f"    cumul {key:<16}"
            f" mean={statistics.mean(vals):.4f}"
            f" median={statistics.median(vals):.4f}"
            f" min={min(vals):.4f}"
            f" max={max(vals):.4f}"
            + (f" stdev={statistics.stdev(vals):.4f}" if len(vals) > 1 else "")
        )


# =============================================================================
# EVALUATION LOOP
# =============================================================================

def run_evaluation(model_id, model_dir, output_path, raw_dataset):
    """
    Start vLLM for model_dir, run the streaming eval loop, stop vLLM.
    raw_dataset is a fresh HF streaming dataset iterator.
    """
    global _pipeline

    # ── Resume support ────────────────────────────────────────────────────────
    results, errors = [], []
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            _existing = json.load(f)
        results = _existing.get("per_item", [])
        errors  = _existing.get("errors",   [])
        print(f"  Resuming '{model_id}' — {len(results)} items already done.")
    else:
        print(f"  Starting fresh for '{model_id}'.")

    already_done = len(results)

    # ── Start vLLM server ─────────────────────────────────────────────────────
    start_vllm_server(model_dir)
    wait_for_server()

    # ── Init PaddleOCRVL — copied verbatim from original notebook Cell 6 ──────
    from paddleocr import PaddleOCRVL
    _pipeline = PaddleOCRVL(
        vl_rec_backend="vllm-server",
        vl_rec_server_url=f"http://localhost:{VLLM_PORT}/v1",
        layout_detection_model_name="PP-DocLayoutV2",
        layout_detection_model_dir=DOCLAYOUT_MODEL_PATH,
    )
    print("  PaddleOCRVL pipeline initialized.")
    print("  Pipeline ready. Starting stream...\n")

    from PIL import Image

    evaluated  = len(results)
    _seen      = 0

    try:
        for row in raw_dataset:
            if MAX_EVAL_ITEMS is not None and evaluated >= MAX_EVAL_ITEMS:
                break

            # ── score filter ──────────────────────────────────────────────────
            score = row.get("uncommon_char_score")
            if score is None or float(score) < UNCOMMON_CHAR_SCORE_MIN:
                del row
                continue

            # ── skip rows already processed on a previous run ─────────────────
            if _seen < already_done:
                _seen += 1
                del row
                continue
            _seen += 1

            reference_text = row.get("text", "") or ""
            raw_image      = row.get("image")

            # ── decode image then free row immediately ────────────────────────
            if isinstance(raw_image, Image.Image):
                pil_image = raw_image.convert("RGB")
            elif isinstance(raw_image, dict) and "bytes" in raw_image:
                pil_image = Image.open(io.BytesIO(raw_image["bytes"])).convert("RGB")
            elif isinstance(raw_image, bytes):
                pil_image = Image.open(io.BytesIO(raw_image)).convert("RGB")
            else:
                raise ValueError(f"Unrecognised image type: {type(raw_image)}")
            del raw_image
            del row

            # ── inference ─────────────────────────────────────────────────────
            print(f"  processing item {evaluated} "
                  f"({pil_image.width}x{pil_image.height}px) ...", flush=True)
            try:
                hypothesis_text = _ocr_with_timeout_and_retry(pil_image, evaluated, model_dir, model_id)
            except Exception as ocr_err:
                errors.append({"idx": evaluated, "error": f"OCR: {ocr_err}"})
                evaluated += 1
                _save_checkpoint(output_path, model_id, results, errors)
                continue
            finally:
                pil_image.close()
                del pil_image

            # ── metrics & record ──────────────────────────────────────────────
            metrics = compute_metrics(reference_text, hypothesis_text)
            results.append({
                "idx":                evaluated,
                "uncommon_char_score": float(score),
                **metrics,
            })
            evaluated += 1

            # ── incremental save ──────────────────────────────────────────────
            _save_checkpoint(output_path, model_id, results, errors)

            # ── per-item print ────────────────────────────────────────────────
            print(
                f"[{evaluated:>4}/{MAX_EVAL_ITEMS}] "
                f"WER={metrics['wer']:.3f}  CER={metrics['cer']:.3f}  "
                f"CharAcc={metrics['char_accuracy']:.3f}  "
                f"WordAcc={metrics['word_accuracy']:.3f}  "
                f"score={float(score):.3f}"
            )

            # ── cumulative stats every 10 items ───────────────────────────────
            if evaluated % 10 == 0:
                print(f"  ── cumulative after {evaluated} items ──")
                _running_stats(results)
                gc.collect()

    finally:
        # ── always stop the server, even on crash ─────────────────────────────
        del _pipeline
        _pipeline = None
        stop_vllm_server()

    print(f"\n  Finished '{model_id}': {evaluated} evaluated, {len(errors)} errors.")
    print(f"  Saved to '{output_path}' ({os.path.getsize(output_path):,} bytes)\n")

    return results, errors


# =============================================================================
# STATISTICAL COMPARISON
# =============================================================================

def compare_models(results_a, summary_a, results_b, summary_b):
    from scipy import stats

    map_a = {r["idx"]: r for r in results_a}
    map_b = {r["idx"]: r for r in results_b}
    shared_idx = sorted(set(map_a) & set(map_b))
    print(f"  Shared items for paired tests: {len(shared_idx)}")

    comparison = {
        "model_a":              summary_a["model"],
        "model_b":              summary_b["model"],
        "n_paired":             len(shared_idx),
        "metrics":              {},
        "cer_by_score_bucket_a": summary_a["cer_by_score_bucket"],
        "cer_by_score_bucket_b": summary_b["cer_by_score_bucket"],
        "wer_by_score_bucket_a": summary_a["wer_by_score_bucket"],
        "wer_by_score_bucket_b": summary_b["wer_by_score_bucket"],
    }

    for metric in ("wer", "cer", "char_accuracy", "word_accuracy"):
        vals_a = [map_a[i][metric] for i in shared_idx]
        vals_b = [map_b[i][metric] for i in shared_idx]
        diffs  = [a - b for a, b in zip(vals_a, vals_b)]

        if len(shared_idx) >= 10:
            w_stat, p_wilcoxon = stats.wilcoxon(vals_a, vals_b, alternative="two-sided")
        else:
            w_stat, p_wilcoxon = None, None

        t_stat, p_ttest = stats.ttest_rel(vals_a, vals_b)

        comparison["metrics"][metric] = {
            "model_a_mean":               round(statistics.mean(vals_a), 4),
            "model_b_mean":               round(statistics.mean(vals_b), 4),
            "mean_diff_a_minus_b":        round(statistics.mean(diffs), 4),
            "median_diff":                round(statistics.median(diffs), 4),
            "wilcoxon_statistic":         round(float(w_stat), 4)     if w_stat      is not None else None,
            "wilcoxon_p":                 round(float(p_wilcoxon), 6) if p_wilcoxon  is not None else None,
            "ttest_statistic":            round(float(t_stat), 4)     if t_stat      is not None else None,
            "ttest_p":                    round(float(p_ttest), 6)    if p_ttest     is not None else None,
            "significant_0.05_wilcoxon": bool(p_wilcoxon < 0.05) if p_wilcoxon is not None else None,
            "significant_0.01_wilcoxon": bool(p_wilcoxon < 0.01) if p_wilcoxon is not None else None,
        }

    return comparison


def print_comparison(comparison):
    _tee("\n" + "=" * 70)
    _tee("COMPARISON REPORT")
    _tee("=" * 70)
    _tee(f"  BASE     : {comparison['model_b']}")
    _tee(f"  FINETUNE : {comparison['model_a']}")
    _tee(f"  Paired items : {comparison['n_paired']}")
    _tee()
    _tee(f"  {'Metric':<18} {'BASE mean':>10} {'FINE mean':>10} {'Δ (FINE-BASE)':>14} "
         f"{'Wilcoxon p':>12} {'Signif@0.05':>12}")
    _tee("  " + "-" * 80)
    for metric, m in comparison["metrics"].items():
        sig = m["significant_0.05_wilcoxon"]
        sig_str = ("YES ***" if m.get("significant_0.01_wilcoxon") else
                   "YES *"   if sig else
                   "no"      if sig is False else "n/a")
        p_str = f"{m['wilcoxon_p']:.4f}" if m["wilcoxon_p"] is not None else "n/a"
        # Δ is FINETUNE - BASE, i.e. -(A-B) since A=finetuned, B=base
        delta = -m["mean_diff_a_minus_b"]
        _tee(f"  {metric:<18} {m['model_b_mean']:>10.4f} {m['model_a_mean']:>10.4f} "
             f"{delta:>+14.4f} {p_str:>12} {sig_str:>12}")
    _tee()
    _tee("  CER by score bucket (BASE | FINETUNE):")
    all_buckets = sorted(
        set(comparison["cer_by_score_bucket_a"]) | set(comparison["cer_by_score_bucket_b"])
    )
    _tee(f"  {'Bucket':<18} {'BASE CER':>12} {'FINE CER':>12} {'Δ (FINE-BASE)':>14}")
    _tee("  " + "-" * 60)
    for b in all_buckets:
        a_agg = comparison["cer_by_score_bucket_a"].get(b, {})
        b_agg = comparison["cer_by_score_bucket_b"].get(b, {})
        a_m   = a_agg.get("mean")
        b_m   = b_agg.get("mean")
        if a_m is None and b_m is None:
            continue
        diff_str = f"{a_m - b_m:+.4f}" if (a_m is not None and b_m is not None) else "n/a"
        base_str = f"{b_m:.4f} (n={b_agg.get('n',0)})" if b_m is not None else "n/a"
        fine_str = f"{a_m:.4f} (n={a_agg.get('n',0)})" if a_m is not None else "n/a"
        _tee(f"  {b:<18} {base_str:>12} {fine_str:>12} {diff_str:>14}")
    _tee("=" * 70)
    _tee("  Note: Δ < 0 means FINETUNE is BETTER (lower WER/CER or higher accuracy)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    from datasets import load_dataset

    # ── Download models ───────────────────────────────────────────────────────
    print("=" * 60)
    print("DOWNLOADING MODELS")
    print("=" * 60)
    print("Downloading fine-tuned model...")
    ensure_model(FINETUNED_MODEL_ID, FINETUNED_MODEL_DIR)
    print("Downloading base model...")
    ensure_model(BASE_MODEL_ID, BASE_MODEL_DIR)
    print("Models ready.\n")

    # ── Two independent dataset streams ──────────────────────────────────────
    print("Loading dataset streams...")
    ds_finetuned = load_dataset(EVAL_DATASET_ID, split="train", streaming=True)
    ds_base      = load_dataset(EVAL_DATASET_ID, split="train", streaming=True)
    print("Streams ready.\n")

    # ── Run fine-tuned model ──────────────────────────────────────────────────
    print("=" * 60)
    print(f"EVALUATING: {FINETUNED_MODEL_ID}")
    print("=" * 60)
    results_finetuned, errors_finetuned = run_evaluation(
        model_id=FINETUNED_MODEL_ID,
        model_dir=FINETUNED_MODEL_DIR,
        output_path=JSON_FINETUNED,
        raw_dataset=ds_finetuned,
    )
    summary_finetuned = build_summary(results_finetuned, FINETUNED_MODEL_ID)

    # ── Open report file — written alongside console output from here on ──────
    global _report_file
    _report_file = open("reports.txt", "w", encoding="utf-8")

    print("\nSummary (fine-tuned):")
    _tee("\nSummary (fine-tuned):")
    print_summary(summary_finetuned)

    # ── Run base model ────────────────────────────────────────────────────────
    print("=" * 60)
    print(f"EVALUATING: {BASE_MODEL_ID}")
    print("=" * 60)
    results_base, errors_base = run_evaluation(
        model_id=BASE_MODEL_ID,
        model_dir=BASE_MODEL_DIR,
        output_path=JSON_BASE,
        raw_dataset=ds_base,
    )
    summary_base = build_summary(results_base, BASE_MODEL_ID)
    print("\nSummary (base):")
    _tee("\nSummary (base):")
    print_summary(summary_base)

    # ── Statistical comparison ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("COMPUTING COMPARISON")
    print("=" * 60)
    comparison = compare_models(
        results_finetuned, summary_finetuned,
        results_base,      summary_base,
    )
    print_comparison(comparison)

    # ── Save comparison JSON ──────────────────────────────────────────────────
    comparison_payload = {
        "config": {
            "eval_dataset":            EVAL_DATASET_ID,
            "uncommon_char_score_min": UNCOMMON_CHAR_SCORE_MIN,
            "max_eval_items":          MAX_EVAL_ITEMS,
            "model_a_finetuned":       FINETUNED_MODEL_ID,
            "model_b_base":            BASE_MODEL_ID,
        },
        "summary_finetuned": summary_finetuned,
        "summary_base":      summary_base,
        "comparison":        comparison,
    }
    with open(JSON_COMPARISON, "w", encoding="utf-8") as f:
        json.dump(comparison_payload, f, ensure_ascii=False, indent=2)

    _report_file.close()
    _report_file = None

    print(f"\nAll results saved:")
    for path in (JSON_FINETUNED, JSON_BASE, JSON_COMPARISON, "reports.txt"):
        print(f"  {os.path.abspath(path)}  ({os.path.getsize(path):,} bytes)")


if __name__ == "__main__":
    main()