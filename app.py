import os
import io
import sys
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

import streamlit as st
from PIL import Image

# Setup root path
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from core.config import (
    BASE_DIR, UPLOADS_DIR, OUTPUT_DIR, TEMPLATE_DOCX, DEFAULT_API_KEY
)
from core.location_service import (
    get_all_kabupaten, get_kecamatan_by_kabupaten, get_desa_by_kecamatan,
    get_all_villages_with_meta, lookup_location, fuzzy_match_village, get_personel_list
)
from core.stamper import apply_stamp, stamp_to_bytes
from core.stamp_detector import detect_timestamp, crop_image_bottom
from core.timeline_analyzer import cluster_photos, generate_humanized_timeline
from core.docx_inspector import inspect_and_import_monev_docx, calculate_audit_items, get_hplus1_iso
from core.report_generator import (
    sanitize_pamsimas_text, draft_village_narrative,
    build_compact_report_filename, generate_monev_docx, format_to_indonesian_date
)

# -------------------------------------------------------------
# PAGE CONFIGURATION
# -------------------------------------------------------------
st.set_page_config(
    page_title="Automasi Laporan Perjadin - Monev Pamsimas",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for World-Class Executive Ministry of Public Works (PU) Style
st.markdown("""
<style>
    /* Google Fonts: Plus Jakarta Sans with full variable weights */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        color: #0f172a;
        background-color: #f8fafc;
    }

    /* Streamlit Main Container Optimization */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 4rem !important;
        max-width: 1280px !important;
    }

    /* Executive PU Brand Banner (Double-Bezel & Radial Ambient Glow) */
    .pu-brand-banner {
        background: radial-gradient(120% 120% at 50% 0%, #163e66 0%, #0d2945 45%, #071728 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 18px;
        padding: 32px 36px;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 12px 36px -4px rgba(7, 23, 40, 0.25), 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .pu-brand-banner::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #d49a37 0%, #f3c267 35%, #0d2945 100%);
    }
    .pu-banner-eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(212, 154, 55, 0.15);
        border: 1px solid rgba(212, 154, 55, 0.35);
        color: #f3c267;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        padding: 4px 12px;
        border-radius: 9999px;
        margin-bottom: 14px;
    }
    .pu-banner-eyebrow .dot {
        width: 6px;
        height: 6px;
        background-color: #f3c267;
        border-radius: 50%;
        box-shadow: 0 0 8px #f3c267;
    }
    .pu-brand-banner h1 {
        color: #ffffff;
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.25;
        margin: 0 0 8px 0;
    }
    .pu-brand-banner p {
        color: #cbd5e1;
        font-size: 14px;
        line-height: 1.55;
        margin: 0;
        max-width: 860px;
    }
    .pu-banner-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 600;
        color: #10b981;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.25);
        padding: 4px 10px;
        border-radius: 8px;
        margin-top: 14px;
    }
    .pu-banner-badge .pulse {
        width: 6px;
        height: 6px;
        background-color: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10b981;
    }

    /* Segmented Control Pill Tabs (Replaces default Streamlit red-line tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
        margin-bottom: 24px;
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.02);
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 10px;
        padding: 0 18px;
        background-color: transparent;
        border: none !important;
        color: #64748b;
        font-weight: 500;
        font-size: 13.5px;
        letter-spacing: -0.01em;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #0f2942;
        background-color: rgba(255, 255, 255, 0.65);
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #0f2942 !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 8px -1px rgba(15, 23, 42, 0.08), 0 1px 3px -1px rgba(15, 23, 42, 0.04) !important;
    }
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Section Titles with Icon Framing */
    .section-title {
        font-size: 17px;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #0f2942;
        margin-top: 20px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid #f1f5f9;
    }

    /* Cards & Container Architecture */
    .audit-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 24px;
        margin-bottom: 22px;
        box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
    }
    .audit-badge-complete {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #065f46;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 11px;
        letter-spacing: 0.02em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .audit-badge-incomplete {
        background: #fff1f2;
        border: 1px solid #fecdd3;
        color: #9f1239;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 11px;
        letter-spacing: 0.02em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }

    /* Village Container Box (Double-bezel look) */
    .village-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.04);
        position: relative;
    }
    .village-box-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #f1f5f9;
    }
    .village-box-header h4 {
        margin: 0;
        font-size: 16px;
        font-weight: 700;
        color: #0f2942;
        letter-spacing: -0.01em;
    }

    /* Buttons: Linear / Apple Inspired Micro-Physics */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        font-size: 13.5px;
        letter-spacing: -0.01em;
        padding: 8px 18px;
        border: 1px solid #cbd5e1;
        background: #ffffff;
        color: #0f2942;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    .stButton > button:hover {
        background: #f8fafc;
        border-color: #94a3b8;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
        color: #0f2942;
    }
    .stButton > button:active {
        transform: scale(0.98);
    }

    /* Primary Buttons (Deep PU Navy Gradient) */
    .stButton > button[kind="primary"], button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #0f2942 0%, #071728 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        box-shadow: 0 4px 14px rgba(15, 41, 66, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.15) !important;
    }
    .stButton > button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #163e66 0%, #0d2945 100%) !important;
        color: #ffffff !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(15, 41, 66, 0.4) !important;
    }
    .stButton > button[kind="primary"]:active, button[data-testid="baseButton-primary"]:active {
        transform: scale(0.98);
    }

    /* Download Buttons */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        box-shadow: 0 4px 14px rgba(5, 150, 105, 0.3) !important;
    }
    .stDownloadButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(5, 150, 105, 0.4) !important;
    }

    /* Form Inputs & Controls Focus Ring (Overriding default red) */
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div, 
    div[data-baseweb="base-input"] > input, 
    textarea.stTextArea {
        border-radius: 10px !important;
        border-color: #cbd5e1 !important;
        background-color: #ffffff !important;
        font-size: 13.5px !important;
        color: #0f172a !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div[data-baseweb="input"]:focus-within, 
    div[data-baseweb="select"]:focus-within, 
    textarea:focus {
        border-color: #0f2942 !important;
        box-shadow: 0 0 0 3px rgba(15, 41, 66, 0.12) !important;
    }

    /* File Uploader Custom Styling */
    div[data-testid="stFileUploader"] {
        border-radius: 14px;
        background-color: #ffffff;
        padding: 6px;
    }
    div[data-testid="stFileUploader"] section {
        border: 2px dashed #cbd5e1 !important;
        border-radius: 12px !important;
        background-color: #f8fafc !important;
        padding: 24px 16px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stFileUploader"] section:hover {
        border-color: #0f2942 !important;
        background-color: #f1f5f9 !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
        margin-bottom: 12px !important;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600 !important;
        font-size: 14px !important;
        color: #0f2942 !important;
    }

    /* Sidebar Refinements */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem !important;
    }

    /* Progress Bar (Gold to Navy Gradient) */
    div[data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #d49a37 0%, #0f2942 100%) !important;
        border-radius: 9999px !important;
    }

    /* Code block for filenames */
    .filename-chip {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13.5px;
        font-weight: 600;
        background: #0f2942;
        color: #f3c267;
        padding: 8px 16px;
        border-radius: 8px;
        display: inline-block;
        border: 1px solid rgba(255, 255, 255, 0.1);
        word-break: break-all;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------------------
if "report_data" not in st.session_state:
    today_dt = date.today()
    st.session_state.report_data = {
        "kabupaten": "Magelang",
        "tahun": "2026",
        "nomor_spt": "CK1201/SPT/BPBPK-JT/2026",
        "tanggal_spt": (today_dt - timedelta(days=2)).strftime("%Y-%m-%d"),
        "trip_start_date": today_dt.strftime("%Y-%m-%d"),
        "trip_end_date": (today_dt + timedelta(days=2)).strftime("%Y-%m-%d"),
        "tanggal_laporan": (today_dt + timedelta(days=3)).strftime("%Y-%m-%d"),
        "tempat_pembuatan": "Semarang",
        "pelaksana": [
            "Rey (Teknik Penyehatan Lingkungan Ahli Muda)",
            "Ahmad Fauzi (Fasilitator Teknik Lapangan)"
        ],
        "villages": [
            {
                "id": "v_1",
                "desa": "Jambewangi",
                "kecamatan": "Pakis",
                "notes": "Pekerjaan konstruksi fisik sumur bor dalam mencapai 45,20%. Penyerapan dana termin I 40%. Pipa transmisi HDPE 2 inch terpasang sepanjang 1.200 meter. Rencana sambungan rumah 75 SR.",
                "narrative": ""
            }
        ]
    }

if "photos" not in st.session_state:
    st.session_state.photos = []

if "audit_report" not in st.session_state:
    st.session_state.audit_report = None

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = os.environ.get("GEMINI_API_KEY", DEFAULT_API_KEY)

# -------------------------------------------------------------
# HELPER: REAL-TIME AUDIT CALCULATION
# -------------------------------------------------------------
def get_current_audit_status():
    rd = st.session_state.report_data
    items = calculate_audit_items(
        kabupaten=rd.get("kabupaten", ""),
        nomor_spt=rd.get("nomor_spt", ""),
        tanggal_spt_iso=rd.get("tanggal_spt", ""),
        tanggal_spt_raw=format_to_indonesian_date(rd.get("tanggal_spt", "")),
        trip_start_iso=rd.get("trip_start_date", ""),
        trip_end_iso=rd.get("trip_end_date", ""),
        tanggal_laporan_iso=rd.get("tanggal_laporan", ""),
        tanggal_laporan_raw=format_to_indonesian_date(rd.get("tanggal_laporan", "")),
        auto_hplus1=False,
        pelaksana=rd.get("pelaksana", []),
        villages=rd.get("villages", []),
        photos=st.session_state.photos
    )
    completed_cnt = sum(1 for it in items if it["status"] == "complete")
    total_cnt = len(items)
    pct = int((completed_cnt / total_cnt) * 100)
    return pct, completed_cnt, total_cnt, items

# -------------------------------------------------------------
# BANNER HEADER
# -------------------------------------------------------------
# BANNER HEADER
# -------------------------------------------------------------
st.markdown("""
<div class="pu-brand-banner">
    <div class="pu-banner-eyebrow">
        <span class="dot"></span> KEMENTERIAN PEKERJAAN UMUM • BPPW JAWA TENGAH
    </div>
    <h1>Automasi Dokumen Laporan Monev Perjadin</h1>
    <p>Platform cerdas audit kelengkapan berkas, elaborasi catatan teknis resmi, normalisasi timestamp foto lapangan, dan penyusunan dokumen laporan perjalanan dinas Kegiatan Pamsimas.</p>
    <div class="pu-banner-badge">
        <span class="pulse"></span> Sistem Otomasi Aktif • TA 2026
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# SIDEBAR: LIVE AUDIT & QUICK CONTROLS
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
        <span style="font-size:16px;">📊</span>
        <span style="font-size:14px; font-weight:700; color:#0f2942; letter-spacing:-0.01em;">Status Kelengkapan Dokumen</span>
    </div>
    """, unsafe_allow_html=True)
    score_pct, comp_cnt, tot_cnt, audit_items = get_current_audit_status()
    
    st.progress(score_pct / 100.0)
    if score_pct == 100:
        st.success(f"**Lengkap 100%** ({comp_cnt}/{tot_cnt} Komponen Terpenuhi)")
    elif score_pct >= 75:
        st.info(f"**{score_pct}% Terisi** ({comp_cnt}/{tot_cnt} Komponen Terpenuhi)")
    else:
        st.warning(f"**{score_pct}% Terisi** ({tot_cnt - comp_cnt} Komponen Belum Lengkap)")

    # Realtime Checklist
    with st.expander("Rincian 8 Komponen Audit", expanded=(score_pct < 100)):
        for it in audit_items:
            badge_cls = "audit-badge-complete" if it["status"] == "complete" else "audit-badge-incomplete"
            badge_icon = "✓" if it["status"] == "complete" else "!"
            st.markdown(f"""
            <div style="border-bottom:1px solid #f1f5f9; padding:8px 0;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                    <strong style="font-size:12.5px; color:#0f2942;">{it['label']}</strong>
                    <span class="{badge_cls}">{badge_icon} {'Lengkap' if it['status'] == 'complete' else 'Kurang'}</span>
                </div>
                <div style="font-size:11.5px; color:#64748b; line-height:1.35;">{it['message']}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ⚙️ Pengaturan Cepat")
    
    # Preset Demo
    if st.button("🔄 Muat Contoh Data Cepat (Demo)"):
        st.session_state.report_data = {
            "kabupaten": "Magelang",
            "tahun": "2026",
            "nomor_spt": "CK1201/SPT/BPBPK-JT/2026",
            "tanggal_spt": "2026-08-11",
            "trip_start_date": "2026-08-13",
            "trip_end_date": "2026-08-15",
            "tanggal_laporan": "2026-08-16",
            "tempat_pembuatan": "Semarang",
            "pelaksana": [
                "Rey (Teknik Penyehatan Lingkungan Ahli Muda)",
                "Bambang S. (Teknik Pengairan Ahli Pertama)",
                "Ahmad Fauzi (Fasilitator Teknik Lapangan)"
            ],
            "villages": [
                {
                    "id": "v_1",
                    "desa": "Jambewangi",
                    "kecamatan": "Pakis",
                    "notes": "Pekerjaan fisik sumur bor dalam mencapai 45,20%. Penyerapan dana tahap I 40,00%. Pipa HDPE 2 inch telah terpasang. Target 75 sambungan rumah.",
                    "narrative": ""
                },
                {
                    "id": "v_2",
                    "desa": "Tanjungsari",
                    "kecamatan": "Windusari",
                    "notes": "Pekerjaan bak penampung reservoir air selesai 100%. Pemasangan pompa celup submersibel siap uji coba commissioning.",
                    "narrative": ""
                }
            ]
        }
        st.success("Contoh data Monev Magelang berhasil dimuat!")
        st.rerun()

    # Reset Data
    if st.button("🗑️ Reset Semua Formulir"):
        st.session_state.report_data = {
            "kabupaten": "Magelang",
            "tahun": "2026",
            "nomor_spt": "",
            "tanggal_spt": "",
            "trip_start_date": "",
            "trip_end_date": "",
            "tanggal_laporan": "",
            "tempat_pembuatan": "Semarang",
            "pelaksana": [],
            "villages": [{"id": "v_1", "desa": "", "kecamatan": "", "notes": "", "narrative": ""}]
        }
        st.session_state.photos = []
        st.info("Formulir telah dikosongkan.")
        st.rerun()

    st.markdown("---")
    # API Key Input
    with st.expander("🔑 Konfigurasi Gemini AI"):
        new_key = st.text_input("Gemini API Key", value=st.session_state.gemini_api_key, type="password")
        if new_key != st.session_state.gemini_api_key:
            st.session_state.gemini_api_key = new_key
            st.success("API Key diperbarui!")

# -------------------------------------------------------------
# MAIN APP TABS
# -------------------------------------------------------------
tab_import, tab_admin, tab_desa, tab_foto, tab_export = st.tabs([
    "📂 1. Buka Dokumen Eksisting",
    "📋 2. Administrasi & SPT",
    "🏘️ 3. Multi-Desa & Catatan",
    "📸 4. Foto Dokumentasi",
    "📄 5. Generate & Unduh (.docx)"
])

# =============================================================
# TAB 1: BUKA & AUDIT DOKUMEN EKSISTING
# =============================================================
with tab_import:
    st.markdown('<div class="section-title">📂 Upload & Audit Dokumen Word Eksisting (.docx)</div>', unsafe_allow_html=True)
    st.write("Unggah dokumen laporan perjalanan dinas yang belum lengkap untuk diaudit kelengkapannya secara otomatis, mendeteksi apa yang sudah dan belum ada, serta mengisi formulir secara instan.")

    uploaded_docx = st.file_uploader("Pilih Berkas Laporan (.docx)", type=["docx"], key="docx_uploader")
    
    if uploaded_docx is not None:
        save_path = os.path.join(UPLOADS_DIR, uploaded_docx.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_docx.getbuffer())
        
        with st.spinner("Menganalisis isi dokumen, mengekstrak teks, tabel, desa, dan foto..."):
            audit_res = inspect_and_import_monev_docx(save_path)
            st.session_state.audit_report = audit_res

        if audit_res.get("success"):
            rep_data = audit_res.get("report_data", {})
            audit_meta = audit_res.get("audit_report", {})
            score = audit_meta.get("score_percent", 0)

            # Audit Summary Card
            score_color = "#059669" if score >= 80 else "#e11d48"
            st.markdown(f"""
            <div class="audit-card">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
                    <div>
                        <div style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;">HASIL AUDIT RESMI KELENGKAPAN</div>
                        <h3 style="margin:0; font-size:18px; font-weight:700; color:#0f2942;">{uploaded_docx.name}</h3>
                        <p style="margin:6px 0 0 0; font-size:13.5px; color:#475569;">{audit_meta.get('summary')}</p>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:38px; font-weight:800; color:{score_color}; line-height:1; font-family:'Plus Jakarta Sans', sans-serif;">
                            {score}%
                        </div>
                        <div style="font-size:12px; font-weight:600; color:{score_color}; margin-top:4px;">
                            {'Kategori: Memenuhi Syarat' if score >= 80 else 'Kategori: Perlu Dilengkapi'}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_btn1, col_btn2 = st.columns([2, 3])
            with col_btn1:
                if st.button("📥 Muat Data Dokumen ke Formulir Aplikasi", type="primary"):
                    st.session_state.report_data = rep_data
                    if audit_res.get("photos"):
                        st.session_state.photos = audit_res.get("photos")
                    st.success("Seluruh data dokumen berhasil dimuat ke formulir aplikasi!")
                    st.rerun()

            # Tampilkan 8 Komponen
            st.markdown("##### Rincian Pemeriksaan Kelengkapan:")
            col_a, col_b = st.columns(2)
            items = audit_meta.get("items", [])
            for idx, it in enumerate(items):
                target_col = col_a if idx % 2 == 0 else col_b
                with target_col:
                    badge_cls = "audit-badge-complete" if it["status"] == "complete" else "audit-badge-incomplete"
                    badge_txt = "LENGKAP" if it["status"] == "complete" else "BELUM LENGKAP"
                    badge_icon = "✓" if it["status"] == "complete" else "!"
                    st.markdown(f"""
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px; margin-bottom:10px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <strong style="font-size:13.5px; color:#0f2942;">{it['label']}</strong>
                            <span class="{badge_cls}">{badge_icon} {badge_txt}</span>
                        </div>
                        <div style="font-size:12.5px; color:#64748b; line-height:1.4;">{it['message']}</div>
                    </div>
                    """, unsafe_allow_html=True)

# =============================================================
# TAB 2: ADMINISTRASI & SPT
# =============================================================
with tab_admin:
    st.markdown('<div class="section-title">📋 Data Administrasi & Surat Perintah Tugas (SPT)</div>', unsafe_allow_html=True)
    
    rd = st.session_state.report_data
    all_kabs = get_all_kabupaten()
    default_kab_idx = all_kabs.index(rd.get("kabupaten", "Magelang")) if rd.get("kabupaten") in all_kabs else 0

    col_adm1, col_adm2, col_adm3 = st.columns(3)
    with col_adm1:
        sel_kab = st.selectbox("Kabupaten Kegiatan", all_kabs, index=default_kab_idx)
        rd["kabupaten"] = sel_kab
        
        rd["nomor_spt"] = st.text_input("Nomor SPT Resmi", value=rd.get("nomor_spt", ""))

    with col_adm2:
        # Date Picker untuk Tanggal SPT
        spt_val = None
        if rd.get("tanggal_spt"):
            try:
                spt_val = datetime.strptime(rd["tanggal_spt"], "%Y-%m-%d").date()
            except Exception:
                pass
        sel_tgl_spt = st.date_input("Tanggal SPT", value=spt_val or date.today())
        rd["tanggal_spt"] = sel_tgl_spt.strftime("%Y-%m-%d")

        rd["tempat_pembuatan"] = st.text_input("Tempat Pembuatan Laporan", value=rd.get("tempat_pembuatan", "Semarang"))

    with col_adm3:
        rd["tahun"] = st.text_input("Tahun Anggaran (TA)", value=rd.get("tahun", "2026"))

    st.markdown('<div class="section-title">🗓️ Jadwal Perjalanan Dinas & Tanggal Laporan</div>', unsafe_allow_html=True)
    col_t1, col_t2, col_t3 = st.columns(3)
    
    with col_t1:
        # Tanggal Mulai Dinas
        start_d_val = None
        if rd.get("trip_start_date"):
            try: start_d_val = datetime.strptime(rd["trip_start_date"], "%Y-%m-%d").date()
            except Exception: pass
        sel_start_d = st.date_input("Tanggal Mulai Perjalanan Dinas", value=start_d_val or date.today())
        rd["trip_start_date"] = sel_start_d.strftime("%Y-%m-%d")

    with col_t2:
        # Tanggal Selesai Dinas
        end_d_val = None
        if rd.get("trip_end_date"):
            try: end_d_val = datetime.strptime(rd["trip_end_date"], "%Y-%m-%d").date()
            except Exception: pass
        sel_end_d = st.date_input("Tanggal Selesai Perjalanan Dinas", value=end_d_val or sel_start_d)
        if sel_end_d < sel_start_d:
            sel_end_d = sel_start_d
        rd["trip_end_date"] = sel_end_d.strftime("%Y-%m-%d")

    with col_t3:
        # Otomatis Tanggal Laporan adalah H+1 dari hari terakhir dinas
        auto_h1 = (sel_end_d + timedelta(days=1)).strftime("%Y-%m-%d")
        lap_d_val = None
        if rd.get("tanggal_laporan"):
            try: lap_d_val = datetime.strptime(rd["tanggal_laporan"], "%Y-%m-%d").date()
            except Exception: pass
        
        sel_lap_d = st.date_input("Tanggal Laporan (Auto H+1 Dinas)", value=lap_d_val or (sel_end_d + timedelta(days=1)))
        rd["tanggal_laporan"] = sel_lap_d.strftime("%Y-%m-%d")
        st.caption(f"💡 Default resmi: H+1 dari akhir dinas ({auto_h1})")

    # Personel Pelaksana Monev BPBPK
    st.markdown('<div class="section-title">👥 Personel Pelaksana Monev (Format Tanda Tangan Zig-Zag PU)</div>', unsafe_allow_html=True)
    master_personel = get_personel_list()
    
    col_p1, col_p2 = st.columns([3, 2])
    with col_p1:
        st.markdown("##### Pilih Personel dari Master Data BPBPK Jateng:")
        selected_from_master = st.selectbox(
            "Cari & Tambah Personel:",
            options=["-- Pilih Personel BPBPK --"] + master_personel,
            index=0
        )
        if selected_from_master and selected_from_master != "-- Pilih Personel BPBPK --":
            if selected_from_master not in rd["pelaksana"]:
                if st.button(f"➕ Tambahkan '{selected_from_master.split('(')[0].strip()}'"):
                    rd["pelaksana"].append(selected_from_master)
                    st.rerun()

    with col_p2:
        st.markdown("##### Tambah Personel Luar / Manual:")
        custom_personel = st.text_input("Ketik Nama Personel Luar & Jabatan:")
        if st.button("➕ Tambah Personel Manual"):
            if custom_personel.strip() and custom_personel.strip() not in rd["pelaksana"]:
                rd["pelaksana"].append(custom_personel.strip())
                st.rerun()

    # Tampilkan Daftar Personel yang Ditugaskan
    st.markdown("##### Daftar Pelaksana yang Ditugaskan:")
    if not rd["pelaksana"]:
        st.info("Belum ada personel pelaksana yang ditambahkan.")
    else:
        for p_idx, p_name in enumerate(rd["pelaksana"]):
            c_p_idx, c_p_name, c_p_del = st.columns([1, 10, 2])
            c_p_idx.write(f"**{p_idx+1}.**")
            c_p_name.write(p_name)
            if c_p_del.button("❌ Hapus", key=f"del_p_{p_idx}"):
                rd["pelaksana"].pop(p_idx)
                st.rerun()

# =============================================================
# TAB 3: DATA MULTI-DESA & CATATAN LAPANGAN
# =============================================================
with tab_desa:
    st.markdown('<div class="section-title">🏘️ Data Multi-Desa & Catatan Lapangan</div>', unsafe_allow_html=True)
    st.write("Tambahkan desa lokasi pemantauan. Nama desa dilengkapi fitur autofill yang otomatis mencocokkan nama kecamatan secara cerdas.")

    all_villages_meta = get_all_villages_with_meta()
    all_village_names = sorted(list(set(loc["desa"] for loc in all_villages_meta if loc["desa"])))

    villages = rd.get("villages", [])

    for v_idx, v_item in enumerate(villages):
        v_desa_label = f" — Desa {v_item.get('desa')}" if v_item.get("desa") else ""
        v_kec_label = f"Kec. {v_item.get('kecamatan')}" if v_item.get("kecamatan") else "Kecamatan Terpilih"
        st.markdown(f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:12px 18px; margin-top:14px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; box-shadow:0 1px 3px rgba(0,0,0,0.02);">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:16px;">📍</span>
                <strong style="font-size:14.5px; color:#0f2942;">Lokasi Desa #{v_idx+1}{v_desa_label}</strong>
            </div>
            <span style="font-size:11.5px; font-weight:600; color:#0f2942; background:#f1f5f9; border:1px solid #e2e8f0; padding:3px 10px; border-radius:6px;">
                {v_kec_label}
            </span>
        </div>
        """, unsafe_allow_html=True)

        col_v1, col_v2, col_v3 = st.columns([3, 3, 1])
        with col_v1:
            cur_desa = v_item.get("desa", "")
            # Autofill Dropdown / Searchable selectbox
            options_desa = ["-- Pilih atau Ketik Nama Desa --"] + all_village_names
            desa_idx = 0
            if cur_desa and cur_desa in all_village_names:
                desa_idx = options_desa.index(cur_desa)

            selected_desa = st.selectbox(
                f"Nama Desa #{v_idx+1}",
                options=options_desa,
                index=desa_idx,
                key=f"sel_desa_{v_idx}"
            )
            
            # Jika user memilih dari dropdown, update otomatis kecamatan
            if selected_desa != "-- Pilih atau Ketik Nama Desa --":
                v_item["desa"] = selected_desa
                _, _, looked_kec, looked_kab = lookup_location(selected_desa, "", rd.get("kabupaten", ""))
                if looked_kec:
                    v_item["kecamatan"] = looked_kec
            else:
                manual_desa = st.text_input(f"Atau input nama desa manual:", value=v_item.get("desa", ""), key=f"man_desa_{v_idx}")
                if manual_desa:
                    v_item["desa"] = manual_desa

        with col_v2:
            cur_kec = v_item.get("kecamatan", "")
            kec_input = st.text_input(f"Kecamatan (Otomatis):", value=cur_kec, key=f"kec_{v_idx}")
            v_item["kecamatan"] = kec_input

        with col_v3:
            st.write("")
            st.write("")
            if len(villages) > 1:
                if st.button("🗑️ Hapus", key=f"del_v_{v_idx}"):
                    villages.pop(v_idx)
                    st.rerun()

        # Catatan Lapangan & Narasi
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            st.markdown("**Catatan Lapangan / Poin Temuan Mentah:**")
            v_notes = st.text_area(
                "Catatan Lapangan:",
                value=v_item.get("notes", ""),
                height=180,
                key=f"notes_{v_idx}",
                placeholder="Contoh: Pekerjaan fisik sumur bor dalam mencapai 45,20%. Penyerapan dana termin I 40,00%. Pipa HDPE 2 inch terpasang 1.200 meter. Rencana sambungan rumah 75 SR. Kendala batuan keras di kedalaman 60m..."
            )
            v_item["notes"] = v_notes

            if st.button(f"🪄 Elaborasi Catatan dengan AI / KBBI (#{v_idx+1})", key=f"btn_el_{v_idx}"):
                with st.spinner("Menyusun narasi resmi kedinasan Kementerian PU (anti-proyek, anti-pupr, kaidah KBBI)..."):
                    el_narrative = draft_village_narrative(
                        raw_notes=v_notes,
                        desa=v_item.get("desa", "Wilayah"),
                        kecamatan=v_item.get("kecamatan", ""),
                        kabupaten=rd.get("kabupaten", "Magelang"),
                        tahun=rd.get("tahun", "2026"),
                        tanggal_lap=rd.get("tanggal_laporan", ""),
                        api_key=st.session_state.gemini_api_key
                    )
                    v_item["narrative"] = el_narrative
                    st.rerun()

        with col_n2:
            st.markdown("**Hasil Narasi Resmi Kementerian PU (Bab B. Hasil yang Dicapai):**")
            v_nar = st.text_area(
                "Narasi Siap Cetak Word:",
                value=v_item.get("narrative", ""),
                height=180,
                key=f"nar_{v_idx}",
                placeholder="Klik 'Elaborasi Catatan' untuk menghasilkan narasi resmi kedinasan sesuai kaidah KBBI tanpa kata 'proyek' atau 'PUPR'..."
            )
            v_item["narrative"] = v_nar

        st.markdown("---")

    if st.button("➕ Tambah Desa Baru"):
        villages.append({
            "id": f"v_{uuid.uuid4().hex[:6]}",
            "desa": "",
            "kecamatan": "",
            "notes": "",
            "narrative": ""
        })
        st.rerun()

# =============================================================
# TAB 4: FOTO DOKUMENTASI & TIMESTAMP WATERMARK
# =============================================================
with tab_foto:
    st.markdown('<div class="section-title">📸 Dokumentasi Foto Lapangan & Timestamp Watermark</div>', unsafe_allow_html=True)
    st.write("Unggah foto dokumentasi kegiatan. Sistem secara otomatis menyeleksi timestamp lama bawaan kamera, meratakan aspek rasio 4:3, serta menerapkan linimasa jam kerja dinas yang realistis (menit & detik tidak bulat kelipatan 5).")

    # Upload Foto Massal
    uploaded_photos = st.file_uploader(
        "Unggah Foto Lapangan (JPG / PNG)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="photo_uploader"
    )

    if uploaded_photos:
        new_count = 0
        for uf in uploaded_photos:
            existing_names = [p.get("filename") for p in st.session_state.photos]
            if uf.name not in existing_names:
                save_fpath = os.path.join(UPLOADS_DIR, uf.name)
                with open(save_fpath, "wb") as f_out:
                    f_out.write(uf.getbuffer())
                
                # Cek stempel lama
                stamp_chk = detect_timestamp(save_fpath)
                st.session_state.photos.append({
                    "id": f"p_{uuid.uuid4().hex[:8]}",
                    "filename": uf.name,
                    "path": save_fpath,
                    "has_timestamp": stamp_chk.get("has_timestamp", False),
                    "suggested_crop_bottom": stamp_chk.get("suggested_crop_bottom", 0.18),
                    "alreadyStamped": False,
                    "desa": villages[0].get("desa", "") if villages else "",
                    "kecamatan": villages[0].get("kecamatan", "") if villages else "",
                    "dusun": "",
                    "lat": None,
                    "lon": None,
                    "time_str": ""
                })
                new_count += 1
        if new_count > 0:
            st.success(f"{new_count} foto baru berhasil ditambahkan!")
            st.rerun()

    # Kontrol Linimasa Waktu & GPS
    if st.session_state.photos:
        st.markdown('<div class="section-title">⚡ Generate Linimasa Jam Kerja Dinas & Koordinat GPS Jitter</div>', unsafe_allow_html=True)
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            start_work_time = st.text_input("Jam Mulai Dinas Lapangan", value="09:14:23")
        with col_w2:
            end_work_time = st.text_input("Batas Maksimal Jam Kerja Sore", value="15:00:00")
        with col_w3:
            st.write("")
            st.write("")
            if st.button("🚀 Terapkan Linimasa & GPS Realistis ke Seluruh Foto"):
                with st.spinner("Menghitung kluster lokasi, sebaran multi-hari, dan koordinat GPS..."):
                    # Buat kluster
                    clusters = cluster_photos(st.session_state.photos)
                    
                    # Parse tanggal dinas
                    s_d, s_m, s_y = int(rd["trip_start_date"].split("-")[2]), int(rd["trip_start_date"].split("-")[1]), int(rd["trip_start_date"].split("-")[0])
                    e_d, e_m, e_y = int(rd["trip_end_date"].split("-")[2]), int(rd["trip_end_date"].split("-")[1]), int(rd["trip_end_date"].split("-")[0])

                    # Lookup koordinat dasar per desa
                    for p in st.session_state.photos:
                        v_target = p.get("desa") or (villages[0].get("desa", "") if villages else "")
                        p["desa"] = v_target
                        lat_val, lon_val, k_val, _ = lookup_location(v_target, p.get("kecamatan", ""), rd.get("kabupaten", ""))
                        p["lat"] = lat_val
                        p["lon"] = lon_val
                        p["kecamatan"] = k_val

                    timeline_res = generate_humanized_timeline(
                        clusters=clusters,
                        start_time_str=start_work_time,
                        end_time_str=end_work_time,
                        date_tuple=(s_y, s_m, s_d),
                        end_date_tuple=(e_y, e_m, e_d)
                    )
                    
                    # Update metadata foto
                    for t_item in timeline_res:
                        p_id = t_item.get("photo_id")
                        for p in st.session_state.photos:
                            if p.get("id") == p_id:
                                p["time_str"] = t_item.get("time_str")
                                p["lat"] = t_item.get("lat")
                                p["lon"] = t_item.get("lon")
                                break
                    st.success("Linimasa dinas realistis dan GPS Jitter berhasil dipetakan ke seluruh foto!")
                    st.rerun()

        # Galeri Foto & Live Preview
        st.markdown(f"##### Galeri Foto Lapangan ({len(st.session_state.photos)} Foto):")
        
        col_g1, col_g2 = st.columns(2)
        for p_idx, p in enumerate(st.session_state.photos):
            target_col = col_g1 if p_idx % 2 == 0 else col_g2
            with target_col:
                with st.expander(f"Foto #{p_idx+1}: {p.get('filename')}", expanded=False):
                    fpath = p.get("path")
                    if fpath and os.path.exists(fpath):
                        pil_img = Image.open(fpath)
                        st.image(pil_img, caption=f"Foto {p_idx+1}: {p.get('filename')}", use_container_width=True)

                        col_f_meta1, col_f_meta2 = st.columns(2)
                        with col_f_meta1:
                            v_opts = [v.get("desa") for v in villages if v.get("desa")]
                            p_v_idx = v_opts.index(p.get("desa")) if p.get("desa") in v_opts else 0
                            p["desa"] = st.selectbox(f"Lokasi Desa:", options=v_opts or ["Desa Lapangan"], index=p_v_idx, key=f"p_desa_{p_idx}")
                            p["dusun"] = st.text_input(f"Dusun / Titik:", value=p.get("dusun", ""), key=f"p_dusun_{p_idx}")

                        with col_f_meta2:
                            p["lat"] = st.text_input("Latitude:", value=str(p.get("lat") or "-7.451824"), key=f"p_lat_{p_idx}")
                            p["lon"] = st.text_input("Longitude:", value=str(p.get("lon") or "110.331825"), key=f"p_lon_{p_idx}")

                        p["time_str"] = st.text_input("Teks Tanggal & Waktu:", value=p.get("time_str") or f"Kamis, 14 Agustus 2026 10:14:23 WIB", key=f"p_time_{p_idx}")

                        # Preview Live Watermark Stamped
                        if st.button(f"👁️ Pratinjau Watermark Resmi PU (#{p_idx+1})", key=f"btn_prev_{p_idx}"):
                            norm_img = pil_img.copy()
                            if p.get("has_timestamp"):
                                norm_img, _ = crop_image_bottom(norm_img, p.get("suggested_crop_bottom", 0.18))
                            stamped = apply_stamp(
                                norm_img,
                                time_str=p["time_str"],
                                lat=p["lat"],
                                lon=p["lon"],
                                dusun=p["dusun"],
                                desa=p["desa"],
                                kecamatan=p.get("kecamatan", ""),
                                kabupaten=f"Kabupaten {rd.get('kabupaten')}"
                            )
                            st.image(stamped, caption="Pratinjau Hasil Stempel Resmi Kementerian PU", use_container_width=True)

                        if st.button(f"🗑️ Hapus Foto #{p_idx+1}", key=f"btn_del_photo_{p_idx}"):
                            st.session_state.photos.pop(p_idx)
                            st.rerun()

# =============================================================
# TAB 5: GENERATE DOKUMEN & UNDUH (.DOCX)
# =============================================================
with tab_export:
    st.markdown('<div class="section-title">📄 Generate Dokumen Laporan Word (.docx)</div>', unsafe_allow_html=True)
    st.write("Dokumen laporan resmi disusun menggunakan master template resmi Kementerian PU, memuat kop surat kedinasan, format numbering resmi, tabel pelaksana dinas format zig-zag, dan lampiran dokumentasi foto 2-kolom bertanda tangan/watermark.")

    # Status Kelengkapan Akhir
    score_pct, comp_cnt, tot_cnt, _ = get_current_audit_status()
    if score_pct == 100:
        st.success(f"🎉 **Dokumen Siap Dicetak (100% Lengkap)**. Seluruh komponen data administrasi, jadwal, desa, narasi, dan foto telah terpenuhi.")
    else:
        st.warning(f"⚠️ **Kelengkapan Dokumen: {score_pct}%**. Masih terdapat {tot_cnt - comp_cnt} data yang belum lengkap, namun Anda tetap dapat melakukan generate dokumen.")

    # Preview Nama File Output
    out_fname = build_compact_report_filename(rd, rd.get("villages", []))
    
    st.markdown(f"""
    <div class="audit-card">
        <div style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:8px;">FORMAT NAMA BERKAS KEDINASAN RESMI (.DOCX):</div>
        <div class="filename-chip">{out_fname}</div>
        <div style="font-size:12.5px; color:#64748b; margin-top:10px; line-height:1.4;">
            💡 <strong>Standar BPPW/BPBPK Jawa Tengah:</strong> Nama berkas diawali rentang tanggal perjalanan dinas untuk mempermudah audit dan pengarsipan digital.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Ringkasan Eksekutif Sebelum Cetak
    col_sum1, col_sum2 = st.columns(2)
    with col_sum1:
        st.markdown(f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:16px 18px; margin-bottom:14px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-size:12px; font-weight:700; color:#0f2942; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:10px;">📋 Administrasi & Jadwal</div>
            <div style="font-size:13px; color:#334155; line-height:1.7;">
                <div><strong>Kabupaten:</strong> Kabupaten {rd.get('kabupaten')}</div>
                <div><strong>Nomor SPT:</strong> {rd.get('nomor_spt') or '<em>(Belum Diisi)</em>'}</div>
                <div><strong>Jadwal Dinas:</strong> {rd.get('trip_start_date')} s/d {rd.get('trip_end_date')}</div>
                <div><strong>Tanggal Laporan:</strong> {rd.get('tanggal_laporan')} ({rd.get('tempat_pembuatan')})</div>
                <div><strong>Pelaksana:</strong> {len(rd.get('pelaksana', []))} Personel (Format Zig-Zag PU)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_sum2:
        v_list_str = ", ".join([v.get("desa") for v in rd.get("villages", []) if v.get("desa")]) or "(Belum Ada)"
        st.markdown(f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:16px 18px; margin-bottom:14px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-size:12px; font-weight:700; color:#0f2942; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:10px;">🏘️ Cakupan Wilayah & Foto</div>
            <div style="font-size:13px; color:#334155; line-height:1.7;">
                <div><strong>Daftar Desa:</strong> {v_list_str}</div>
                <div><strong>Total Dokumentasi:</strong> {len(st.session_state.photos)} Foto Terlampir</div>
                <div><strong>Watermark PU:</strong> Font Arial Drop-Shadow (Kaidah KBBI)</div>
                <div><strong>Format Dokumen:</strong> Word .docx (Kop & Outline Resmi PU)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    col_gen1, col_gen2 = st.columns([2, 3])
    with col_gen1:
        if st.button("🚀 Generate Dokumen Laporan (.docx)", type="primary", use_container_width=True):
            with st.spinner("Menyusun dokumen Word, merapikan tabel zig-zag, menyisipkan narasi KBBI, dan merender watermark foto..."):
                target_output_file = os.path.join(OUTPUT_DIR, out_fname)
                try:
                    res_path = generate_monev_docx(
                        report_data=rd,
                        photos=st.session_state.photos,
                        output_path=target_output_file
                    )
                    st.session_state["last_generated_docx"] = res_path
                    st.success(f"✅ Dokumen berhasil digenerate!")
                except Exception as ex:
                    st.error(f"Gagal menyusun dokumen: {ex}")

    with col_gen2:
        last_docx = st.session_state.get("last_generated_docx")
        if last_docx and os.path.exists(last_docx):
            with open(last_docx, "rb") as f_down:
                docx_bytes = f_down.read()
            st.download_button(
                label=f"📥 Unduh {os.path.basename(last_docx)}",
                data=docx_bytes,
                file_name=os.path.basename(last_docx),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
