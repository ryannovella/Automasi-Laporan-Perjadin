import os

# Base directory: root of "Automasi Laporan Perjadin"
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # .../core
BASE_DIR  = os.path.dirname(_THIS_DIR)                   # .../Automasi Laporan Perjadin

DATA_DIR       = os.path.join(BASE_DIR, "data")
UPLOADS_DIR    = os.path.join(DATA_DIR, "uploads")
OUTPUT_DIR     = os.path.join(DATA_DIR, "output")
LOGS_DIR       = os.path.join(DATA_DIR, "logs")
TEMP_MEDIA_DIR = os.path.join(DATA_DIR, "temp_media")
TEMPLATES_DIR  = os.path.join(BASE_DIR, "templates")

# Master template and data files
TEMPLATE_DOCX = os.path.join(TEMPLATES_DIR, "template_laporan_monev.docx")
LOCATIONS_CSV = os.path.join(DATA_DIR, "data_lokasi.csv")
PERSONEL_TXT  = os.path.join(DATA_DIR, "Nama Personel.txt")

# Ensure required directories exist
for _d in [DATA_DIR, UPLOADS_DIR, OUTPUT_DIR, LOGS_DIR, TEMP_MEDIA_DIR, TEMPLATES_DIR]:
    os.makedirs(_d, exist_ok=True)

# Official Stamping Standards (Kementerian Pekerjaan Umum / Pamsimas)
def _resolve_stamp_font() -> str:
    candidates = [
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return "arial.ttf"

STAMP_FONT_PATH    = _resolve_stamp_font()
FALLBACK_FONT_PATH = "arial.ttf"

# Watermark typography & proportions
FONT_SIZE_RATIO     = 0.04237   # ~20px on 472px image height
LINE_HEIGHT_RATIO   = 1.15      # Line height multiplier
MARGIN_RIGHT_RATIO  = 0.0222    # Right margin padding
MARGIN_BOTTOM_RATIO = 0.0254    # Bottom margin padding

SHADOW_DX_SCALE   = 1.2
SHADOW_DY_SCALE   = 1.2
SHADOW_BLUR_SCALE = 0.8
SHADOW_OPACITY    = 235
TEXT_COLOR        = (255, 255, 255, 255)

# Gemini AI API Configuration for Report Elaboration
# Membaca secara aman dari .streamlit/secrets.toml, environment variable, atau Streamlit Cloud Secrets
def _get_default_api_key() -> str:
    if "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"]:
        return os.environ["GEMINI_API_KEY"]
    secrets_file = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r", encoding="utf-8") as f:
                for line in f:
                    clean_l = line.strip()
                    if clean_l.startswith("GEMINI_API_KEY") and "=" in clean_l:
                        parts = clean_l.split("=", 1)
                        if len(parts) == 2:
                            return parts[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return ""

DEFAULT_API_KEY = _get_default_api_key()
GEMINI_MODEL    = "gemini-3.1-flash-lite"
