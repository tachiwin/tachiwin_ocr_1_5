"""
per_language_stats.py — Tachiwin-OCR-1.5 eval stats
pip install pandas tabulate scipy
"""
import json, os, sys
import argparse
from datetime import datetime
import pandas as pd
from scipy.stats import ttest_rel

MIN_N_DIM      = 3
DIMENSIONS     = ["code", "superlanguage", "family", "collection", "source"]

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Generate per-language eval stats and charts.")
parser.add_argument(
    "--finetuned",
    default="eval_finetuned.json",
    help="Fine-tuned model eval JSON (default: eval_finetuned.json)"
)
parser.add_argument(
    "--base",
    default="eval_base.json",
    help="Base model eval JSON (default: eval_base.json)"
)
parser.add_argument(
    "--catalog",
    default="pdfs_metadata.json",
    help="PDF catalog JSON (default: pdfs_metadata.json)"
)
parser.add_argument(
    "--cache",
    default="eval_metadata_cache.json",
    help="Metadata cache JSON (default: eval_metadata_cache.json)"
)
parser.add_argument(
    "--run-label",
    default="",
    help="Optional label for this run (e.g. 'v1.6-test')"
)
parser.add_argument(
    "--output-dir",
    default="output",
    help="Directory for all output files (default: output)"
)
args = parser.parse_args()

EVAL_FINETUNED = args.finetuned
EVAL_BASE      = args.base
CATALOG_FILE   = args.catalog
CACHE_FILE     = args.cache
RUN_LABEL      = args.run_label
OUTPUT_DIR     = args.output_dir

# ── Output paths (single source of truth) ─────────────────────────────────────
CHARTS_DIR      = os.path.join(OUTPUT_DIR, "charts")
REPORT_FILE     = os.path.join(OUTPUT_DIR, "evaluation_report.md")
DOC_STATS_FILE  = os.path.join(OUTPUT_DIR, "stats_by_document.csv")
def dim_stats_file(dim):
    return os.path.join(OUTPUT_DIR, f"stats_by_{dim}.csv")

# ── Load eval JSONs ───────────────────────────────────────────────────────────
print("Loading eval JSONs...")
with open(EVAL_FINETUNED) as f:
    ft_items = pd.DataFrame(json.load(f)["per_item"]).set_index("idx")
with open(EVAL_BASE) as f:
    base_items = pd.DataFrame(json.load(f)["per_item"]).set_index("idx")
n_pages = len(ft_items)
print(f"  Fine-tuned: {n_pages} rows | Base: {len(base_items)} rows")

# ── Distribution diagnostics ─────────────────────────────────────────────────
print("\n=== Distribution diagnostics (all items) ===")
import numpy as np
for label, vals in [("CER base",   ft_items["cer"].values),
                     ("CER ft",     base_items["cer"].values),
                     ("WER base",   ft_items["wer"].values),
                     ("WER ft",     base_items["wer"].values)]:
    arr = np.array(vals, dtype=float)
    sorted_arr = np.sort(arr)
    n = len(arr)
    p99_idx = int(n * 0.99)
    p95_idx = int(n * 0.95)
    mean = np.mean(arr)
    std = np.std(arr, ddof=1)
    print(f"  {label:12s}: mean={mean:.4f}  std={std:.4f}  var={std*std:.4f}  "
          f"min={arr.min():.4f}  p25={np.percentile(arr,25):.4f}  "
          f"median={np.median(arr):.4f}  p75={np.percentile(arr,75):.4f}  "
          f"p95={sorted_arr[p95_idx]:.4f}  p99={sorted_arr[p99_idx]:.4f}  max={arr.max():.4f}")
    # Count outliers: values > mean + 3*std
    outliers = arr[arr > mean + 3*std]
    if len(outliers) > 0:
        print(f"    ⚠  {len(outliers)} items > mean+3σ ({mean+3*std:.4f}): "
              f"min outlier={outliers.min():.4f}, max outlier={outliers.max():.4f}")

# ── Load metadata cache (skip _ keys appended by previous runs) ───────────────
print(f"Loading cache from {CACHE_FILE}...")
with open(CACHE_FILE) as f:
    cache = json.load(f)
cache_rows = {k: v for k, v in cache.items() if not k.startswith("_")}
df_cache = pd.DataFrame.from_dict(cache_rows, orient="index")
df_cache.index = df_cache.index.astype(int)
df_cache.index.name = "idx"
print(f"  {len(df_cache)} rows. Columns: {list(df_cache.columns)}")

# ── Verify alignment ──────────────────────────────────────────────────────────
print("Verifying alignment...")
mismatches = 0
for i in ft_items.index:
    if i not in df_cache.index:
        continue
    if abs(ft_items.loc[i, "uncommon_char_score"] - float(df_cache.loc[i, "uncommon_char_score"])) > 1e-6:
        mismatches += 1
        if mismatches > 5:
            print("Too many mismatches — aborting."); sys.exit(1)
print(f"  ✅ {mismatches} mismatches.")

# ── Load catalog and join ─────────────────────────────────────────────────────
print(f"Loading catalog {CATALOG_FILE}...")
with open(CATALOG_FILE) as f:
    catalog = json.load(f)
cat_rows = []
for h, meta in catalog.items():
    row = {"pdf_hash": h}
    for k, v in meta.items():
        row[k] = v[0] if (isinstance(v, list) and v) else (None if isinstance(v, list) else v)
    cat_rows.append(row)
df_cat = pd.DataFrame(cat_rows).set_index("pdf_hash")
df_joined = df_cache.join(df_cat, on="pdf_hash", how="left")
print(f"  {df_joined['code'].notna().sum() if 'code' in df_joined.columns else 0}/{len(df_joined)} matched")

# ── Build main dataframe ──────────────────────────────────────────────────────
df = df_joined.copy()
df["cer_ft"]        = ft_items["cer"].values
df["wer_ft"]        = ft_items["wer"].values
df["char_acc_ft"]   = ft_items["char_accuracy"].values
df["cer_base"]      = base_items["cer"].values
df["wer_base"]      = base_items["wer"].values
df["char_acc_base"] = base_items["char_accuracy"].values
df["delta_cer"]     = df["cer_base"] - df["cer_ft"]
df["delta_wer"]     = df["wer_base"] - df["wer_ft"]
df["cer_rel_imp"]   = (df["delta_cer"] / df["cer_base"].replace(0, float("nan"))) * 100

# ── Per-dimension stats ───────────────────────────────────────────────────────
def group_stats(df, col, min_n=3):
    if col not in df.columns:
        print(f"  Column '{col}' not found."); return None
    print(f"\n  ── {col} ──")
    rows = []
    for name, g in df.groupby(col, dropna=True):
        if len(g) < min_n:
            continue
        bm = g["cer_base"].mean()
        fm = g["cer_ft"].mean()
        # Paired t-test: base CER vs ft CER within group
        try:
            _, p = ttest_rel(g["cer_base"].values, g["cer_ft"].values)
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        except Exception:
            p, sig = float("nan"), "n/a"
        rows.append({
            col:                        str(name),
            "Pages":                    len(g),
            "Base CER":                 round(bm, 4),
            "Fine-tuned CER":           round(fm, 4),
            "CER Improvement":          f"{round((bm-fm)/bm*100,1)}%" if bm > 0 else "n/a",
            "Base WER":                 round(g["wer_base"].mean(), 4),
            "Fine-tuned WER":           round(g["wer_ft"].mean(), 4),
            "Base Char Accuracy":       round(g["char_acc_base"].mean(), 4),
            "Fine-tuned Char Accuracy": round(g["char_acc_ft"].mean(), 4),
            "p-value":                  round(float(p), 5) if p == p else "n/a",
            "Significance":             sig,
        })
        # ── Per-group SD diagnostic ────────────────────────────────────────────
        cer_b_arr = g["cer_base"].values
        cer_f_arr = g["cer_ft"].values
        wer_b_arr = g["wer_base"].values
        cer_b_std  = np.std(cer_b_arr, ddof=1)
        cer_f_std  = np.std(cer_f_arr, ddof=1)
        wer_b_std  = np.std(wer_b_arr, ddof=1)
        # Flag if SD is suspiciously large relative to mean
        warn = ""
        if bm > 0 and cer_b_std > bm:
            warn = " ⚠ SD > mean (CER base)"
        elif cer_b_std > 3 * bm and bm > 0:
            warn = " ⚠ SD > 3x mean (CER base)"
        if cer_b_std > 2:
            warn += " 🔥 extreme CER base variance"
        if warn:
            print(f"    [{str(name)[:35]:35s}] n={len(g):4d}  "
                  f"CER_base: mean={bm:.4f}  SD={cer_b_std:.4f}  var={cer_b_std*cer_b_std:.4f}  "
                  f"min={cer_b_arr.min():.4f}  max={cer_b_arr.max():.4f}  |  "
                  f"CER_ft: mean={fm:.4f}  SD={cer_f_std:.4f}  "
                  f"min={cer_f_arr.min():.4f}  max={cer_f_arr.max():.4f}  |  "
                  f"WER_base SD={wer_b_std:.4f}"
                  f"{warn}")
    if not rows: return None
    return pd.DataFrame(rows).sort_values("Pages", ascending=False).reset_index(drop=True)

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("\nComputing per-dimension stats...")
all_stats = {}
for dim in DIMENSIONS:
    s = group_stats(df, dim, min_n=MIN_N_DIM)
    if s is not None and len(s) > 0:
        all_stats[dim] = s
        s.to_csv(dim_stats_file(dim), index=False)
        print(f"  [{dim}] {len(s)} groups → {dim_stats_file(dim)}")

# ── Per-document stats ────────────────────────────────────────────────────────
print("\nComputing per-document stats...")
doc_meta_cols = [c for c in ["pdf_hash","name","code","language","superlanguage",
                              "family","collection","source"] if c in df.columns]
def doc_agg(g):
    bm = g["cer_base"].mean(); fm = g["cer_ft"].mean()
    return pd.Series({
        "Pages":                    len(g),
        "Base CER":                 round(bm, 4),
        "Fine-tuned CER":           round(fm, 4),
        "CER Improvement":          f"{round((bm-fm)/bm*100,1)}%" if bm > 0 else "n/a",
        "Base WER":                 round(g["wer_base"].mean(), 4),
        "Fine-tuned WER":           round(g["wer_ft"].mean(), 4),
        "Base Char Accuracy":       round(g["char_acc_base"].mean(), 4),
        "Fine-tuned Char Accuracy": round(g["char_acc_ft"].mean(), 4),
        **{c: g[c].iloc[0] for c in doc_meta_cols if c != "pdf_hash"},
    })
doc_stats = (df.groupby("pdf_hash", dropna=True)
               .apply(doc_agg, include_groups=False)
               .sort_values("Pages", ascending=False)
               .reset_index())
doc_stats.to_csv(DOC_STATS_FILE, index=False)
print(f"  {len(doc_stats)} documents → {DOC_STATS_FILE}")


# ── Charts ────────────────────────────────────────────────────────────────────
print("\nGenerating charts...")
print("\n=== Chart SD debug — overall ===")
print(f"  Overall CER base  SD: {df['cer_base'].std():.4f}  (mean={df['cer_base'].mean():.4f})")
base_outliers = df[df['cer_base'] > df['cer_base'].mean() + 3*df['cer_base'].std()]
print(f"  CER base outliers (>mean+3σ): {len(base_outliers)} items")
if len(base_outliers) > 0:
    for _, r in base_outliers.head(5).iterrows():
        print(f"    idx={r.name}: CER_base={r['cer_base']:.4f}  CER_ft={r['cer_ft']:.4f}  "
              f"code={r.get('code','?')}  superlang={r.get('superlanguage','?')}")
print(f"  Overall CER ft    SD: {df['cer_ft'].std():.4f}  (mean={df['cer_ft'].mean():.4f})")
print(f"  Overall WER base  SD: {df['wer_base'].std():.4f}  (mean={df['wer_base'].mean():.4f})")
print(f"  Overall WER ft    SD: {df['wer_ft'].std():.4f}  (mean={df['wer_ft'].mean():.4f})")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

os.makedirs(CHARTS_DIR, exist_ok=True)
# ── Color palette ────────────────────────────────────────────────────────────
# Metric-specific (ft, base_dim) — tweak these freely
COLOR_CER = ("#D4A843", "#D8C89A")   # CER:  amber ft, dim beige-gold base
COLOR_WER = ("#5B9BD5", "#B6CCE0")   # WER:  slightly different blue
COLOR_ACC = ("#93A241", "#C4CCA8")   # Acc:  green ft, dim green-gray base
# Fallback / general
BRAND = COLOR_CER[0]
GRAY  = COLOR_CER[1]
chart_refs = {}

def savefig(name, caption, dim="general"):
    full_path = os.path.join(CHARTS_DIR, f"{name}.png")
    # Relative path from OUTPUT_DIR — used in markdown report (also in OUTPUT_DIR)
    rel_path  = os.path.relpath(full_path, OUTPUT_DIR)
    plt.tight_layout()
    plt.savefig(full_path, dpi=130, bbox_inches="tight")
    plt.close()
    chart_refs.setdefault(dim, []).append((caption, rel_path))
    print(f"  {full_path}")

def clean(series):
    """Strip significance markers from label strings."""
    return series.str.replace(r" \*+$", "", regex=True).str.strip()

def sig_bracket(ax, x_ft, y_ft, sig, y_offset=0.02):
    """Draw significance star above the fine-tuned bar."""
    if sig not in ("*", "**", "***"):
        return
    top = y_ft + y_offset
    ax.text(x_ft, top, sig, ha="center", va="bottom", fontsize=9, color="black", fontweight="bold")

def clip_err(vals, sds):
    """Return (err_low, err_high) so bars never go below 0."""
    vals = np.array(vals, dtype=float)
    sds  = np.array(sds,  dtype=float)
    err_low  = np.minimum(sds, vals)   # don't go below 0
    err_high = sds
    return [err_low, err_high]

def grouped_bar_chart(ax, x, labels, base_vals, ft_vals, base_sd, ft_sd,
                      sig_list, ylabel, title, rot=35, dim_name="",
                      base_color=None, ft_color=None):
    """Generic grouped bar with SD error bars and sig stars above FT bar.
    base_color / ft_color: hex or name. If None, falls back to GRAY / BRAND globals.
    """
    if base_color is None: base_color = GRAY
    if ft_color   is None: ft_color   = BRAND
    # ── Debug SD for this chart ───────────────────────────────────────────────
    print(f"\n  [chart {dim_name or title}]:")
    for i, (lbl, bv, fv, bsd, fsd) in enumerate(zip(labels, base_vals, ft_vals, base_sd, ft_sd)):
        if bsd > bv and bv > 0:
            print(f"    ⚠ '{lbl[:30]}': base SD={bsd:.4f} > base mean={bv:.4f}  (SD/mean={bsd/bv:.1f}x)")
        if fsd > fv and fv > 0:
            print(f"    ⚠ '{lbl[:30]}': ft   SD={fsd:.4f} > ft   mean={fv:.4f}  (SD/mean={fsd/fv:.1f}x)")
        if bsd > 5 * bv and bv > 0:
            print(f"    🔥 '{lbl[:30]}': base SD={bsd:.4f} is {bsd/bv:.0f}x mean={bv:.4f} (massive outlier skew)")
    w = 0.35
    bars_b = ax.bar(x - w/2, base_vals, w, label="Base",       color=base_color,
                    yerr=clip_err(base_vals, base_sd), capsize=3, error_kw={"elinewidth":1})
    bars_f = ax.bar(x + w/2, ft_vals,   w, label="Fine-tuned", color=ft_color,
                    yerr=clip_err(ft_vals,  ft_sd),   capsize=3, error_kw={"elinewidth":1})
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=rot, ha="right", fontsize=8)
    ax.set_ylabel(ylabel); ax.set_title(title); ax.legend()
    # sig stars above FT bar
    y_max = max((v + e) for v, e in zip(ft_vals, ft_sd) if not np.isnan(e))
    offset = y_max * 0.04
    for xi, (yf, yf_sd, sig) in enumerate(zip(ft_vals, ft_sd, sig_list)):
        sig_bracket(ax, xi + w/2, yf + yf_sd, sig, offset)

def hbar_chart(ax, labels, vals, sds, sig_list, xlabel, title, dim_name="", clip_zero=True):
    """Horizontal bar with SD and sig stars.
    clip_zero: if True, clamp error bars so the bar never visually crosses 0.
               Set to False when the metric can meaningfully be negative (e.g. improvement %).
    """
    y = np.arange(len(labels))
    vals_a = np.array(vals, dtype=float)
    sds_a  = np.array(sds,  dtype=float)
    # ── Debug SD ──────────────────────────────────────────────────────────────
    print(f"\n  [hbar {dim_name or title}]:")
    for lbl, v, s in zip(labels, vals, sds):
        if s > abs(v) and v != 0:
            print(f"    ⚠ '{lbl[:30]}': SD={s:.2f} {'>' if v>=0 else '<'} mean={v:.2f}  (SD/|mean|={s/abs(v):.1f}x)")
    if clip_zero:
        xerr_low  = np.minimum(sds_a, np.abs(vals_a))
        xerr_high = np.minimum(sds_a, np.abs(vals_a))
        xerr = [xerr_low, xerr_high]
    else:
        xerr = sds_a  # symmetric — allows bars to cross 0
    bars = ax.barh(y, vals, color=BRAND, xerr=xerr, capsize=3, error_kw={"elinewidth":1})
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel(xlabel); ax.set_title(title)
    # Compute full extent for text offset (handle negative vals)
    if clip_zero:
        x_max = max(v + e for v, e in zip(vals, sds) if not np.isnan(e))
    else:
        x_max = max(abs(v) + e for v, e in zip(vals, sds) if not np.isnan(e))
    for bar, val, sd, sig in zip(bars, vals, sds, sig_list):
        lbl = f"{val:.1f}%"
        if sig in ("*","**","***"): lbl += f" {sig}"
        if val >= 0:
            ax.text(val + sd + x_max*0.01, bar.get_y() + bar.get_height()/2,
                    lbl, va="center", fontsize=8)
        else:
            ax.text(val - sd - x_max*0.01, bar.get_y() + bar.get_height()/2,
                    lbl, ha="right", va="center", fontsize=8)

def per_item_sd(df, group_col, group_val, metric):
    g = df[df[group_col] == group_val]
    return g[metric].std() if len(g) > 1 else 0.0

def bucket_sd(df, lo, hi, metric):
    g = df[(df["uncommon_char_score"] >= lo) & (df["uncommon_char_score"] < hi)]
    return g[metric].std() if len(g) > 1 else 0.0

# ── 01. Overall CER ───────────────────────────────────────────────────────────
_, p_overall_cer = ttest_rel(df["cer_base"].values, df["cer_ft"].values)
sig_overall = "***" if p_overall_cer < 0.001 else "**" if p_overall_cer < 0.01 else "*" if p_overall_cer < 0.05 else "ns"
fig, ax = plt.subplots(figsize=(5, 4))
vals = [df["cer_base"].mean(), df["cer_ft"].mean()]
sds  = [df["cer_base"].std(),  df["cer_ft"].std()]
bars = ax.bar(["Base model","Tachiwin-OCR-1.5"], vals, color=[COLOR_CER[1], COLOR_CER[0]], width=0.5,
              yerr=clip_err(vals, sds), capsize=4, error_kw={"elinewidth":1.2})
# sig bracket between the two bars
y_top = max(v+s for v,s in zip(vals,sds)) * 1.15
ax.set_ylim(top=y_top * 1.12)
ax.annotate("", xy=(1, y_top), xytext=(0, y_top),
            arrowprops=dict(arrowstyle="-", color="black", lw=1.2))
ax.text(0.5, y_top + y_top*0.015, sig_overall, ha="center", fontsize=11, fontweight="bold")
ax.set_ylabel("Mean CER"); ax.set_title("Overall CER: Base vs Fine-tuned")
savefig("01_overall_cer", "Overall CER comparison", "general")

# ── 02. Overall WER ───────────────────────────────────────────────────────────
_, p_overall_wer = ttest_rel(df["wer_base"].values, df["wer_ft"].values)
sig_wer = "***" if p_overall_wer < 0.001 else "**" if p_overall_wer < 0.01 else "*" if p_overall_wer < 0.05 else "ns"
fig, ax = plt.subplots(figsize=(5, 4))
vals = [df["wer_base"].mean(), df["wer_ft"].mean()]
sds  = [df["wer_base"].std(),  df["wer_ft"].std()]
bars = ax.bar(["Base model","Tachiwin-OCR-1.5"], vals, color=[COLOR_WER[1], COLOR_WER[0]], width=0.5,
              yerr=clip_err(vals, sds), capsize=4, error_kw={"elinewidth":1.2})
# sig bracket between the two bars
y_top = max(v+s for v,s in zip(vals,sds)) * 1.15
ax.set_ylim(top=y_top * 1.12)
ax.annotate("", xy=(1, y_top), xytext=(0, y_top),
            arrowprops=dict(arrowstyle="-", color="black", lw=1.2))
ax.text(0.5, y_top + y_top*0.015, sig_wer, ha="center", fontsize=11, fontweight="bold")
ax.set_ylabel("Mean WER"); ax.set_title("Overall WER: Base vs Fine-tuned")
savefig("02_overall_wer", "Overall WER comparison", "general")

# ── 03. Overall Char Accuracy ─────────────────────────────────────────────────
_, p_overall_acc = ttest_rel(df["char_acc_base"].values, df["char_acc_ft"].values)
sig_acc = "***" if p_overall_acc < 0.001 else "**" if p_overall_acc < 0.01 else "*" if p_overall_acc < 0.05 else "ns"
fig, ax = plt.subplots(figsize=(5, 4))
vals = [df["char_acc_base"].mean(), df["char_acc_ft"].mean()]
sds  = [df["char_acc_base"].std(),  df["char_acc_ft"].std()]
bars = ax.bar(["Base model","Tachiwin-OCR-1.5"], vals, color=[COLOR_ACC[1], COLOR_ACC[0]], width=0.5,
              yerr=clip_err(vals, sds), capsize=4, error_kw={"elinewidth":1.2})
# sig bracket between the two bars
y_top = max(v+s for v,s in zip(vals,sds)) * 1.15
ax.set_ylim(top=y_top * 1.12)
ax.annotate("", xy=(1, y_top), xytext=(0, y_top),
            arrowprops=dict(arrowstyle="-", color="black", lw=1.2))
ax.text(0.5, y_top + y_top*0.015, sig_acc, ha="center", fontsize=11, fontweight="bold")
ax.set_ylabel("Mean Char Accuracy"); ax.set_title("Overall Char Accuracy: Base vs Fine-tuned")
savefig("03_overall_accuracy", "Overall Char Accuracy comparison", "general")

# ── 04. CER by bucket ─────────────────────────────────────────────────────────
bucket_defs = [(0.4,0.5),(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.0)]
b_labels, b_base, b_ft, b_base_sd, b_ft_sd, b_sigs = [], [], [], [], [], []
for lo, hi in bucket_defs:
    g = df[(df["uncommon_char_score"] >= lo) & (df["uncommon_char_score"] < hi)]
    if len(g) < 3: continue
    try:
        _, p = ttest_rel(g["cer_base"].values, g["cer_ft"].values)
        sig = "***" if p<0.001 else "**" if p<0.01 else "*" if p<0.05 else "ns"
    except: sig = "n/a"
    b_labels.append(f"[{lo:.1f},{hi:.1f})")
    b_base.append(g["cer_base"].mean()); b_ft.append(g["cer_ft"].mean())
    b_base_sd.append(g["cer_base"].std()); b_ft_sd.append(g["cer_ft"].std())
    b_sigs.append(sig)
x = np.arange(len(b_labels))
fig, ax = plt.subplots(figsize=(9, 4))
grouped_bar_chart(ax, x, b_labels, b_base, b_ft, b_base_sd, b_ft_sd,
                  b_sigs, "Mean CER", "CER by uncommon_char_score bucket", rot=0, dim_name="bucket",
                  base_color=COLOR_CER[1], ft_color=COLOR_CER[0])
savefig("04_cer_by_bucket", "CER by difficulty bucket", "general")

# ── 05. WER by bucket ────────────────────────────────────────────────────────────
bucket_defs = [(0.4,0.5),(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.0)]
b_labels_w, b_base_w, b_ft_w, b_base_sd_w, b_ft_sd_w, b_sigs_w = [], [], [], [], [], []
for lo, hi in bucket_defs:
    g = df[(df["uncommon_char_score"] >= lo) & (df["uncommon_char_score"] < hi)]
    if len(g) < 3: continue
    try:
        _, p = ttest_rel(g["wer_base"].values, g["wer_ft"].values)
        sig = "***" if p<0.001 else "**" if p<0.01 else "*" if p<0.05 else "ns"
    except: sig = "n/a"
    b_labels_w.append(f"[{lo:.1f},{hi:.1f})")
    b_base_w.append(g["wer_base"].mean()); b_ft_w.append(g["wer_ft"].mean())
    b_base_sd_w.append(g["wer_base"].std()); b_ft_sd_w.append(g["wer_ft"].std())
    b_sigs_w.append(sig)
x = np.arange(len(b_labels_w))
fig, ax = plt.subplots(figsize=(9, 4))
grouped_bar_chart(ax, x, b_labels_w, b_base_w, b_ft_w, b_base_sd_w, b_ft_sd_w,
                  b_sigs_w, "Mean WER", "WER by uncommon_char_score bucket", rot=0, dim_name="bucket_wer",
                  base_color=COLOR_WER[1], ft_color=COLOR_WER[0])
savefig("05_wer_by_bucket", "WER by difficulty bucket", "general")

# ── 06. Char Accuracy by bucket ──────────────────────────────────────────────────
bucket_defs = [(0.4,0.5),(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.0)]
b_labels_a, b_base_a, b_ft_a, b_base_sd_a, b_ft_sd_a, b_sigs_a = [], [], [], [], [], []
for lo, hi in bucket_defs:
    g = df[(df["uncommon_char_score"] >= lo) & (df["uncommon_char_score"] < hi)]
    if len(g) < 3: continue
    try:
        _, p = ttest_rel(g["char_acc_base"].values, g["char_acc_ft"].values)
        sig = "***" if p<0.001 else "**" if p<0.01 else "*" if p<0.05 else "ns"
    except: sig = "n/a"
    b_labels_a.append(f"[{lo:.1f},{hi:.1f})")
    b_base_a.append(g["char_acc_base"].mean()); b_ft_a.append(g["char_acc_ft"].mean())
    b_base_sd_a.append(g["char_acc_base"].std()); b_ft_sd_a.append(g["char_acc_ft"].std())
    b_sigs_a.append(sig)
x = np.arange(len(b_labels_a))
fig, ax = plt.subplots(figsize=(9, 4))
grouped_bar_chart(ax, x, b_labels_a, b_base_a, b_ft_a, b_base_sd_a, b_ft_sd_a,
                  b_sigs_a, "Mean Char Accuracy", "Char Accuracy by uncommon_char_score bucket", rot=0, dim_name="bucket_acc",
                  base_color=COLOR_ACC[1], ft_color=COLOR_ACC[0])
savefig("06_characc_by_bucket", "Char Accuracy by difficulty bucket", "general")

# ── Helper: build arrays from all_stats for a dimension ───────────────────────
def dim_arrays(stats, dim, base_col, ft_col, top_n=None, sort_col=None):
    s = stats.copy()
    s[dim] = clean(s[dim])
    if sort_col: s = s.nsmallest(top_n or len(s), sort_col)
    elif top_n:  s = s.head(top_n)
    labels = s[dim].tolist()
    bv = s[base_col].tolist(); fv = s[ft_col].tolist()
    # SD: per-item from df grouped by original (unmarked) dim value
    bsd, fsd = [], []
    for lbl in labels:
        mask = df[dim].astype(str).str.strip() == lbl if dim in df.columns else pd.Series([False]*len(df))
        g = df[mask]
        bsd.append(g[base_col.lower().replace(" ","_").replace("-","_")].std() if len(g)>1 else 0)
        fsd.append(g[ft_col.lower().replace(" ","_").replace("-","_")].std()  if len(g)>1 else 0)
    sigs = s["Significance"].tolist()
    return labels, bv, fv, bsd, fsd, sigs

# Simpler SD pull direct from df
def sd_from_df(df, dim_col, labels, metric_col):
    """Compute SD of metric_col for each label group, using exact groupby match."""
    grouped = df.groupby(dim_col)[metric_col].std()
    result = []
    for lbl in labels:
        result.append(float(grouped.get(lbl, 0.0)) if not pd.isna(grouped.get(lbl, float("nan"))) else 0.0)
    return result

# ── 07. CER by superlanguage ──────────────────────────────────────────────────
if "superlanguage" in all_stats:
    s = all_stats["superlanguage"].copy()
    s["superlanguage"] = clean(s["superlanguage"])
    s = s.nsmallest(12, "Fine-tuned CER")
    labels = s["superlanguage"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    grouped_bar_chart(ax, x, labels,
        s["Base CER"].tolist(), s["Fine-tuned CER"].tolist(),
        sd_from_df(df, "superlanguage", labels, "cer_base"),
        sd_from_df(df, "superlanguage", labels, "cer_ft"),
        s["Significance"].tolist(), "Mean CER", "CER by superlanguage (top 12)", dim_name="superlanguage_cer",
        base_color=COLOR_CER[1], ft_color=COLOR_CER[0])
    savefig("07_superlanguage_cer", "CER by superlanguage", "superlanguage")

# ── 08. WER by superlanguage ──────────────────────────────────────────────────
if "superlanguage" in all_stats:
    s = all_stats["superlanguage"].copy()
    s["superlanguage"] = clean(s["superlanguage"])
    s = s.nsmallest(12, "Fine-tuned WER")
    labels = s["superlanguage"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    grouped_bar_chart(ax, x, labels,
        s["Base WER"].tolist(), s["Fine-tuned WER"].tolist(),
        sd_from_df(df, "superlanguage", labels, "wer_base"),
        sd_from_df(df, "superlanguage", labels, "wer_ft"),
        s["Significance"].tolist(), "Mean WER", "WER by superlanguage (top 12)", dim_name="superlanguage_wer",
        base_color=COLOR_WER[1], ft_color=COLOR_WER[0])
    savefig("08_superlanguage_wer", "WER by superlanguage", "superlanguage")

# ── 09. Char Accuracy by superlanguage ────────────────────────────────────────
if "superlanguage" in all_stats:
    s = all_stats["superlanguage"].copy()
    s["superlanguage"] = clean(s["superlanguage"])
    s = s.nlargest(12, "Fine-tuned Char Accuracy")
    labels = s["superlanguage"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    grouped_bar_chart(ax, x, labels,
        s["Base Char Accuracy"].tolist(), s["Fine-tuned Char Accuracy"].tolist(),
        sd_from_df(df, "superlanguage", labels, "char_acc_base"),
        sd_from_df(df, "superlanguage", labels, "char_acc_ft"),
        s["Significance"].tolist(), "Mean Char Accuracy", "Char Accuracy by superlanguage (top 12)", dim_name="superlanguage_acc",
        base_color=COLOR_ACC[1], ft_color=COLOR_ACC[0])
    savefig("09_superlanguage_accuracy", "Char Accuracy by superlanguage", "superlanguage")

# ── 10. CER by linguistic family ──────────────────────────────────────────────
if "family" in all_stats:
    s = all_stats["family"].copy()
    s["family"] = clean(s["family"])
    labels = s["family"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(7, len(labels)*0.7), 4.5))
    grouped_bar_chart(ax, x, labels,
        s["Base CER"].tolist(), s["Fine-tuned CER"].tolist(),
        sd_from_df(df, "family", labels, "cer_base"),
        sd_from_df(df, "family", labels, "cer_ft"),
        s["Significance"].tolist(), "Mean CER", "CER by linguistic family", dim_name="family_cer",
        base_color=COLOR_CER[1], ft_color=COLOR_CER[0])
    savefig("10_family_cer", "CER by linguistic family", "family")

# ── 11. CER improvement % by family (horizontal) ─────────────────────────────
if "family" in all_stats:
    s = all_stats["family"].copy()
    s["family"] = clean(s["family"])
    s["imp"] = s["CER Improvement"].str.replace("%","").astype(float)
    s["imp_sd"] = [df[df["family"]==lbl]["cer_rel_imp"].std() if (df["family"]==lbl).any() else 0
                   for lbl in s["family"]]
    s = s.sort_values("imp", ascending=True)
    fig, ax = plt.subplots(figsize=(7, max(3, len(s)*0.5)))
    hbar_chart(ax, s["family"].tolist(), s["imp"].tolist(),
               s["imp_sd"].tolist(), s["Significance"].tolist(),
               "CER Improvement %", "CER Improvement % by linguistic family", dim_name="family_improvement", clip_zero=False)
    savefig("11_family_improvement", "CER improvement % by linguistic family", "family")

# ── 12. CER by collection ─────────────────────────────────────────────────────
if "collection" in all_stats:
    s = all_stats["collection"].copy()
    s["collection"] = clean(s["collection"])
    labels = s["collection"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(8, len(labels)*0.8), 4.5))
    grouped_bar_chart(ax, x, labels,
        s["Base CER"].tolist(), s["Fine-tuned CER"].tolist(),
        sd_from_df(df, "collection", labels, "cer_base"),
        sd_from_df(df, "collection", labels, "cer_ft"),
        s["Significance"].tolist(), "Mean CER", "CER by collection type", dim_name="collection_cer",
        base_color=COLOR_CER[1], ft_color=COLOR_CER[0])
    savefig("12_collection_cer", "CER by collection type", "collection")

# ── 13. CER by source institution ────────────────────────────────────────────
if "source" in all_stats:
    s = all_stats["source"].copy()
    s["source"] = clean(s["source"])
    labels = s["source"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(7, len(labels)*0.8), 4.5))
    grouped_bar_chart(ax, x, labels,
        s["Base CER"].tolist(), s["Fine-tuned CER"].tolist(),
        sd_from_df(df, "source", labels, "cer_base"),
        sd_from_df(df, "source", labels, "cer_ft"),
        s["Significance"].tolist(), "Mean CER", "CER by source institution", dim_name="source_cer",
        base_color=COLOR_CER[1], ft_color=COLOR_CER[0])
    savefig("13_source_cer", "CER by source institution", "source")

# ── 14. CER by code (language) ───────────────────────────────────────────────
if "code" in all_stats:
    s = all_stats["code"].copy()
    s["code"] = clean(s["code"])
    s["imp"] = s["CER Improvement"].str.replace("%","").astype(float)
    s = s.sort_values("imp", ascending=False)
    labels = s["code"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(10, len(labels)*0.65), 5.5))
    grouped_bar_chart(ax, x, labels,
        s["Base CER"].tolist(), s["Fine-tuned CER"].tolist(),
        sd_from_df(df, "code", labels, "cer_base"),
        sd_from_df(df, "code", labels, "cer_ft"),
        s["Significance"].tolist(), "Mean CER", "CER by language code (sorted by improvement)", dim_name="code_cer",
        base_color=COLOR_CER[1], ft_color=COLOR_CER[0])
    savefig("14_code_cer", "CER by language code", "code")

# ── 15. CER improvement % by code (horizontal) ───────────────────────────────
if "code" in all_stats:
    s = all_stats["code"].copy()
    s["code"] = clean(s["code"])
    s["imp"] = s["CER Improvement"].str.replace("%","").astype(float)
    s["imp_sd"] = [df[df["code"]==lbl]["cer_rel_imp"].std() if (df["code"]==lbl).any() else 0
                   for lbl in s["code"]]
    s = s.sort_values("imp", ascending=True)
    fig, ax = plt.subplots(figsize=(8, max(4, len(s)*0.5)))
    hbar_chart(ax, s["code"].tolist(), s["imp"].tolist(),
               s["imp_sd"].tolist(), s["Significance"].tolist(),
               "CER Improvement %", "CER Improvement % by language code", dim_name="code_improvement", clip_zero=False)
    savefig("15_code_improvement", "CER improvement % by language code", "code")

# ── 16. Scatter: coverage vs improvement (superlanguage) ─────────────────────
if "superlanguage" in all_stats:
    s = all_stats["superlanguage"].copy()
    s["superlanguage"] = clean(s["superlanguage"])
    s["imp"] = s["CER Improvement"].str.replace("%","").astype(float)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [BRAND if sig in ("*","**","***") else GRAY for sig in s["Significance"]]
    ax.scatter(s["Pages"], s["imp"], c=colors, s=70, zorder=3)
    for _, r in s.iterrows():
        ax.annotate(r["superlanguage"], (r["Pages"], r["imp"]),
                    fontsize=7, xytext=(4,2), textcoords="offset points")
    ax.set_xlabel("Pages in eval set"); ax.set_ylabel("CER Improvement %")
    ax.set_title("Sample size vs CER improvement\n(green = significant p<0.05)")
    ax.grid(True, alpha=0.3)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BRAND,label="significant"),
                        Patch(color=GRAY,label="not significant")])
    savefig("16_scatter_coverage_improvement", "Sample size vs CER improvement", "superlanguage")

print(f"  {sum(len(v) for v in chart_refs.values())} charts saved to {CHARTS_DIR}/")

# ── Write evaluation report ───────────────────────────────────────────────────
print(f"\nWriting {REPORT_FILE}...")
md = [
    "# Tachiwin-OCR-1.5 Evaluation Report\n",
    f"{n_pages}-page benchmark · uncommon_char_score ≥ 0.4  |  Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{' · ' + RUN_LABEL if RUN_LABEL else ''}\n",
    "",
    "**Base model:** [PaddleOCR-VL-1.5](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5)  "
    "·  **Fine-tuned model:** [Tachiwin-OCR-1.5](https://huggingface.co/tachiwin/Tachiwin-OCR-1.5)\n",
    "",
    f"Significance (paired t-test, base CER vs fine-tuned CER within group): *** p<0.001  ** p<0.01  * p<0.05  ns=not significant\n",
    f"Overall: base CER {df['cer_base'].mean():.4f} → ft CER {df['cer_ft'].mean():.4f} "
    f"(−{df['cer_rel_imp'].mean():.1f}% relative)\n",
]
for caption, path in chart_refs.get("general", []):
    md.append(f"\n![{caption}]({path})\n")

# Bucket table with significance
md.append("\n## By uncommon_char_score bucket\n")
bucket_rows = []
for lo, hi in [(0.4,0.5),(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.0)]:
    g = df[(df["uncommon_char_score"] >= lo) & (df["uncommon_char_score"] < hi)]
    if len(g) < 3:
        continue
    bm = g["cer_base"].mean(); fm = g["cer_ft"].mean()
    try:
        _, p = ttest_rel(g["cer_base"].values, g["cer_ft"].values)
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        p_str = f"{p:.5f}"
    except Exception:
        sig, p_str = "n/a", "n/a"
    bucket_rows.append({
        "Score range":       f"[{lo:.1f}, {hi:.1f})",
        "Pages":             len(g),
        "Base CER":          round(bm, 4),
        "Fine-tuned CER":    round(fm, 4),
        "CER Improvement":   f"{round((bm-fm)/bm*100,1)}%" if bm > 0 else "n/a",
        "Base WER":          round(g["wer_base"].mean(), 4),
        "Fine-tuned WER":    round(g["wer_ft"].mean(), 4),
        "Base Char Accuracy":       round(g["char_acc_base"].mean(), 4),
        "Fine-tuned Char Accuracy": round(g["char_acc_ft"].mean(), 4),
        "p-value":           p_str,
        "Significance":      sig,
    })
md.append(pd.DataFrame(bucket_rows).to_markdown(index=False))
md.append("")
for caption, path in chart_refs.get("general", [])[1:]:  # bucket chart already in general[1]
    pass  # already added above

for dim, stats in all_stats.items():
    md.append(f"\n## By {dim} (n ≥ {MIN_N_DIM})\n")
    md.append(stats.to_markdown(index=False))
    md.append("")
    for caption, path in chart_refs.get(dim, []):
        md.append(f"\n![{caption}]({path})\n")

# Per-document: one section per doc to avoid wide table
md.append(f"\n## By document ({len(doc_stats)} PDFs)\n")
meta_cols = [c for c in ["name","code","language","superlanguage","family",
                          "collection","source"] if c in doc_stats.columns]
stat_cols = [c for c in ["Pages","Base CER","Fine-tuned CER","CER Improvement",
                          "Base WER","Fine-tuned WER",
                          "Base Char Accuracy","Fine-tuned Char Accuracy"]
             if c in doc_stats.columns]
for _, row in doc_stats.iterrows():
    hash_short = str(row["pdf_hash"])[:16] + "..." if "pdf_hash" in doc_stats.columns else ""
    doc_name = str(row.get("name", hash_short))[:60]
    md.append(f"\n### {doc_name}\n")
    md.append(f"`{hash_short}`\n")
    # metadata table (includes page count)
    meta_rows = [[k, str(row[k])] for k in meta_cols if k in row.index and row[k] is not None]
    meta_rows.append(["Pages", str(row.get("Pages", ""))])
    mdf = pd.DataFrame(meta_rows, columns=["Field", "Value"])
    md.append(mdf.to_markdown(index=False))
    md.append("")
    # stats table: one row, horizontal headers
    scols = ["Base CER","Fine-tuned CER","CER Improvement",
             "Base WER","Fine-tuned WER","Base Char Accuracy","Fine-tuned Char Accuracy"]
    scols = [c for c in scols if c in row.index]
    if scols:
        sdf = pd.DataFrame([{c: row[c] for c in scols}])
        md.append(sdf.to_markdown(index=False))
        md.append("")

with open(REPORT_FILE, "w") as f:
    f.write("\n".join(md))

# ── Update cache with per-doc stats ──────────────────────────────────────────
with open(CACHE_FILE) as f:
    cache_data = json.load(f)
cache_data["_per_document_stats"] = doc_stats.to_dict(orient="records")
with open(CACHE_FILE, "w") as f:
    json.dump(cache_data, f, indent=2, default=str)
print(f"  Per-doc stats saved to {CACHE_FILE}.")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n── Overall ──")
print(f"Base CER: {df['cer_base'].mean():.4f}  Fine-tuned CER: {df['cer_ft'].mean():.4f}  Gain: {df['cer_rel_imp'].mean():.1f}%")
if "family" in all_stats:
    print("\nBy family:")
    print(all_stats["family"][["family","Pages","Base CER","Fine-tuned CER","CER Improvement","Significance"]].to_string(index=False))
print("\nFiles written:")
# List output files
all_outputs = [dim_stats_file(d) for d in DIMENSIONS] + [DOC_STATS_FILE, REPORT_FILE]
for fname in all_outputs:
    if os.path.exists(fname):
        print(f"  {fname}  ({os.path.getsize(fname):,} bytes)")
