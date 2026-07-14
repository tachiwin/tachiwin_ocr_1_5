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

Evaluated on [`tachiwin/ocr-test-challenging-3`](https://huggingface.co/datasets/tachiwin/ocr-test-challenging-3) — 1,000 real PDF-derived pages filtered for indigenous character density (`uncommon_char_score ≥ 0.4`). Both models run the **identical PaddleOCR-VL pipeline** (layout detection → OCR → markdown); the only variable is the OCR model weights.

| Metric | Base (PaddleOCR-VL-1.5) | Tachiwin-OCR-1.5 | Improvement |
|:---|:---:|:---:|:---:|
| **CER ↓** | 0.760 | 0.221 | **−71% relative** |
| **WER ↓** | 0.745 | 0.430 | **−42% relative** |
| **Char accuracy ↑** | 62.7% | 78.7% | **+16.0 pp** |
| **Word accuracy ↑** | 44.4% | 57.7% | **+13.3 pp** |

All improvements statistically significant: **Wilcoxon signed-rank test p < 0.0001** (n = 1,000 paired samples).

### CER by difficulty bucket

Each page is assigned an `uncommon_char_score` based on the log-scaled density of indigenous-specific characters (see [`dataset/uncommon_chars.py`](dataset/uncommon_chars.py)). Higher score = greater indigenous character density = harder for a base model.

| Bucket | n | Base CER | Fine-tuned CER | Reduction |
|:---:|:---:|:---:|:---:|:---:|
| [0.4, 0.5) | 165 | 1.295 | 0.304 | **−77%** |
| [0.5, 0.6) | 173 | 1.346 | 0.273 | **−80%** |
| [0.6, 0.7) | 281 | 0.589 | 0.165 | **−72%** |
| [0.7, 0.8) | 211 | 0.406 | 0.152 | **−63%** |
| [0.8, 0.9) | 45  | 0.370 | 0.256 | **−31%** |
| [0.9, 1.0] | 243 | 0.364 | 0.269 | **−26%** |

The base model exceeds CER 1.0 on the hardest buckets — meaning it inserts more characters than the reference contains. The fine-tuned model brings every bucket below 0.31.

Full detailed results:
---
[`evaluation/results/output/evaluation_report.md`](evaluation/results/output/evaluation_report.md)
---

Please check all artifacts, charts and eval scripts at at [`evaluation/results/`](evaluation/results)

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
MAX_EVAL_ITEMS = 1000          # set to None to run full 33k dataset
UNCOMMON_CHAR_SCORE_MIN = 0.4  # lower for easier samples, raise for harder
```

The script handles model download, vLLM server launch, evaluation loop, statistical testing, and report generation automatically. Results are written to `evaluation/results/`.

**Hardware:** The full 33k-row dataset requires significant GPU time. The 1,000-item subset (`MAX_EVAL_ITEMS = 1000`) runs in approximately 2–3 hours on a single A100.

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
│   ├── tachiwin_ocr_comparison_eval.py   # Full eval + statistical comparison
│   └── results/
│       ├── report_1000.txt          # 1000-item summary report
│       ├── eval_finetuned.json      # Per-item fine-tuned results
│       ├── eval_base.json           # Per-item base model results
│       └── eval_comparison.json     # Paired comparison + statistics
│
├── dataset/
│   ├── uncommon_chars.py            # Character set definition + scoring function
│   ├── char_stats.json              # Character frequency statistics
│   └── layouts.json                 # Layout configuration
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
