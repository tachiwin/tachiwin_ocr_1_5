# Tachiwin-OCR-1.5 🦡

**OCR for the Indigenous Languages of Mexico**

A fine-tuned derivative of [PaddleOCR-VL-1.5](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5) specialized in the **68 officially recognized indigenous languages of Mexico** (INALI) and their hundreds of orthographic variants. This is the first OCR model targeting this language family.

> *Tachiwin* (ˈtaʧiwin) — "language" in Totonac (ISO 639-3: `top`)

[![Model on HF](https://img.shields.io/badge/🤗%20Model-Tachiwin--OCR--1.5-purple)](https://huggingface.co/tachiwin/Tachiwin-OCR-1.5)
[![Demo](https://img.shields.io/badge/🤗%20Demo-document--ocr-blue)](https://huggingface.co/spaces/tachiwin/document-ocr)
[![Demo](https://img.shields.io/badge/🤗%20Demo-multilingual--ocr-blue)](https://huggingface.co/spaces/tachiwin/multilingual_ocr)
[![Eval Dataset](https://img.shields.io/badge/🤗%20Dataset-ocr--test--challenging--3-green)](https://huggingface.co/datasets/tachiwin/ocr-test-challenging-3)
[![Training Dataset](https://img.shields.io/badge/🤗%20Dataset-multilingual__ocr__llm__2-green)](https://huggingface.co/datasets/tachiwin/multilingual_ocr_llm_2)
[![License](https://img.shields.io/badge/License-Apache%202.0-orange)](LICENSE)

---

## Why this model exists

Over 7 million people in Mexico speak one of 68 recognized indigenous languages. These languages — Nahuatl, Zapotec, Mixtec, Maya, Totonac, Mazahua, Tzeltal, Yaqui, and dozens more — share a critical challenge: their orthographies systematically use characters and diacritics that are absent from standard OCR training corpora.

Characters like the saltillo (ʼ), schwa (ə), combining tone marks (◌́ ◌̄ ◌̃), and retroflex markers appear constantly in indigenous language text but are virtually never seen by general-purpose OCR models. The result: base OCR models fail catastrophically on these texts, with CER often exceeding 1.0 on character-dense pages.

Tachiwin-OCR-1.5 addresses this gap by fine-tuning PaddleOCR-VL-1.5 on a purpose-built corpus covering all 68 INALI-recognized languages.

---

## Benchmark results

Evaluated on [`tachiwin/ocr-test-challenging-3`](https://huggingface.co/datasets/tachiwin/ocr-test-challenging-3) — **2,000 real PDF-derived pages** with `uncommon_char_score ≥ 0.3` (report date: 2026-07-18). Both models run the **identical PaddleOCR-VL pipeline** (layout detection → OCR → markdown); the only variable is the OCR model weights.

| Metric | Base (PaddleOCR-VL-1.5) | Tachiwin-OCR-1.5 | Improvement |
|:---|:---:|:---:|:---:|
| **CER ↓** | 0.773 | 0.232 | **−70% relative** |
| **WER ↓** | 0.725 | 0.449 | **−38% relative** |
| **Char accuracy ↑** | 61.0% | 77.4% | **+16.4 pp** |
| **Word accuracy ↑** | 44.6% | 56.6% | **+12.0 pp** |

All improvements statistically significant: **Wilcoxon signed-rank test p < 0.0001** (n = 2,000 paired samples).

### CER by difficulty bucket

Each page is assigned an `uncommon_char_score` based on the log-scaled density of indigenous-specific characters (see [`dataset/uncommon_chars.py`](dataset/uncommon_chars.py)). Higher score = greater indigenous character density = harder for a base model. Buckets are computed dynamically from the data range.

| Bucket | n | Base CER | Fine-tuned CER | Reduction |
|:---:|:---:|:---:|:---:|:---:|
| [0.3, 0.4) | 351 | 0.793 | 0.241 | **−70%** |
| [0.4, 0.5) | 316 | 0.833 | 0.235 | **−72%** |
| [0.5, 0.6) | 280 | 1.010 | 0.245 | **−76%** |
| [0.6, 0.7) | 424 | 0.542 | 0.198 | **−63%** |
| [0.7, 0.8) | 260 | 0.433 | 0.190 | **−56%** |
| [0.8, 0.9) | 106 | 0.786 | 0.252 | **−68%** |
| [0.9, 1.0) | 242 | 1.065 | 0.292 | **−73%** |

The base model exceeds CER 1.0 on the hardest buckets — meaning it inserts more characters than the reference contains. The fine-tuned model brings every bucket below 0.30.

**Full report with charts:**
[`evaluation/test_2000/output/evaluation_report.md`](evaluation/test_2000/output/evaluation_report.md)

See also all eval scripts, per-language stats, and chart artifacts in the [`evaluation/`](evaluation/) directory.

---

## Pipeline architecture

PaddleOCR-VL is a **multi-stage pipeline**, not a single model:

```
Page image
    │
    ▼
Layout detection model     ← unchanged (language-agnostic)
    │  (bounding boxes)
    ▼
OCR model (VL)             ← fine-tuned weights (this repo)
    │  (text per crop)
    ▼
Markdown reconstruction    ← unchanged (deterministic algorithm)
    │
    ▼
Full-page markdown output
```

Fine-tuning targets **only the OCR model weights**. The layout detector and markdown renderer are shared and identical between base and fine-tuned runs — so the benchmark comparison is clean and controlled.

---

## Installation

```bash
pip install paddlepaddle-gpu==3.4.1
pip install "paddleocr[doc-parser]==3.4.1"
```

For the evaluation script, additional dependencies:

```bash
pip install vllm==0.11.1 openai jiwer datasets scipy huggingface_hub Pillow tqdm
```

---

## Quickstart

### Option A — PaddleOCR pipeline (recommended, full page)

```python
from paddleocr import PaddleOCRVL

pipeline = PaddleOCRVL(
    vl_rec_model_name="tachiwin/Tachiwin-OCR-1.5",
    vl_rec_model_dir="./tachiwin_model",  # local cache dir
)

output = pipeline.predict("your_document.png")

for res in output:
    res.print()
    res.save_to_markdown(save_path="output/")
    res.save_to_json(save_path="output/")
```

### Option B — Transformers (single crop)

```python
from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoProcessor

MODEL = "tachiwin/Tachiwin-OCR-1.5"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

image = Image.open("crop.png").convert("RGB")
model = AutoModelForCausalLM.from_pretrained(
    MODEL, trust_remote_code=True, torch_dtype=torch.bfloat16
).to(DEVICE).eval()
processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)

messages = [{"role": "user", "content": [
    {"type": "image", "image": image},
    {"type": "text", "text": "OCR:"},
]}]

inputs = processor.apply_chat_template(
    messages, tokenize=True, add_generation_prompt=True,
    return_dict=True, return_tensors="pt"
).to(DEVICE)

outputs = model.generate(**inputs, max_new_tokens=1024, min_new_tokens=1)
print(processor.batch_decode(outputs, skip_special_tokens=True)[0])
```

### Option C — vLLM server

```bash
vllm serve tachiwin/Tachiwin-OCR-1.5
```

See also: [`examples/quickstart.py`](examples/quickstart.py)

---

## Running the evaluation

The evaluation script compares Tachiwin-OCR-1.5 against the PaddleOCR-VL-1.5 base model on the challenging eval dataset.

```bash
python evaluation/tachiwin_ocr_comparison_eval.py
```

**Key parameters** (edit at top of script):

```python
MAX_EVAL_ITEMS = 2000          # set to None to run full 33k dataset
UNCOMMON_CHAR_SCORE_MIN = 0.3  # lower for easier samples, raise for harder
```

The script handles model download, vLLM server launch, evaluation loop, statistical testing, and report generation automatically. Results are written to `evaluation/`.

After obtaining eval JSONs, generate per-language stats and charts:

```bash
cd evaluation
python per_language_stats.py \
  --finetuned test_2000/eval_finetuned.json \
  --base test_2000/eval_base.json \
  --cache test_2000/eval_metadata_cache.json \
  --catalog pdfs_metadata.json \
  --output-dir test_2000/output \
  --run-label "challenging-3-2000"
```

See `python per_language_stats.py --help` for all options.

**Hardware:** The full 33k-row dataset requires significant GPU time. The 2,000-item subset (`MAX_EVAL_ITEMS = 2000`) runs in approximately 4–6 hours on a single A100.

---

## Character set methodology

The 33-character `UNCOMMON_CHARS` set used for difficulty scoring was not selected manually. It was derived through a **corpus-driven lexicostatistical pipeline**:

1. Character frequency distributions were computed from text corpora for each of Mexico's 68 INALI-recognized indigenous languages and their variants
2. Characters already present in Spanish (es-MX) were excluded — Spanish serves as the canonical baseline to minimize disruption to existing OCR performance
3. The differential character sets from all 68 languages were unioned into a single set covering the full orthographic space of the language family

The resulting characters are those that are linguistically significant across the indigenous language family but systematically absent from standard OCR training data. This is precisely why base models fail: these characters are out-of-distribution, not merely rare.

This methodology was originally developed for a keyboard layout optimization algorithm (also open-source) that identifies which characters need to be added to a standard QWERTY layout to support indigenous language input. The OCR project repurposes this linguistic analysis as a principled difficulty metric.

Full derivation: [`dataset/uncommon_chars.py`](dataset/uncommon_chars.py)

---

## Datasets

| Dataset | Size | Description | Access |
|:---|:---:|:---|:---:|
| [`tachiwin/multilingual_ocr_llm_2`](https://huggingface.co/datasets/tachiwin/multilingual_ocr_llm_2) | ~14.5 GB | Training set — instruction-tuned image/text pairs (synthetic layouts, real indigenous language text) | Public |
| [`tachiwin/ocr-test-challenging-3`](https://huggingface.co/datasets/tachiwin/ocr-test-challenging-3) | ~10.5 GB · 33k rows | Eval set — real PDF-derived pages, filtered by indigenous character density | Public |

**Training data note:** Training uses synthetic document layouts (text blocks rendered as images) to maximize volume. Ground truth text is drawn from real indigenous language corpora. The evaluation dataset is constructed exclusively from real PDFs to ensure authentic difficulty and zero training overlap.

**PDF catalog stats:** The [`pdf_catalog_stats.md`](dataset/pdf_catalog_stats.md) and [`pdf_catalog_stats.json`](dataset/pdf_catalog_stats.json) files provide a detailed breakdown of the underlying PDF corpus (1,525 documents) by source institution, collection type, language family, superlanguage, and ISO code — including null/N/A counts for full transparency.

**Rescanned robustness test:** To validate real-world performance, a 200-page subset of the evaluation set (uncommon_char_score ≥ 0.5) was displayed on an LCD screen, photographed freehand with a cellphone camera (108 MP, no tripod), and OCR-processed through the identical pipeline. The fine-tuned model showed no statistically significant degradation vs clean rendered pages (paired t-test p = 0.62, Wilcoxon p = 0.85). Full results in [`evaluation/test_comparison/output/comparison_report.md`](evaluation/test_comparison/output/comparison_report.md).

---

## Repository structure

```
tachiwin_ocr_1_5/
├── README.md
├── LICENSE                          # Apache-2.0
├── report.pdf                       # Training dataset construction report
│
├── training/
│   └── Tachiwin_OCR_PaddleOCR_VL_1_5_Finetuning.ipynb
│
├── evaluation/
│   ├── per_language_stats.py                # Per-language stats, charts, and report
│   ├── compare_rendered_vs_rescanned.py     # Rendered vs rescanned comparison
│   ├── generate_metadata_cache.py           # Build metadata cache from HF dataset
│   ├── pdfs_metadata.json                   # Shared PDF catalog (metadata per pdf_hash)
│   ├── tachiwin_ocr_comparison_eval.py      # Full eval + statistical comparison
│   ├── eval_tachiwin_colab.py               # Colab-adapted eval variant
│   ├── run_modified_eval.py                 # Modified eval runner
│   ├── report_generator/                    # PDF report generator (fonts, logo, script)
│   ├── test_1000/                        # 1,000-page benchmark (uncommon ≥ 0.4)
│   │   ├── eval_base.json
│   │   ├── eval_finetuned.json
│   │   ├── eval_comparison.json
│   │   ├── eval_metadata_cache.json
│   │   └── output/
│   │       ├── evaluation_report.md      # Full report with charts (markdown)
│   │       ├── stats_by_code.csv         # Per-language CER/WER/Acc
│   │       ├── stats_by_document.csv     # Per-document CER/WER/Acc
│   │       ├── stats_by_superlanguage.csv
│   │       ├── stats_by_family.csv
│   │       ├── stats_by_collection.csv
│   │       ├── stats_by_source.csv
│   │       └── charts/                   # 16 PNG charts (see report for links)
│   ├── test_2000/                        # 2,000-page benchmark (uncommon ≥ 0.3)
│   │   ├── eval_base.json
│   │   ├── eval_finetuned.json
│   │   ├── eval_metadata_cache.json
│   │   └── output/
│   │       ├── evaluation_report.md      # Full report with charts (markdown)
│   │       ├── stats_by_code.csv
│   │       ├── stats_by_document.csv
│   │       ├── stats_by_superlanguage.csv
│   │       ├── stats_by_family.csv
│   │       ├── stats_by_collection.csv
│   │       ├── stats_by_source.csv
│   │       └── charts/                   # 16 PNG charts (see report for links)
│   ├── test_rescanned/                   # 200-page rescanned benchmark (uncommon ≥ 0.5)
│   │   ├── eval_base.json
│   │   ├── eval_finetuned.json
│   │   ├── eval_metadata_cache.json
│   │   └── output/
│   │       ├── evaluation_report.md
│   │       └── charts/
│   └── test_comparison/
│       └── output/
│           ├── comparison_report.md      # Rendered vs rescanned analysis
│           └── charts/
│
├── dataset/
│   ├── uncommon_chars.py            # Character set definition + scoring function
│   ├── char_stats.json              # Character frequency statistics
│   ├── layouts.json                 # Layout configuration
│   ├── pdf_catalog_stats.md         # PDF catalog statistics (narrative)
│   └── pdf_catalog_stats.json       # PDF catalog statistics (structured)
│
└── examples/
    └── quickstart.py                # Single image → markdown output
```

---

## Supported languages (sample)

The model covers all 68 INALI-recognized language groups, including:

| ISO | Language | Family |
|:---:|:---|:---|
| `nah` | Nahuatl (multiple variants) | Uto-Aztecan |
| `zap` | Zapotec (multiple variants) | Oto-Manguean |
| `mix` | Mixtec (multiple variants) | Oto-Manguean |
| `myn` | Mayan languages (Yucatec, Tzeltal, Tzotzil...) | Mayan |
| `top` | Totonac | Totonacan |
| `maz` | Central Mazahua | Oto-Manguean |
| `amu` | Amuzgo | Oto-Manguean |
| `sei` | Seri | Isolate |
| `yaq` | Yaqui | Uto-Aztecan |
| `lac` | Lacandon | Mayan |
| `mto` | Totontepec Mixe | Mixe-Zoque |

---

## Fine-tuning details

- **Base model:** `PaddlePaddle/PaddleOCR-VL-1.5`
- **Framework:** [Unsloth](https://github.com/unslothai/unsloth) + TRL (SFT)
- **Method:** Supervised fine-tuning on instruction-tuned image/text pairs
- **Scope:** OCR model weights only; layout detector unchanged
- **Training data:** `tachiwin/multilingual_ocr_llm_2` (~14.5 GB)

See [`training/Tachiwin_OCR_PaddleOCR_VL_1_5_Finetuning.ipynb`](training/Tachiwin_OCR_PaddleOCR_VL_1_5_Finetuning.ipynb) and [`report.pdf`](report.pdf) for full details.

---

## Try it online

| Space | Description |
|:---|:---|
| [tachiwin/document-ocr](https://huggingface.co/spaces/tachiwin/document-ocr) | Upload a full document page — returns clean markdown with layout |
| [tachiwin/multilingual_ocr](https://huggingface.co/spaces/tachiwin/multilingual_ocr) | Multilingual OCR interface |

---

## Citation

If you use this model or dataset in your research, please cite:

```bibtex
@misc{tachiwin-ocr-2025,
  title        = {Tachiwin-OCR-1.5: OCR for the Indigenous Languages of Mexico},
  author       = {Tachiwin},
  year         = {2025},
  howpublished = {\url{https://huggingface.co/tachiwin/Tachiwin-OCR-1.5}},
  note         = {Fine-tuned from PaddlePaddle/PaddleOCR-VL-1.5}
}
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

Model weights inherit the license of the base model (`PaddlePaddle/PaddleOCR-VL-1.5`, Apache 2.0).

---

*Built with ❤️ for linguistic diversity and digital inclusion.*  
*Dedicated to the speakers of Mexico's 68 indigenous languages.*
