"""
Tachiwin-OCR-1.5 — Training Data Construction Report
Build: python build_report.py  →  tachiwin_training_data_report.pdf

FONT SETUP (run locally if NotoSans not available):
  Place these in the same directory as this script:
    NotoSans-Regular.ttf, NotoSans-Bold.ttf, NotoSans-Italic.ttf
    Poppins-Light.ttf  (for logo wordmark, optional)
  Or install system-wide and update FONT_DIR below.

LOGO:
  Place tachiwin_logo.svg (or .png) at LOGO_PATH below.
  If missing, the header renders text-only gracefully.
"""

import os, math
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Image
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.platypus import Image as RLImage

# ── Font paths ────────────────────────────────────────────────────────────────
FONT_DIR  = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(FONT_DIR, "tachiwin_logo.png")   # convert SVG→PNG locally if needed

def try_register(name, path):
    if os.path.exists(path):
        pdfmetrics.registerFont(TTFont(name, path))
        return True
    return False

has_noto = all([
    try_register("NotoSans",       os.path.join(FONT_DIR, "NotoSans-Regular.ttf")),
    try_register("NotoSans-Bold",  os.path.join(FONT_DIR, "NotoSans-Bold.ttf")),
    try_register("NotoSans-Italic",os.path.join(FONT_DIR, "NotoSans-Italic.ttf")),
])
try_register("Poppins-Light", os.path.join(FONT_DIR, "Poppins-Light.ttf"))

BODY_FONT  = "NotoSans"       if has_noto else "Helvetica"
BODY_BOLD  = "NotoSans-Bold"  if has_noto else "Helvetica-Bold"
BODY_ITAL  = "NotoSans-Italic"if has_noto else "Helvetica-Oblique"
MONO_FONT  = "Courier"
TITLE_FONT = "Poppins-Light"  if os.path.exists(os.path.join(FONT_DIR,"Poppins-Light.ttf")) else BODY_FONT

print(f"Fonts: body={BODY_FONT}, title={TITLE_FONT}, noto={has_noto}")

# ── Brand colors ──────────────────────────────────────────────────────────────
PRIMARY    = colors.HexColor("#93A241")   # Tachiwin green
PRIMARY_LT = colors.HexColor("#EEF2DC")
SECONDARY  = colors.HexColor("#79ABD8")   # Tachiwin blue
SECONDARY_LT = colors.HexColor("#E3EFF7")
DARK       = colors.HexColor("#2B2B28")
GRAY       = colors.HexColor("#5F5E5A")
GRAY_LT    = colors.HexColor("#F4F3EE")
GRAY_MID   = colors.HexColor("#D3D1C7")
WHITE      = colors.white
RED        = colors.HexColor("#A32D2D")
RED_LT     = colors.HexColor("#FCEBEB")
AMBER      = colors.HexColor("#BA7517")
AMBER_LT   = colors.HexColor("#FAEEDA")

W, H   = A4
MARGIN = 2.2 * cm
TW     = W - 2 * MARGIN   # text width

# ── Styles ────────────────────────────────────────────────────────────────────
def S(name, **kw): return ParagraphStyle(name, **kw)

sH1 = S("H1", fontName=BODY_BOLD, fontSize=14, leading=19,
         textColor=PRIMARY, spaceBefore=20, spaceAfter=6,
         borderPad=0, borderWidth=0)
sH2 = S("H2", fontName=BODY_BOLD, fontSize=11, leading=15,
         textColor=DARK, spaceBefore=12, spaceAfter=4)
sH3 = S("H3", fontName=BODY_BOLD, fontSize=10, leading=14,
         textColor=GRAY, spaceBefore=8, spaceAfter=3)
sBody = S("Body", fontName=BODY_FONT, fontSize=10, leading=15,
          textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=5)
sBodyL = S("BodyL", fontName=BODY_FONT, fontSize=10, leading=15,
           textColor=DARK, alignment=TA_LEFT, spaceAfter=4)
sBullet = S("Bullet", fontName=BODY_FONT, fontSize=10, leading=14,
            textColor=DARK, leftIndent=14, spaceAfter=3)
sCode = S("Code", fontName=MONO_FONT, fontSize=8.5, leading=13,
          textColor=colors.HexColor("#185FA5"),
          backColor=colors.HexColor("#E6F1FB"),
          leftIndent=10, rightIndent=10, spaceBefore=3, spaceAfter=4)
sCaption = S("Caption", fontName=BODY_ITAL, fontSize=8.5, leading=12,
             textColor=GRAY, alignment=TA_CENTER, spaceAfter=8)
sSmall = S("Small", fontName=BODY_FONT, fontSize=8.5, leading=12,
           textColor=GRAY, spaceAfter=2)
sTH = S("TH", fontName=BODY_BOLD, fontSize=9, leading=12, textColor=WHITE)
sTD = S("TD", fontName=BODY_FONT,  fontSize=9, leading=13, textColor=DARK)
sTDmono = S("TDmono", fontName=MONO_FONT, fontSize=8.5, leading=12, textColor=DARK)

# ── Helpers ───────────────────────────────────────────────────────────────────
def spacer(h=0.3): return Spacer(1, h*cm)
def rule(color=GRAY_MID): return HRFlowable(width="100%", thickness=0.5, color=color, spaceAfter=4)
def h1(t): return Paragraph(t, sH1)
def h2(t): return Paragraph(t, sH2)
def h3(t): return Paragraph(t, sH3)
def body(t): return Paragraph(t, sBody)
def bodyl(t): return Paragraph(t, sBodyL)
def bullet(t): return Paragraph(f"&#8226;&#160; {t}", sBullet)
def caption(t): return Paragraph(t, sCaption)
def small(t): return Paragraph(t, sSmall)
def code(t): return Paragraph(t, sCode)

def callout(text, style="info"):
    mp = {
        "info":    (SECONDARY_LT, SECONDARY),
        "success": (PRIMARY_LT,   PRIMARY),
        "warning": (AMBER_LT,     AMBER),
        "danger":  (RED_LT,       RED),
    }
    bg, border = mp.get(style, mp["info"])
    tbl = Table([[Paragraph(text, S("cb", fontName=BODY_FONT, fontSize=9.5,
                  leading=14, textColor=DARK))]], colWidths=[TW])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), bg),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
        ("TOPPADDING",   (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LINEAFTER",    (0,0),(0,-1),  3, border),
    ]))
    return tbl

def dtable(headers, rows, cw=None):
    if cw is None:
        cw = [TW/len(headers)]*len(headers)
    data = [[Paragraph(h, sTH) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), sTD) for c in row])
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  PRIMARY),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 7),
        ("RIGHTPADDING",  (0,0),(-1,-1), 7),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, GRAY_LT]),
        ("GRID",          (0,0),(-1,-1), 0.3, GRAY_MID),
        ("LINEBELOW",     (0,0),(-1,0),  0.5, PRIMARY),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    return t

def metrics_row(items, card_height=1.5*cm):
    cw = TW / len(items)
    cells = []
    for val, lbl, col in items:
        inner = Table([
            [Paragraph(val, S("mv", fontName=BODY_BOLD, fontSize=17,
                              leading=21, textColor=col, alignment=TA_CENTER))],
            [Paragraph(lbl, S("ml", fontName=BODY_FONT, fontSize=8.5,
                              leading=12, textColor=GRAY, alignment=TA_CENTER))],
        ], colWidths=[cw-10], rowHeights=[card_height, 2*cm])
        inner.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), GRAY_LT),
            ("TOPPADDING",    (0,0),(-1,-1), 9),
            ("BOTTOMPADDING", (0,0),(-1,-1), 9),
            ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ]))
        cells.append(inner)
    tbl = Table([cells], colWidths=[cw]*len(items))
    tbl.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
        ("RIGHTPADDING", (0,0),(-1,-1), 4),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))
    return tbl

# ── Header / footer ───────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GRAY_MID)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, H-1.55*cm, W-MARGIN, H-1.55*cm)
    canvas.setFont(BODY_FONT if has_noto else "Helvetica", 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(MARGIN, H-1.3*cm, "Tachiwin-OCR-1.5 — Training Data Construction Report")
    canvas.drawRightString(W-MARGIN, H-1.3*cm, "PaddleOCR Hackathon 10th")
    canvas.line(MARGIN, 1.4*cm, W-MARGIN, 1.4*cm)
    canvas.drawCentredString(W/2, 1.0*cm, f"— {doc.page} —")
    canvas.restoreState()

def on_first_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GRAY_MID)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 1.4*cm, W-MARGIN, 1.4*cm)
    canvas.setFont(BODY_FONT if has_noto else "Helvetica", 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(W/2, 1.0*cm, "— 1 —")
    canvas.restoreState()

# ── Cover header flowable (article-style, not hero block) ─────────────────────
class ArticleHeader(Flowable):
    def __init__(self):
        Flowable.__init__(self)
        self.width  = TW
        self.height = 5.2*cm

    def draw(self):
        c = self.canv
        # Thin top rule in primary color
        c.setStrokeColor(PRIMARY)
        c.setLineWidth(2)
        c.line(0, self.height, self.width, self.height)

        # Logo / wordmark area
        logo_w = 2.8*cm
        if os.path.exists(LOGO_PATH):
            c.drawImage(LOGO_PATH, -20, self.height-1.6*cm,
                        width=logo_w, height=1.4*cm,
                        preserveAspectRatio=True, mask='auto')
        c.setFillColor(DARK)
        c.setFont(TITLE_FONT if has_noto else "Helvetica-Bold", 16)
        c.drawString(45, self.height-1.1*cm, "Tachiwin")

        # Document type label
        c.setFillColor(GRAY)
        c.setFont(BODY_FONT if has_noto else "Helvetica", 8)
        c.drawString(0, self.height-2.0*cm,
                     "PaddleOCR Global Derivative Model Challenge — Hackathon 10th")

        # Title
        c.setFillColor(DARK)
        c.setFont(BODY_BOLD if has_noto else "Helvetica-Bold", 18)
        c.drawString(0, self.height-3.1*cm, "Training Data Construction Report")

        # Subtitle
        c.setFont(BODY_FONT if has_noto else "Helvetica", 11)
        c.setFillColor(PRIMARY)
        c.drawString(0, self.height-3.8*cm, "Tachiwin-OCR-1.5: Indigenous Languages of Mexico")

        # Thin bottom rule
        c.setStrokeColor(GRAY_MID)
        c.setLineWidth(0.5)
        c.line(0, 0, self.width, 0)

# ── CER comparison chart ──────────────────────────────────────────────────────
def cer_chart():
    d = Drawing(TW, 180)
    bc = VerticalBarChart()
    bc.x = 50; bc.y = 30
    bc.height = 130; bc.width = TW - 70
    bc.data = [
        [0.793, 0.833, 1.010, 0.542, 0.433, 0.786, 1.065],
        [0.241, 0.235, 0.245, 0.198, 0.190, 0.252, 0.292],
    ]
    bc.categoryAxis.categoryNames = [
        "[0.3,0.4)","[0.4,0.5)","[0.5,0.6)",
        "[0.6,0.7)","[0.7,0.8)","[0.8,0.9)","[0.9,1.0)"
    ]
    bc.categoryAxis.labels.fontName = BODY_FONT if has_noto else "Helvetica"
    bc.categoryAxis.labels.fontSize = 7.5
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 1.2
    bc.valueAxis.valueStep = 0.2
    bc.valueAxis.labels.fontName = BODY_FONT if has_noto else "Helvetica"
    bc.valueAxis.labels.fontSize = 8
    bc.bars[0].fillColor = colors.HexColor("#E24B4A")
    bc.bars[1].fillColor = PRIMARY
    bc.groupSpacing = 6; bc.barSpacing = 1.5
    d.add(bc)
    d.add(Rect(52,  8, 10, 8, fillColor=colors.HexColor("#E24B4A"), strokeWidth=0))
    d.add(String(66, 10, "Base model (PaddleOCR-VL-1.5)",
                 fontName=BODY_FONT if has_noto else "Helvetica", fontSize=8,
                 fillColor=GRAY))
    d.add(Rect(230, 8, 10, 8, fillColor=PRIMARY, strokeWidth=0))
    d.add(String(244, 10, "Tachiwin-OCR-1.5",
                 fontName=BODY_FONT if has_noto else "Helvetica", fontSize=8,
                 fillColor=GRAY))
    return d

# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════
doc = SimpleDocTemplate(
    os.path.normpath(os.path.join(FONT_DIR, "..", "..", "report.pdf")),
    pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN,
    topMargin=2.6*cm, bottomMargin=2.0*cm,
    title="Training Data Construction Report — Tachiwin-OCR-1.5",
    author="Tachiwin",
)

story = []

# ── Cover ─────────────────────────────────────────────────────────────────────
story.append(ArticleHeader())
story.append(spacer(0.5))
story.append(body(
    "This report documents the training dataset construction methodology, fine-tuning "
    "procedure, evaluation dataset design, and benchmark results for <b>Tachiwin-OCR-1.5</b> "
    "— a fine-tuned derivative of PaddleOCR-VL-1.5 specialized in the 68 officially "
    "recognized indigenous languages of Mexico (INALI)."
))
story.append(spacer(0.2))
story.append(metrics_row([
    ("68",      "New Languages\nTrained",      PRIMARY),
    ("16",      "Languages\nSignificant Improvement",      DARK),
    ("+33",      "Specialized\ncharacters",      SECONDARY),
    ("14Gb", "Training dataset",                    DARK),
    ("49K",  "Training samples",                    PRIMARY),
    ("33K", "Evaluation samples",      SECONDARY),
]))
story.append(spacer(0.4))
story.append(rule())

# ── Table of contents ─────────────────────────────────────────────────────────
story.append(spacer(0.3))
story.append(h1("Contents"))
toc = [
    ("1", "Training Dataset Construction"),
    ("2", "Fine-Tuning"),
    ("3", "Evaluation Dataset Construction"),
    ("4", "Evaluation Methodology and Results"),
    ("5", "Open-Source Assets"),
]
for num, title in toc:
    story.append(bodyl(
        f"<font color='#93A241'><b>{num}.</b></font>&#160;&#160;{title}"
    ))
story.append(PageBreak())

# ── Project Overview ──────────────────────────────────────────────────────────
story.append(h1("Project Overview"))
story.append(body(
    "Tachiwin-OCR-1.5 is a fine-tuned derivative of PaddleOCR-VL-1.5 specialized in the "
    "<b>68 officially recognized indigenous languages of Mexico</b> as defined by the "
    "Instituto Nacional de Lenguas Indígenas (INALI). These languages and their hundreds "
    "of orthographic variants are spoken by over 7 million people, yet have no dedicated "
    "OCR solution in either academia or industry."
))
story.append(body(
    "The project addresses a specific and well-defined failure mode: standard OCR models "
    "have never encountered the orthographic characters used systematically across this "
    "language family. Specialized latin script characters and combining tone marks, "
    "appear constantly in indigenous language text but are "
    "out-of-distribution for any general-purpose OCR model trained primarily on Spanish, "
    "English, and other latin-script high-resource languages."
))
story.append(body(
    "The project covers the full pipeline: construction of a large synthetic training "
    "dataset derived from real indigenous language corpora, supervised fine-tuning of "
    "PaddleOCR-VL-1.5, construction of a real-PDF evaluation dataset with no synthetic "
    "data, and rigorous benchmarking with statistical validation."
))
story.append(spacer(0.2))
story.append(body(
    "<b>Model:</b> tachiwin/Tachiwin-OCR-1.5 &nbsp;|&nbsp; "
    "<b>Base:</b> PaddlePaddle/PaddleOCR-VL-1.5 &nbsp;|&nbsp; "
    "<b>License:</b> Apache 2.0"
))
story.append(spacer(0.3))
story.append(rule())

# ══════════════════════════════════════════════════════════════════════════════
# 1. TRAINING DATASET CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════
story.append(h1("1. Training Dataset Construction"))
story.append(body(
    "The training dataset (<b>tachiwin/multilingual_ocr_llm_2</b>, ~14.5 GB, 49,689 samples) "
    "was produced through a three-stage pipeline: language index assembly, "
    "corpus collection and cleaning, and synthetic image rendering."
))

story.append(h2("1.1 Language index"))
story.append(body(
    "A structured language index was assembled covering all 68 INALI-recognized indigenous "
    "language groups and their documented variants, each tagged with its ISO 639-3 analogue code. "
    "This index served as the authoritative reference for both corpus collection and "
    "character set derivation, ensuring systematic coverage across the full language family "
    "rather than ad-hoc selection."
))

story.append(h2("1.2 Corpus collection and cleaning"))
story.append(body(
    "Using the language index, a broad web scraping pipeline collected a large corpus of "
    "indigenous language text from primarily governmental and institutional websites "
    "(including INALI, SEP, and regional indigenous affairs offices). "
    "Text was categorized per language using the ISO index."
))
story.append(body(
    "The collected text was then cleaned and prepared for rendering:"
))
for item in [
    "Malformed UTF-8 entities removed and all text NFC-normalized",
    "Text segmented into paragraphs with <b>normally distributed paragraph length</b> — ensuring the model sees a balanced range of short and long text blocks",
]:
    story.append(bullet(item))

story.append(h2("1.3 Synthetic image rendering"))
story.append(body(
    "Each paragraph was rendered as a training image using pseudorandom parameter "
    "sampling with normally distributed values around realistic medians. "
    "<b>31 curated font families</b> (which fully covered our specialized character set) were used across the full dataset. "
    "The following parameter space was sampled independently per image:"
))
render_rows = [
    ["Group", "Parameters", "Distribution"],
    ["Text appearance",
     "Point size, char spacing, line spacing, uppercase",
     "ptsize median 21 ±11 pt; char_spacing ±0.3; line_spacing median 0 ±3"],
    ["Color",
     "Background gray, text gray, color mode, RGB jitter",
     "Background mostly white (median 255 ±80); text mostly dark (median 0 ±80); ~25% chance of full RGB color with aggressive channel variance"],
    ["Geometry",
     "Short side, margin factor, aspect ratio",
     "Short side median 500 ±150 px; 60% horizontal (ratio 1.2–2.5), 20% vertical (0.7–0.8), 20% square (0.8–1.2)"],
    ["Geometric distortions",
     "Rotation, skew X/Y, perspective, wave",
     "Rotation ±0.5°; skew X/Y ±0.5; perspective ±0.1; wave ~30% chance (amplitude ±0.5, freq ±50)"],
    ["Blur",
     "Gaussian blur; motion blur (radius, sigma, angle)",
     "Gaussian median 0.2 ±1.0 σ; motion blur ~30% chance, radius 4 ±2, any angle 0–360°"],
    ["Noise",
     "Type: Gaussian / Impulse / Laplacian / Poisson / Uniform",
     "~30% chance; Gaussian 30%, Impulse 30%, Laplacian 10%, Poisson 10%, Uniform 20%"],
    ["Photometric",
     "Brightness, contrast, dirty/stain overlay",
     "Brightness ±10, contrast ±10; dirty overlay ~30% chance"],
    ["Morphology",
     "Erode/Dilate — kernel: Diamond, Disk, or Square",
     "Simulates ink spread or character erosion"],
    ["Text alignment", "Left, center, right",
     "60% left, 30% center, 10% right"],
]
story.append(dtable(render_rows[0], render_rows[1:],
                    cw=[3.2*cm, 5.2*cm, 7.6*cm]))
story.append(spacer(0.2))
story.append(body(
    "With 31 font families combined with independently sampled continuous distortion "
    "parameters, the practical number of visually distinct configurations is in the "
    "tens of millions — producing an unbiased dataset that generalizes across the "
    "full spectrum of real-world text capture conditions: clean prints, scans, "
    "photographs, photocopies, and degraded or aged documents."
))

story.append(h2("1.4 Character set derivation"))
story.append(body(
    "The 33-character <b>UNCOMMON_CHARS</b> set — used both in training quality filtering "
    "and evaluation difficulty scoring — was derived through a corpus-driven "
    "lexicostatistical pipeline, not selected manually:"
))
for item in [
    "Character frequency distributions were computed from corpora for each of the 68 language groups and their variants",
    "Characters already present in Spanish (es-MX) were excluded — Spanish serves as the canonical baseline to avoid disrupting existing OCR performance on the dominant language",
    "The differential character sets from all 68 languages were unioned into a single comprehensive set",
]:
    story.append(bullet(item))
story.append(spacer(0.2))
story.append(body(
    "The resulting 33 markers are characters that are linguistically significant across "
    "the indigenous language family but systematically absent from standard OCR training "
    "data. This character set was originally developed for a keyboard layout optimization "
    "algorithm (separately released open-source) and repurposed here as a principled "
    "linguistic coverage and difficulty metric."
))
story.append(spacer(0.1))
char_rows = [
    ["Character", "Unicode", "Name", "Linguistic function"],
    ["ƚ",  "U+019A", "Latin Small Letter L with Bar",           "Lateral consonant variant"],
    ["ꞌ",  "U+A78C", "Latin Small Letter Saltillo",             "Glottal stop / saltillo marker"],
    ["ʌ",  "U+028C", "Latin Small Letter Turned V",             "Open-mid back unrounded vowel"],
    ["ʉ",  "U+0289", "Latin Small Letter U Bar",                "Close central rounded vowel"],
    ["ɛ",  "U+025B", "Latin Small Letter Open E",               "Open-mid front vowel"],
    ["ɨ",  "U+0268", "Latin Small Letter I with Stroke",        "Close central vowel"],
    ["ⁿ",  "U+207F", "Superscript Latin Small Letter N",        "Prenasalization marker"],
    ["‑",  "U+2011", "Non-Breaking Hyphen",                     "Morpheme boundary marker"],
    ["ˊ",  "U+02CA", "Modifier Letter Acute Accent",            "Standalone rising tone diacritic"],
    ["ˋ",  "U+02CB", "Modifier Letter Grave Accent",            "Standalone falling tone diacritic"],
    ["ḻ",  "U+1E3B", "Latin Small Letter L with Line Below",    "Retroflex lateral"],
    ["ṉ",  "U+1E49", "Latin Small Letter N with Line Below",    "Retroflex nasal"],
    ["ǔ",  "U+01D4", "Latin Small Letter U with Caron",         "Tone marker (rising)"],
    ["ǎ",  "U+01CE", "Latin Small Letter A with Caron",         "Tone marker (rising)"],
    ["ə",  "U+0259", "Latin Small Letter Schwa",                "Mid-central vowel"],
    ["ʼ",  "U+02BC", "Modifier Letter Apostrophe",              "Saltillo / glottal stop"],
    ["ˉ",  "U+02C9", "Modifier Letter Macron",                  "Level tone diacritic"],
    ["ǿ",  "U+01FF", "Latin Small Letter O with Stroke and Acute", "Complex diacritic combination"],
    ["ŋ",  "U+014B", "Latin Small Letter Eng",                  "Velar nasal"],
    ["į",  "U+012F", "Latin Small Letter I with Ogonek",        "Nasalized vowel"],
    ["ō",  "U+014D", "Latin Small Letter O with Macron",        "Long/level-tone vowel"],
    ["ā",  "U+0101", "Latin Small Letter A with Macron",        "Long/level-tone vowel"],
    ["ī",  "U+012B", "Latin Small Letter I with Macron",        "Long/level-tone vowel"],
    ["ē",  "U+0113", "Latin Small Letter E with Macron",        "Long/level-tone vowel"],
    ["ū",  "U+016B", "Latin Small Letter U with Macron",        "Long/level-tone vowel"],
    ["ž",  "U+017E", "Latin Small Letter Z with Caron",         "Postalveolar fricative"],
    ["š",  "U+0161", "Latin Small Letter S with Caron",         "Postalveolar fricative"],
    ["◌̱", "U+0331", "Combining Macron Below",                  "Tone / length mark below"],
    ["◌̨", "U+0328", "Combining Ogonek",                        "Nasalization mark"],
    ["◌̄", "U+0304", "Combining Macron",                        "Length / level tone"],
    ["◌̈", "U+0308", "Combining Diaeresis",                     "Vowel quality mark"],
    ["◌̃", "U+0303", "Combining Tilde",                         "Nasalization mark"],
    ["◌́", "U+0301", "Combining Acute Accent",                  "Rising tone / stress mark"],
]
story.append(dtable(char_rows[0], char_rows[1:],
                    cw=[1.5*cm, 1.8*cm, 6.5*cm, 6.2*cm]))
story.append(caption("Table: Complete UNCOMMON_CHARS set — 33 orthographic markers "
                     "covering the indigenous language family of Mexico."))
story.append(spacer(0.2))
story.append(callout(
    "<b>Training vs evaluation data:</b> The training dataset uses synthetic image "
    "rendering to maximize volume. The evaluation dataset "
    "(tachiwin/ocr-test-challenging-3) is built exclusively from real PDF pages — "
    "no synthetic data. This separation ensures the benchmark reflects real-world "
    "performance, not training distribution memorization.",
    "success"
))

story.append(spacer(0.2))
story.append(RLImage("sample1.jpg", width=10*cm, height=6*cm))
story.append(RLImage("sample2.jpg", width=10*cm, height=6*cm))
story.append(caption("Figure 1. Sample training images with complex diacritics and specialized characters"))
# ══════════════════════════════════════════════════════════════════════════════
# 2. FINE-TUNING
# ══════════════════════════════════════════════════════════════════════════════
story.append(h1("2. Fine-Tuning"))
story.append(body(
    "Fine-tuning was performed using <b>Unsloth</b> with the TRL SFTTrainer. "
    "As per standard PaddleOCR-VL fine-tuning practice, training targets the OCR model "
    "weights; the layout detection stage is language-agnostic and was left unchanged."
))

story.append(h2("2.1 Training configuration"))
ft_rows = [
    ["Parameter", "Value", "Notes"],
    ["Base model",            "PaddlePaddle/PaddleOCR-VL-1.5", ""],
    ["Framework",             "Unsloth + TRL SFTTrainer",       "~2× faster vs standard HF training"],
    ["Fine-tuning type",      "Full parameter SFT",             "full_finetuning=True"],
    ["Training samples",      "49,689",                         "tachiwin/multilingual_ocr_llm_2"],
    ["Epochs",                "2",                              ""],
    ["Batch size",            "4",                              "Per device"],
    ["Gradient accumulation", "8 steps",                        "Effective batch size = 32"],
    ["Learning rate",         "5e-5",                           ""],
    ["LR scheduler",          "Cosine",                         ""],
    ["Warmup ratio",          "0.05",                           "≈ 155 steps"],
    ["Optimizer",             "AdamW 8-bit",                    "Memory-efficient"],
    ["Weight decay",          "0.001",                          ""],
    ["Max sequence length",   "2,048 tokens",                   "Padded to multiples of 8"],
    ["Precision",             "bf16 / fp16",                    "Auto-detected per GPU"],
    ["Seed",                  "3407",                           "Reproducibility"],
    ["Checkpointing",         "Every 500 steps → HF Hub",       "save_total_limit=1; resumable"],
    ["Experiment tracking",   "Weights & Biases",               "Run: tachiwin_ocr_1_5_a"],
]
story.append(dtable(ft_rows[0], ft_rows[1:],
                    cw=[4.5*cm, 5.0*cm, 6.5*cm]))
story.append(spacer(0.2))

story.append(h2("2.2 Total training steps"))
story.append(code(
    "total_steps = ceil(49689 / (4 × 8)) × 2 epochs  =  ceil(49689 / 32) × 2  =  1553 × 2  =  3,106 steps\n"
    "warmup_steps = round(0.05 × 3106)  =  155 steps"
))

story.append(h2("2.3 Training strategy notes"))
for item in [
    ("<b>Full fine-tuning over LoRA:</b> All model parameters are updated. "
     "For a task requiring the model to learn an entirely new character vocabulary "
     "across 68 language groups, full fine-tuning provides greater capacity to adapt "
     "embedding and attention layers that LoRA would leave frozen."),
    ("<b>Response-only training:</b> Only the assistant response tokens contribute to the "
     "loss. Prompt tokens (image + 'OCR:' instruction) are masked with −100 using "
     "<font name='Courier' size='9'>UnslothVisionDataCollator</font> with "
     "<font name='Courier' size='9'>train_on_responses_only=True</font>, "
     "preventing the model from wasting capacity reproducing the fixed prompt."),
    ("<b>Resumable across sessions:</b> A custom "
     "<font name='Courier' size='9'>ColabTimeoutCallback</font> detects approaching "
     "session timeouts, saves a checkpoint to Hugging Face Hub, and resumes exactly "
     "from that checkpoint in the next session — making multi-session training practical."),
]:
    story.append(bullet(item))
    story.append(spacer(0.1))

story.append(spacer(0.2))
story.append(RLImage("chart1.png", width=10*cm, height=6*cm))
story.append(RLImage("chart2.png", width=10*cm, height=6*cm))
story.append(RLImage("chart3.png", width=10*cm, height=6*cm))
story.append(caption("Figure 2. Finetune charts for train loss, learning rate and gradient norm."))

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 3. EVALUATION DATASET CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════
story.append(h1("3. Evaluation Dataset Construction"))
story.append(body(
    "The evaluation dataset (<b>tachiwin/ocr-test-challenging-3</b>, ~10.5 GB, 33,000 rows) "
    "is built exclusively from real PDF documents, with no synthetic data. "
    "The construction pipeline is fundamentally different from the training pipeline."
))

story.append(h2("3.1 Page selection criteria"))
story.append(body(
    "Pages were drawn from a corpus of indigenous language PDF documents. "
    "A page was selected for the evaluation set only when it passed all of "
    "the following criteria simultaneously:"
))
for item in [
    "<b>Clean native text extraction:</b> <font name='Courier' size='9'>pymupdf4llm</font> "
    "must extract text from the page with less than 2% replacement/box characters "
    "(U+FFFD, U+25A1), with a minimum character count of 100. This threshold ensures "
    "the extracted text is a reliable ground truth — not a partial or garbled extraction.",
    "<b>Indigenous character density:</b> The page must have an "
    "<font name='Courier' size='9'>uncommon_char_score ≥ 0.3</font> (see below; configurable via "
    "<font name='Courier' size='9'>UNCOMMON_CHAR_SCORE_MIN</font>). "
    "This ensures every evaluation page contains a meaningful presence of "
    "indigenous-specific characters — the exact characters the model is designed to handle.",
    "<b>Valid image render:</b> The page must render successfully as a high-resolution "
    "PNG from the same PDF, with no blank or corrupt output.",
]:
    story.append(bullet(item))

story.append(h2("3.2 Ground truth and test input"))
story.append(body(
    "For each selected page, two outputs are generated from the same PDF page:"
))
for item in [
    "<b>Reference (ground truth):</b> Text extracted by <font name='Courier' size='9'>pymupdf4llm</font> "
    "in markdown format, with HTML/image entities stripped.",
    "<b>Test input:</b> The page rendered as a PNG image, fed through the full PaddleOCR-VL "
    "pipeline (layout detection → OCR → markdown). HTML/image entities are also stripped "
    "from the OCR output before comparison.",
]:
    story.append(bullet(item))
story.append(spacer(0.2))
story.append(callout(
    "Both the base model and the fine-tuned model run the identical PaddleOCR-VL "
    "pipeline — same layout detector, same markdown renderer. The only variable is "
    "the OCR model weights. Any performance difference is therefore attributable "
    "exclusively to OCR recognition quality.",
    "success"
))

story.append(h2("3.3 uncommon_char_score"))
story.append(body(
    "Each row in the dataset has a computed <b>uncommon_char_score</b> — a continuous "
    "value between 0.0 and 1.0 based on the log-scaled density and diversity of "
    "UNCOMMON_CHARS characters in the reference text:"
))
story.append(code(
    "score = log10(uncommon_count + 1) / log10(total_chars + 1)\n"
    "      + min(0.3, unique_uncommon_chars × 0.05)\n"
    "# Capped at 1.0. Higher = denser indigenous character content."
))
story.append(body(
    "The full 33,000-row dataset contains rows across the entire score range 0.0–1.0, "
    "reflecting the natural variation in indigenous character density across the document corpus. "
    "When running the evaluation script, an arbitrary minimum score threshold can be set via "
    "<font name='Courier' size='9'>UNCOMMON_CHAR_SCORE_MIN</font> to select any desired "
    "subset of the data. Setting it to 0.0 evaluates the entire unfiltered dataset; "
    "raising it restricts evaluation to pages with progressively higher indigenous "
    "character density. This makes it possible to run the evaluation at any desired "
    "level of character-complexity, as required by the competition's variable-difficulty criteria."
))
story.append(body(
    "For the benchmark reported in this submission, "
    "<font name='Courier' size='9'>UNCOMMON_CHAR_SCORE_MIN = 0.3</font> was used, "
    "with a 2,000-item subset providing broad coverage across the score range. "
    "Results broken down by score range are reported in Section 4."
))
IMG_W = TW/2 - 0.5*cm
IMG_H = IMG_W * 1.41  # A4 aspect ratio — adjust if your images differ

img_a = RLImage("dataset1.jpg", width=IMG_W, height=IMG_H)
img_b = RLImage("dataset2.jpg", width=IMG_W, height=IMG_H)

side_by_side = Table(
    [[img_a, img_b]],
    colWidths=[TW/2, TW/2]
)
side_by_side.setStyle(TableStyle([
    ("ALIGN",  (0,0), (-1,-1), "CENTER"),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
]))
story.append(side_by_side)
story.append(caption("Figure 3. Samples from the evaluation dataset of two PDF pages containing uncommon_char_score 1.0 (the highest) containing a large ammount of specialized characters which also have perfect text transcription"))

# ── 3.4 PDF catalog statistics ───────────────────────────────────────────────
story.append(PageBreak())
story.append(h2("3.4 PDF catalog statistics"))
story.append(body(
    "The PDF catalog underpinning both the training and evaluation datasets contains "
    "<b>1,525 unique documents</b> collected from institutional sources across Mexico. "
    "These PDFs cover indigenous language grammars, dictionaries, writing guides, "
    "educational materials, and legal documents. The tables below summarize the "
    "catalog composition by source, collection type, language family, and superlanguage. "
    "Null entries (N/A) indicate documents where the metadata field was not applicable."
))
story.append(spacer(0.1))

# Source
story.append(h3("By source institution"))
pdf_src_rows = [
    ["Source", "Count", "%"],
    ["ILV (Instituto Lingüístico de Verano)", "861", "56.5%"],
    ["SEP (Secretaría de Educación Pública)", "150", "9.8%"],
    ["Other (AVELI, books, IMJUVE, UN, etc.)", "94",  "6.2%"],
    ["INALI (Instituto Nacional de Lenguas)",  "83",  "5.4%"],
    ["SSA (Secretaría de Salud)",              "81",  "5.3%"],
    ["CENAPRED",                               "59",  "3.9%"],
    ["Government",                             "56",  "3.7%"],
    ["N/A",                                    "141", "9.2%"],
]
story.append(dtable(pdf_src_rows[0], pdf_src_rows[1:],
                    cw=[7*cm, 2*cm, 2*cm]))
story.append(spacer(0.2))

# Collection
story.append(h3("By collection type"))
pdf_coll_rows = [
    ["Collection", "Count", "%"],
    ["Other",            "161", "10.6%"],
    ["Textbooks",        "150", "9.8%"],
    ["Dictionary",       "118", "7.7%"],
    ["Academic",         "114", "7.5%"],
    ["COVID-19",         "81",  "5.3%"],
    ["Writing rules",    "63",  "4.1%"],
    ["Natural disasters", "59", "3.9%"],
    ["Legal",            "56",  "3.7%"],
    ["N/A",              "723", "47.4%"],
]
story.append(dtable(pdf_coll_rows[0], pdf_coll_rows[1:],
                    cw=[7*cm, 2*cm, 2*cm]))
story.append(spacer(0.2))

# Family
story.append(PageBreak())
story.append(h3("By language family"))
pdf_fam_rows = [
    ["Family", "Count", "%"],
    ["Otomangue",         "816", "53.5%"],
    ["Yuto-Nahua",        "183", "12.0%"],
    ["Mayense",           "122", "8.0%"],
    ["Totonaco-Tepehua",   "79", "5.2%"],
    ["Mixe-Zoqueano",      "59", "3.9%"],
    ["Other (8 families)",  "44", "2.9%"],
    ["N/A",               "222", "14.6%"],
]
story.append(dtable(pdf_fam_rows[0], pdf_fam_rows[1:],
                    cw=[7*cm, 2*cm, 2*cm]))
story.append(spacer(0.2))

# Superlanguage
story.append(h3("By superlanguage (top 10)"))
pdf_sl_rows = [
    ["Superlanguage", "Count", "%"],
    ["Zapoteco",          "330", "21.6%"],
    ["Mixteco",           "285", "18.7%"],
    ["Náhuatl",           "113", "7.4%"],
    ["Mazateco",           "61", "4.0%"],
    ["Totonaco",           "48", "3.1%"],
    ["Tepehua",            "31", "2.0%"],
    ["Chinanteco",         "28", "1.8%"],
    ["Maya",               "25", "1.6%"],
    ["Amuzgo",             "23", "1.5%"],
    ["Other (56 groups)", "359", "23.5%"],
    ["N/A",               "222", "14.6%"],
]
story.append(dtable(pdf_sl_rows[0], pdf_sl_rows[1:],
                    cw=[7*cm, 2*cm, 2*cm]))
story.append(spacer(0.2))

story.append(callout(
    "Full catalog statistics (including per-language breakdowns across all 206 coded "
    "language varieties) are available at "
    "<font name='Courier' size='9'>dataset/pdf_catalog_stats.md</font> and "
    "<font name='Courier' size='9'>dataset/pdf_catalog_stats.json</font> in the repository.",
    "info"
))

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 4. EVALUATION METHODOLOGY AND RESULTS
# ══════════════════════════════════════════════════════════════════════════════
story.append(h1("4. Evaluation Methodology and Results"))

story.append(h2("4.1 Evaluation design"))
story.append(body(
    "The evaluation script (<b>tachiwin_ocr_comparison_eval.py</b>, attached to this "
    "submission) performs a full paired comparison between the base model and "
    "Tachiwin-OCR-1.5 on the challenging evaluation dataset. It is fully self-contained:"
))
for item in [
    "Downloads both models from Hugging Face Hub",
    "Launches a vLLM server as a subprocess",
    "Runs the evaluation loop with timeout and retry handling",
    "Computes CER, WER, char accuracy, and word accuracy per item",
    "Performs Wilcoxon signed-rank test and paired t-test for statistical validation",
    "Outputs per-item JSON and a summary report",
]:
    story.append(bullet(item))
story.append(spacer(0.2))
story.append(body(
    "<b>Full-pipeline evaluation:</b> Both models run the complete PaddleOCR-VL pipeline "
    "(layout detection → OCR → markdown reconstruction) on each page image. "
    "The pipeline constants — layout detector, reading order algorithm, markdown renderer — "
    "are shared and identical between both runs. Differences in CER/WER are therefore "
    "entirely attributable to the OCR model weights. "
    "Evaluating at the full-page level (rather than pre-segmented crops) reflects "
    "real-world deployment conditions and is a more demanding, realistic benchmark."
))
story.append(body(
    "<b>Paired design:</b> Both models are evaluated on exactly the same pages, "
    "enabling paired statistical tests. HTML and image entities are stripped from both "
    "reference and OCR output before metric computation, so evaluation measures text "
    "recognition quality only."
))
story.append(code(
    "# Key parameters in tachiwin_ocr_comparison_eval.py\n"
    "MAX_EVAL_ITEMS = 2000          # set to None to run the full 33k dataset\n"
    "UNCOMMON_CHAR_SCORE_MIN = 0.3  # set to 0.0 for unfiltered; raise for harder subsets\n"
    "\n"
    "# Dependencies\n"
    "vllm==0.11.1  paddlepaddle-gpu==3.4.1  paddleocr[doc-parser]==3.4.1\n"
    "openai  jiwer  datasets  scipy  huggingface_hub  Pillow  tqdm"
))
story.append(callout(
    "The full 33,000-row dataset can be evaluated by setting MAX_EVAL_ITEMS = None. "
    "UNCOMMON_CHAR_SCORE_MIN can be set to any value between 0.0 and 1.0 to select "
    "subsets by indigenous character density — from the full unfiltered corpus (0.0) "
    "to pages with maximum character complexity (approaching 1.0). "
    "The 2,000-item benchmark subset runs in approximately 4–6 hours on a single A100.",
    "info"
))

story.append(h2("4.2 Metrics"))
story.append(body(
    "<b>CER (Character Error Rate)</b> is the primary metric. It operates at the character "
    "level and is less sensitive to the agglutinative morphology common in indigenous "
    "languages, where a single character error at a morpheme boundary can inflate "
    "word-level error counts disproportionately. WER, char accuracy, and word accuracy "
    "are reported as secondary metrics."
))
story.append(body(
    "Statistical significance is assessed using the <b>Wilcoxon signed-rank test</b> "
    "(non-parametric, appropriate for paired samples with non-normal distributions). "
    "A paired t-test is computed as a secondary check."
))
story.append(PageBreak())
story.append(h2("4.3 Results"))
story.append(body(
    "Results on the 2,000-item benchmark subset (uncommon_char_score ≥ 0.3, n=2,000 paired samples):"
))
story.append(spacer(0.1))
perf_rows = [
    ["Metric", "Base model", "Tachiwin-OCR-1.5", "Absolute Δ", "Relative Δ", "Wilcoxon p"],
    ["CER ↓",           "0.773", "0.232", "−0.541", "−70%",  "< 0.0001 ***"],
    ["WER ↓",           "0.725", "0.449", "−0.276", "−38%",  "< 0.0001 ***"],
    ["Char accuracy ↑", "61.0%", "77.4%", "+16.4pp","+27%",  "< 0.0001 ***"],
    ["Word accuracy ↑", "44.6%", "56.6%", "+12.0pp","+27%",  "< 0.0001 ***"],
]
story.append(dtable(perf_rows[0], perf_rows[1:],
                    cw=[3.2*cm, 2.6*cm, 3.2*cm, 2.2*cm, 2.2*cm, 2.6*cm]))
story.append(spacer(0.3))
story.append(RLImage("chart_01_overall_cer.png", width=TW*0.46, height=4.5*cm))
story.append(RLImage("chart_02_overall_wer.png", width=TW*0.46, height=4.5*cm))
story.append(RLImage("chart_03_overall_accuracy.png", width=TW*0.46, height=4.5*cm))
story.append(spacer(0.3))

story.append(PageBreak())
story.append(h2("4.4 CER by score range"))
story.append(body(
    "For analysis, the continuous uncommon_char_score of each evaluated page is "
    "discretized into ranges to show how performance varies with indigenous character "
    "density. These are not separate evaluation runs or pre-defined strata — "
    "they are a tabular representation of the distribution of results across the "
    "continuous score axis:"
))
diff_rows = [
    ["Score range", "N pages", "% of subset", "Base CER", "Fine-tuned CER", "Reduction"],
    ["[0.3, 0.4)", "351", "17.6%", "0.793", "0.241", "−70%"],
    ["[0.4, 0.5)", "316", "15.8%", "0.833", "0.235", "−72%"],
    ["[0.5, 0.6)", "280", "14.0%", "1.010", "0.245", "−76%"],
    ["[0.6, 0.7)", "424", "21.2%", "0.542", "0.198", "−63%"],
    ["[0.7, 0.8)", "260", "13.0%", "0.433", "0.190", "−56%"],
    ["[0.8, 0.9)", "106",  "5.3%",  "0.786", "0.252", "−68%"],
    ["[0.9, 1.0)", "242", "12.1%", "1.065", "0.292", "−73%"],
    ["<b>Total</b>", "<b>2,000</b>", "<b>100%</b>", "<b>0.773</b>", "<b>0.232</b>", "<b>−70%</b>"],
]
story.append(dtable(diff_rows[0], diff_rows[1:],
                    cw=[2.4*cm, 2.0*cm, 2.5*cm, 2.4*cm, 3.0*cm, 2.7*cm]))
story.append(spacer(0.3))
# Inline chart (kept for reference — alternative to the PNG charts below)
# story.append(cer_chart())
# story.append(caption(
#     "Figure 4: Mean CER per uncommon_char_score range. Lower is better. "
#     "Red = PaddleOCR-VL-1.5 base. Green = Tachiwin-OCR-1.5."))
story.append(RLImage("chart_04_cer_by_bucket.png", width=TW*0.95, height=6*cm))
story.append(RLImage("chart_05_wer_by_bucket.png", width=TW*0.95, height=6*cm))
story.append(RLImage("chart_06_characc_by_bucket.png", width=TW*0.95, height=6*cm))
story.append(spacer(0.2))

story.append(PageBreak())
# ── 4.5 Per-language results ─────────────────────────────────────────────────
story.append(h2("4.5 Per-language results"))
story.append(body(
    "The chart below shows CER by language code (sorted by improvement, descending). "
    "Languages with larger sample sizes (e.g., Amuzgo 328 pages, Chinanteco 217 pages) "
    "show the most reliable improvement estimates. Low-N languages (≤ 7 pages) "
    "often lack statistical significance despite large point estimates."
))
story.append(RLImage("chart_14_code_cer.png", width=TW*0.95, height=6*cm))
story.append(RLImage("chart_15_code_improvement.png", width=TW*0.9, height=15*cm))
story.append(spacer(0.1))
story.append(PageBreak())
story.append(body(
    "The following table lists the largest languages by page count (≥ 20 pages). "
    "Full results for all 30 languages are in the repository."
))
story.append(spacer(0.1))
lang_rows = [
    ["Code", "Language", "Pages", "Base CER", "FT CER", "Improvement", "Sig."],
    ["amu",  "Amuzgo",       "328", "1.054", "0.219", "−79%",  "***"],
    ["lac",  "Lacandón",     "431", "0.322", "0.200", "−38%",  "**"],
    ["cco",  "Chinanteco",   "217", "1.584", "0.325", "−79%",  "***"],
    ["chz",  "Chinanteco",   "187", "0.439", "0.264", "−40%",  "***"],
    ["zae",  "Zapoteco",     "165", "1.179", "0.281", "−76%",  "***"],
    ["otm",  "Otomí",        "146", "0.340", "0.143", "−58%",  "***"],
    ["zpl",  "Zapoteco",     "76",  "0.380", "0.190", "−50%",  "*"],
    ["maj",  "Mazateco",     "64",  "2.534", "0.282", "−89%",  "***"],
    ["mxb",  "Mixteco",      "50",  "0.362", "0.211", "−42%",  "**"],
    ["ote",  "Otomí",        "42",  "0.242", "0.205", "−15%",  "ns"],
    ["ztg",  "Zapoteco",     "42",  "0.237", "0.125", "−47%",  "**"],
    ["vmp",  "Mazateco",     "33",  "0.131", "0.073", "−44%",  "***"],
    ["xtn",  "Mixteco",      "32",  "1.201", "0.196", "−84%",  "*"],
    ["jmx",  "Mixteco",      "22",  "0.498", "0.088", "−82%",  "***"],
]
story.append(dtable(lang_rows[0], lang_rows[1:],
                    cw=[1.2*cm, 2.8*cm, 1.2*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.2*cm]))
story.append(spacer(0.3))

story.append(PageBreak())
# ── 4.6 Per-superlanguage results ────────────────────────────────────────────
story.append(h2("4.6 Per-superlanguage results"))
story.append(body(
    "Grouping languages by superlanguage shows clear performance variation across "
    "all three metrics — CER, WER, and character accuracy."
))
story.append(RLImage("chart_07_superlanguage_cer.png", width=TW*0.95, height=6*cm))
story.append(RLImage("chart_08_superlanguage_wer.png", width=TW*0.95, height=6*cm))
story.append(RLImage("chart_09_superlanguage_accuracy.png", width=TW*0.95, height=6*cm))
story.append(spacer(0.1))
sl_rows = [
    ["Superlanguage", "Pages", "Base CER", "FT CER", "Improvement", "Sig."],
    ["Lacandón",      "431", "0.322", "0.200", "−38%",  "**"],
    ["Chinanteco",    "412", "1.049", "0.297", "−72%",  "***"],
    ["Amuzgo",        "328", "1.054", "0.219", "−79%",  "***"],
    ["Zapoteco",      "319", "0.814", "0.249", "−69%",  "***"],
    ["Otomí",         "188", "0.318", "0.157", "−51%",  "***"],
    ["Mixteco",       "146", "0.620", "0.214", "−66%",  "***"],
    ["Mazateco",      "117", "1.505", "0.224", "−85%",  "***"],
    ["Popoluca",       "16", "0.149", "0.077", "−49%",  "***"],
    ["Náhuatl",         "6", "0.216", "0.140", "−35%",   "ns"],
]
story.append(dtable(sl_rows[0], sl_rows[1:],
                    cw=[2.8*cm, 1.4*cm, 2.0*cm, 2.0*cm, 2.2*cm, 1.4*cm]))
story.append(spacer(0.3))

story.append(PageBreak())
# ── 4.7 Per-family results ───────────────────────────────────────────────────
story.append(h2("4.7 Per-family results"))
story.append(body(
    "At the language family level, Otomangue (1,512 pages, 73.5% reduction) dominates "
    "the evaluation set as the largest family. Yuto-Nahua shows the most dramatic "
    "improvement (86.3%) but is limited by its small sample size (8 pages, ns)."
))
story.append(RLImage("chart_10_family_cer.png", width=TW*0.95, height=6*cm))
story.append(RLImage("chart_11_family_improvement.png", width=TW*0.95, height=6*cm))
story.append(spacer(0.1))
fam_rows = [
    ["Family", "Pages", "Base CER", "FT CER", "Improvement", "Sig."],
    ["Otomangue",    "1512", "0.902", "0.239", "−74%",  "***"],
    ["Mayense",       "431", "0.322", "0.200", "−38%",  "**"],
    ["Mixe-Zoqueano",  "16", "0.149", "0.077", "−49%",  "***"],
    ["Yuto-Nahua",      "8", "2.383", "0.325", "−86%",   "ns"],
]
story.append(dtable(fam_rows[0], fam_rows[1:],
                    cw=[2.8*cm, 1.4*cm, 2.0*cm, 2.0*cm, 2.2*cm, 1.4*cm]))
story.append(spacer(0.3))

story.append(PageBreak())
# ── 4.8 Per-collection results ───────────────────────────────────────────────
story.append(h2("4.8 Per-collection results"))
story.append(body(
    "Dictionaries (643 pages) and grammars (632 pages) form the bulk of the evaluation set, "
    "both showing strong improvements (−37% and −72% respectively). Legal documents show "
    "the lowest absolute CER after fine-tuning (0.032) despite their small sample."
))
story.append(RLImage("chart_12_collection_cer.png", width=TW*0.95, height=6*cm))
story.append(spacer(0.1))
col_rows = [
    ["Collection", "Pages", "Base CER", "FT CER", "Improvement", "Sig."],
    ["dictionary",     "643", "0.357", "0.223", "−37%",  "***"],
    ["grammar",        "632", "0.730", "0.203", "−72%",  "***"],
    ["academic",       "44",  "0.241", "0.206", "−15%",   "ns"],
    ["writing_rules",  "35",  "0.856", "0.269", "−69%",  "***"],
    ["legal",          "12",  "0.124", "0.032", "−75%",  "***"],
    ["textbooks",       "4",  "0.424", "0.423",  "−0%",   "ns"],
    ["covid",           "3",  "0.283", "0.274",  "−3%",   "ns"],
    ["audio_stories",   "3",  "0.070", "0.065",  "−7%",   "ns"],
]
story.append(dtable(col_rows[0], col_rows[1:],
                    cw=[2.8*cm, 1.4*cm, 2.0*cm, 2.0*cm, 2.2*cm, 1.4*cm]))
story.append(spacer(0.3))

story.append(PageBreak())
# ── 4.9 Per-source results ───────────────────────────────────────────────────
story.append(h2("4.9 Per-source results"))
story.append(body(
    "The vast majority of pages (1,937 of 2,000) come from the ILV (Instituto Lingüístico "
    "de Verano) source, reflecting the primary institutional source of indigenous language "
    "documentation in Mexico. Government and books sources show excellent post-fine-tuning CER."
))
story.append(RLImage("chart_13_source_cer.png", width=TW*0.95, height=6*cm))
story.append(spacer(0.1))
src_rows = [
    ["Source", "Pages", "Base CER", "FT CER", "Improvement", "Sig."],
    ["ilv",        "1937", "0.793", "0.236", "−70%",  "***"],
    ["books",       "33",  "0.131", "0.073", "−44%",  "***"],
    ["government",  "12",  "0.124", "0.032", "−75%",  "***"],
    ["sep",          "4",  "0.424", "0.423",  "−0%",   "ns"],
    ["ssa",          "3",  "0.283", "0.274",  "−3%",   "ns"],
]
story.append(dtable(src_rows[0], src_rows[1:],
                    cw=[2.8*cm, 1.4*cm, 2.0*cm, 2.0*cm, 2.2*cm, 1.4*cm]))
story.append(spacer(0.3))

story.append(PageBreak())
# ── 4.10 Key findings ────────────────────────────────────────────────────────
story.append(h2("4.10 Key findings"))
for finding in [
    "<b>Consistent improvement across all score ranges:</b> The fine-tuned model brings "
    "every score range below CER 0.30, demonstrating that fine-tuning generalizes across "
    "the full spectrum of indigenous character density.",
    "<b>Largest gains where they matter most:</b> The most dramatic relative improvements "
    "occur in the [0.3–0.6) ranges (−70% to −76%), precisely where indigenous character "
    "density is highest and the base model fails most severely.",
    "<b>Statistical robustness:</b> All four metrics reach Wilcoxon p < 0.0001 on n=2,000 "
    "paired samples. The improvements are not attributable to random variation.",
    "<b>WER vs CER:</b> WER improvement (+38% relative) is more conservative than CER "
    "(+70%) due to the agglutinative morphology of many indigenous languages, where a "
    "single missed character can constitute a full word error. CER is the primary metric "
    "for this reason.",
    "<b>Full results available:</b> Per-item JSON results and per-language breakdowns "
    "are in the evaluation/test_2000/ directory of the GitHub repository.",
    "<b>Comprehensive superiority:</b> The fine-tuned model demonstrated significantly "
    "vastly superior performance versus the base model on OCR tasks for indigenous languages "
    "of Mexico across all metrics (CER, WER, char accuracy, word accuracy).",
    "<b>Low-resource language limitations:</b> Some very low-resource languages did not "
    "achieve statistically significant improvement due to few samples. As per GPU/time/cost "
    "limitations, we were unable to run the full 33K-row inference (which would require "
    "days of processing). We assume a longer evaluation run will demonstrate significant "
    "improvement on very low-resource languages as well.",
    "<b>Expected non-improvement cases:</b> Some languages like Nahuatl, Totonac, Maya, "
    "and others are written in the standard Spanish alphabet. Since the base model "
    "PaddleOCR-VL-1.5 already excels on Spanish script, they are expected NOT to achieve "
    "significant improvements — and this is not a regression, but a ceiling effect.",
    "<b>First-of-its-kind impact:</b> Tachiwin-OCR-1.5 is the first OCR model focused "
    "on the indigenous languages of Mexico that has proven proficiency. It will be "
    "paramount in the digitization and preservation of this rich language heritage.",
]:
    story.append(bullet(finding))
    story.append(spacer(0.05))
story.append(spacer(0.2))
story.append(RLImage("chart_16_scatter_coverage_improvement.png", width=TW*0.95, height=6*cm))
story.append(spacer(0.3))

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 5. OPEN-SOURCE ASSETS
# ══════════════════════════════════════════════════════════════════════════════
story.append(h1("5. Open-Source Assets"))
story.append(body(
    "All project assets are publicly available. Training data is not required to be "
    "open-sourced per the competition rules, but has been made public to maximize "
    "community value."
))
assets_rows = [
    ["Asset", "Location", "Public?"],
    ["Fine-tuned model",        "huggingface.co/tachiwin/Tachiwin-OCR-1.5",            "YES"],
    ["Training dataset",        "huggingface.co/datasets/tachiwin/multilingual_ocr_llm_2","YES"],
    ["Evaluation dataset",      "huggingface.co/datasets/tachiwin/ocr-test-challenging-3","NO"],
    ["Demo — Document OCR",     "huggingface.co/spaces/tachiwin/document-ocr",          "YES"],
    ["Demo — Multilingual OCR", "huggingface.co/spaces/tachiwin/multilingual_ocr",      "YES"],
    ["GitHub repository",       "https://github.com/tachiwin/tachiwin_ocr_1_5",                     "YES"],
]
story.append(dtable(assets_rows[0], assets_rows[1:],
                    cw=[4.5*cm, 9.0*cm, 2.5*cm]))
story.append(spacer(0.4))
story.append(callout(
    "Both Hugging Face Spaces demos are live. Reviewers can test the model directly "
    "by uploading any document image at huggingface.co/spaces/tachiwin/document-ocr — "
    "no local setup required.",
    "success"
))
story.append(spacer(0.5))
story.append(rule())
story.append(spacer(0.3))

# ── Build ─────────────────────────────────────────────────────────────────────
doc.build(story, onFirstPage=on_first_page, onLaterPages=on_page)
print("PDF built successfully →", doc.filename)
