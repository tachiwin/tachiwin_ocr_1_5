"""
Tachiwin-OCR-1.5 — Quickstart
Runs the full PaddleOCR-VL pipeline on a document image and prints markdown output.

Usage:
    python examples/quickstart.py path/to/your_document.png

Requirements:
    pip install paddlepaddle-gpu==3.4.1 "paddleocr[doc-parser]==3.4.1"
"""

import sys
from pathlib import Path
from paddleocr import PaddleOCRVL

MODEL = "tachiwin/Tachiwin-OCR-1.5"
MODEL_CACHE = "./tachiwin_model"
OUTPUT_DIR  = "./output"

def run(image_path: str):
    print(f"Loading model: {MODEL}")
    pipeline = PaddleOCRVL(
        vl_rec_model_name=MODEL,
        vl_rec_model_dir=MODEL_CACHE,
    )

    print(f"Running OCR on: {image_path}")
    output = pipeline.predict(image_path)

    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    for res in output:
        res.print()
        res.save_to_markdown(save_path=OUTPUT_DIR)
        res.save_to_json(save_path=OUTPUT_DIR)

    print(f"\nResults saved to: {OUTPUT_DIR}/")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python examples/quickstart.py <image_path>")
        sys.exit(1)
    run(sys.argv[1])
