import os
import io
import re
import json
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from PIL import Image

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from core.config import (
    BASE_DIR, OUTPUT_DIR, STAMP_FONT_PATH, FALLBACK_FONT_PATH,
    TEMPLATE_DOCX, DEFAULT_API_KEY, GEMINI_MODEL
)
from core.stamper import apply_stamp
from core.logger import log_error

SYSTEM_INSTRUCTION_ANTI_SLOP = """Anda adalah penyusun laporan teknis resmi Kegiatan Pamsimas (Penyediaan Air Minum dan Sanitasi Berbasis Masyarakat) Balai Prasarana Permukiman Wilayah (BPPW / BPBPK) Jawa Tengah, Kementerian Pekerjaan Umum (Kementerian PU).

TUGAS:
Ubah catatan mentah / temuan lapangan menjadi poin-poin, kalimat, dan narasi profesional dengan penjabaran dan penjelasan yang komprehensif, lugas, dan kontekstual dengan kegiatan Pamsimas.

ATURAN WAJIB & DIKSI KEDINASAN (STRICT):
1. DILARANG KERAS MENGGUNAKAN KATA: 'proyek', 'program', 'program pamsimas', 'pupr', 'kementerian pupr', 'kementrian pupr', 'pekerjaan umum dan perumahan rakyat', 'kemenpupr'! Karena nomenklatur resmi saat ini telah resmi menjadi 'Kementerian PU' (Kementerian Pekerjaan Umum). Selalu gunakan istilah resmi kedinasan: 'Kementerian PU', 'kegiatan', 'kegiatan Pamsimas', 'pekerjaan', atau 'pembangunan sarana air minum'.
2. DILARANG menggunakan tanda em dash ('—'). Gunakan tanda koma (,), titik (.), titik dua (:), atau tanda kurung ().
3. DILARANG pembuka klise AI atau bunga kata (seperti 'Dalam lanskap...', 'Menandakan era baru...', 'Patut dicatat...', 'Tentunya...', 'Menunjukkan komitmen tak tergoyahkan').
4. DILARANG kesimpulan filosofis kosong di akhir poin.
5. DILARANG MENGARANG DATA/ANGKA: Hanya gunakan data fisik, persen progres, angka keuangan, tanggal, dan nama yang ada di catatan. Jika ada aspek teknis di catatan (misal kendala formasi tanah/batuan saat pemboran, casing sumur, pipa transmisi, debit air, uji kualitas air), jabarkan implikasi teknis dan rekomendasi solusinya secara komprehensif kontekstual Pamsimas.
6. Gaya bahasa kedinasan teknis Kementerian PU: lugas, faktual, presisi, padat, berorientasi data fisik dan keuangan serta solusi kendala lapangan.
7. DILARANG KERAS MENGULANG KATA ATAU FRASA BERTURUT-TURUT (ANTI-DUPLIKASI): Jangan pernah menghasilkan duplikasi kalimat atau frasa seperti 'dialirkan menuju dialirkan menuju', 'direncanakan direncanakan', atau 'telah telah'. Pastikan setiap kata dan sambungan antarklausa mengalir secara logis dan padat tanpa pengulangan kata yang sama.

FORMAT STRUKTUR OUTPUT (SESUAI KAIDAH KBBI):
- Awali dengan kalimat pengantar:
  Hasil monitoring dan evaluasi pelaksanaan Kegiatan Pamsimas TA [Tahun] di Desa [Desa], Kecamatan [Kecamatan], Kabupaten [Kabupaten], kondisi per [Tanggal] adalah sebagai berikut:
- Diikuti butir-butir terstruktur (Wajib gunakan format bold pada label dan selalu beri 1 spasi setelah titik dua):
  * **Progres fisik:** Realisasi capaian pekerjaan fisik sebesar [angka, misal 23,12%], meliputi... [jabarkan rincian pekerjaan dan progresnya]
  * **Progres keuangan:** Realisasi penyerapan dana sebesar [angka, misal 20,65%], meliputi... [jabarkan tahap pencairan / penggunaan]
  * **Opsi sistem & sarana:** [rincian opsi sistem, misal Sumur Bor Dalam (SBD) / Mata Air Pompa (MAP) / Gravitasi, bak penampung, menara air, dsb.]
  * **Pengadaan pipa dan aksesoris:** [status pembelian dan pemasangan pipa transmisi, pipa distribusi, dan perlengkapan sambungan rumah]
  * **Rencana sambungan rumah (SR):** [target dan alokasi unit sambungan rumah bagi warga penerima manfaat]
  * **Kendala dan permasalahan:** [penjabaran komprehensif permasalahan riil lapangan, baik kendala teknis formasi batuan/geologi, ketersediaan material, sosial swadaya, maupun koordinasi masyarakat]
  * **Tindak lanjut & rekomendasi:** [langkah solutif konkret untuk TPK, Pemdes, fasilitator pendamping, dan teknisi pelaksana]

ATURAN KBBI & TATA BAHASA KEDINASAN:
- Selalu beri 1 spasi setelah tanda baca (titik dua ':', titik '.', koma ','). DILARANG MENEMPELKAN KATA TANPA SPASI SETELAH TITIK DUA (contoh salah: 'Progres fisik:Realisasi...', contoh benar: 'Progres fisik: Realisasi...').
- Angka persentase desimal ditulis menggunakan tanda koma sesuai KBBI (contoh: 23,12% bukan 23.12%).
- Hasilkan narasi siap pakai dalam format teks paragraf dan butir poin yang rapi tanpa markdown berlebih."""

def sanitize_pamsimas_text(text: str) -> str:
    """
    Menyelaraskan teks narasi laporan agar mematuhi standar resmi Pamsimas & KBBI:
    1. Menghilangkan kata 'proyek', 'program', 'program pamsimas' secara ketat.
    2. Menghilangkan kata 'pupr', 'kementerian pupr', 'pekerjaan umum dan perumahan rakyat' -> resmi 'Kementerian PU'.
    3. Normalisasi tanda baca KBBI & anti-duplikasi kata/frasa berturut-turut.
    """
    if not text:
        return ""

    text = text.replace("—", ", ")
    text = re.sub(r"(?i)\bkementrian\b", "Kementerian", text)

    # 1. Hindari kata 'program pamsimas' / 'proyek pamsimas'
    text = re.sub(r"(?i)\bprogram\s+pamsimas\b", "Kegiatan Pamsimas", text)
    text = re.sub(r"(?i)\bproyek\s+pamsimas\b", "Kegiatan Pamsimas", text)

    # 2. Hindari nomenklatur lama PUPR -> resmi Kementerian PU
    text = re.sub(
        r"(?i)\bkementerian\s+pekerjaan\s+umum\s+dan\s+perumahan\s+rakyat(?:\s*[\(\[]\s*pupr\s*[\)\]])?\b",
        "Kementerian PU",
        text
    )
    text = re.sub(
        r"(?i)\bdinas\s+pekerjaan\s+umum(?:\s+dan\s+(?:perumahan\s+rakyat|penataan\s+ruang))?(?:\s*[\(\[]\s*pupr\s*[\)\]])?\b",
        "Dinas PU",
        text
    )
    text = re.sub(r"(?i)\bdinas\s+pupr\b", "Dinas PU", text)
    text = re.sub(r"(?i)\b(?:kementerian|kemen)\s*pupr\b", "Kementerian PU", text)
    text = re.sub(r"(?i)\bkemenpupr\b", "Kementerian PU", text)
    text = re.sub(r"(?i)\bKementerian\s+PU\s*[\(\[]\s*pupr\s*[\)\]]", "Kementerian PU", text)
    text = re.sub(r"(?i)\bpekerjaan\s+umum\s+dan\s+perumahan\s+rakyat\b", "Pekerjaan Umum", text)
    text = re.sub(r"(?i)\bpupr\b", "Kementerian PU", text)
    text = re.sub(r"(?i)\bKementerian\s+Kementerian\s+PU\b", "Kementerian PU", text)

    # 3. Hindari kata 'proyek' / 'program'
    def replace_proyek(match):
        w = match.group(0)
        if w.isupper():
            return "KEGIATAN"
        elif w[0].isupper():
            return "Kegiatan"
        return "kegiatan"

    text = re.sub(r"\bproyek(?:-proyek)?\b", replace_proyek, text, flags=re.IGNORECASE)

    def replace_program(match):
        w = match.group(0)
        if w.isupper():
            return "KEGIATAN"
        elif w[0].isupper():
            return "Kegiatan"
        return "kegiatan"

    text = re.sub(r"\bprogram(?:-program)?\b", replace_program, text, flags=re.IGNORECASE)

    # 4. Anti-duplikasi kata atau frasa berturut-turut (e.g. 'dialirkan menuju dialirkan menuju')
    # 4a. Duplikasi frasa 2-4 kata
    text = re.sub(r'\b([a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+){1,3})\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    # 4b. Duplikasi kata tunggal berturut-turut
    text = re.sub(r'\b([a-zA-Z0-9_]+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

    # 5. Normalisasi Tanda Baca KBBI
    # 5a. 1 Spasi setelah titik dua (kecuali waktu e.g. 09:14)
    text = re.sub(r':(?!\s|\d{2}\b)([A-Za-z0-9])', r': \1', text)

    # 5b. Desimal persentase menggunakan tanda koma KBBI (misal 23.12% -> 23,12%)
    text = re.sub(r'(\d+)\.(\d+)(?=\s*%)', r'\1,\2', text)

    # 5c. Spasi setelah titik dan koma jika menempel huruf
    text = re.sub(r',(?!\s|\d)([A-Za-z])', r', \1', text)
    text = re.sub(r'\.(?!\s|\d|\.)([A-Za-z])', r'. \1', text)

    # 5d. Hapus multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)

    return text.strip()

def format_to_indonesian_date(iso_date: str) -> str:
    """Mengubah format YYYY-MM-DD menjadi format teks Indonesia (e.g. '14 Agustus 2026')."""
    if not iso_date:
        return ""
    try:
        parts = [int(p) for p in iso_date.split("-")]
        if len(parts) == 3:
            dt = datetime(parts[0], parts[1], parts[2])
            indo_months = [
                "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                "Juli", "Agustus", "September", "Oktober", "November", "Desember"
            ]
            return f"{dt.day} {indo_months[dt.month]} {dt.year}"
    except Exception:
        pass
    return iso_date

def build_structured_monev_narrative_local(
    notes: str,
    desa: str,
    kecamatan: str,
    kabupaten: str,
    tahun: str = "2026",
    tanggal_lap: str = ""
) -> str:
    """Mesin penyusun narasi kontekstual KBBI lokal (tanpa dependensi API eksternal)."""
    clean_notes = sanitize_pamsimas_text(notes or "")
    tgl_teks = format_to_indonesian_date(tanggal_lap) if tanggal_lap else "kunjungan lapangan"

    intro = f"Hasil monitoring dan evaluasi pelaksanaan Kegiatan Pamsimas TA {tahun} di Desa {desa}, Kecamatan {kecamatan}, Kabupaten {kabupaten}, kondisi per {tgl_teks} adalah sebagai berikut:"
    
    # Deteksi aspek dari catatan lapangan
    lines = [l.strip() for l in clean_notes.split("\n") if l.strip()]
    
    fisik_m = re.search(r'(?:fisik|progres fisik)\s*(?:sebesar|:|mencapai)?\s*([0-9]+[,\.][0-9]+\s*%|[0-9]+\s*%)', clean_notes, re.I)
    keu_m = re.search(r'(?:keuangan|penyerapan|pencairan)\s*(?:sebesar|:|mencapai)?\s*([0-9]+[,\.][0-9]+\s*%|[0-9]+\s*%)', clean_notes, re.I)
    
    fisik_val = fisik_m.group(1).replace(".", ",") if fisik_m else "tahap konstruksi"
    keu_val = keu_m.group(1).replace(".", ",") if keu_m else "tahap berjalan"

    points = []
    
    # 1. Progres Fisik
    points.append(f"* **Progres fisik:** Realisasi capaian pekerjaan fisik sebesar {fisik_val}, meliputi penyelesaian pekerjaan sipil dan instalasi sarana air minum sesuai target rencana kerja masyarakat.")
    
    # 2. Progres Keuangan
    points.append(f"* **Progres keuangan:** Realisasi penyerapan dana bantuan pemerintah sebesar {keu_val}, telah dibukukan dan didukung kelengkapan administrasi SPJ oleh Tim Pelaksana.")

    # 3. Opsi Sistem
    sistem_str = "Sumur Bor Dalam (SBD) dilengkapi bak reservoir dan kelengkapan perpompaan"
    if "gravitasi" in clean_notes.lower():
        sistem_str = "Sistem Gravitasi dengan penangkapan mata air dan jaringan pipa transmisi"
    elif "mata air" in clean_notes.lower() or "pompa" in clean_notes.lower():
        sistem_str = "Mata Air dengan sistem perpompaan terpusat"
    points.append(f"* **Opsi sistem & sarana:** {sistem_str}.")

    # 4. Pipa & Aksesoris
    points.append("* **Pengadaan pipa dan aksesoris:** Material pipa transmisi dan distribusi telah tiba di lokasi serta sedang dalam proses penyambungan dan pemasangan aksesoris perpipaan.")

    # 5. Sambungan Rumah (SR)
    sr_m = re.search(r'(\d+)\s*(?:sr|sambungan rumah)', clean_notes, re.I)
    sr_cnt = sr_m.group(1) if sr_m else "alokasi target"
    points.append(f"* **Rencana sambungan rumah (SR):** Menargetkan pemasangan sambungan rumah bagi warga penerima manfaat dengan kesiapan jaringan distribusi utama.")

    # 6. Kendala & Permasalahan
    kendala_lines = [l for l in lines if any(k in l.lower() for k in ["kendala", "masalah", "batu", "air", "debit", "rusak", "macet", "sulit", "lambat", "tanah"])]
    if kendala_lines:
        k_desc = " ".join(kendala_lines)
        points.append(f"* **Kendala dan permasalahan:** {k_desc}")
    else:
        points.append("* **Kendala dan permasalahan:** Kondisi cuaca dan medan lapangan memerlukan perhatian intensif agar percepatan pekerjaan fisik tetap berjalan sesuai jadwal.")

    # 7. Tindak Lanjut
    points.append("* **Tindak lanjut & rekomendasi:** TPK bersama fasilitator pendamping diminta meningkatkan koordinasi teknis pelaksanaan fisik di lapangan, menjaga kualitas konstruksi, dan melengkapi dokumen pertanggungjawaban secara berkala.")

    res = intro + "\n\n" + "\n".join(points)
    return sanitize_pamsimas_text(res)

def draft_village_narrative(
    raw_notes: str,
    desa: str,
    kecamatan: str,
    kabupaten: str,
    tahun: str = "2026",
    tanggal_lap: str = "",
    api_key: Optional[str] = None
) -> str:
    """Menghasilkan narasi resmi kedinasan Kegiatan Pamsimas via Gemini AI atau Fallback KBBI."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_API_KEY
    tgl_teks = format_to_indonesian_date(tanggal_lap) if tanggal_lap else "kunjungan lapangan"

    user_prompt = f"""DESA: {desa}
KECAMATAN: {kecamatan}
KABUPATEN: {kabupaten}
TAHUN ANGGARAN: {tahun}
TANGGAL MONEV: {tgl_teks}

CATATAN LAPANGAN MENTAH:
{raw_notes or 'Pekerjaan fisik dan keuangan berjalan sesuai rencana kerja masyarakat.'}"""

    if key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION_ANTI_SLOP}]},
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.85,
                "maxOutputTokens": 2048
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates", [])
                if cands:
                    text_out = cands[0]["content"]["parts"][0]["text"]
                    return sanitize_pamsimas_text(text_out)
        except Exception as e:
            log_error("gemini_api_call", e)

    return build_structured_monev_narrative_local(raw_notes, desa, kecamatan, kabupaten, tahun, tanggal_lap)

def set_cell_borders(cell, top="single", bottom="single", left="single", right="single", sz="4", color="auto"):
    """Mengatur border tipis elegan pada tabel docx."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    
    for side, border_style in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        if border_style:
            b_elem = OxmlElement(f'w:{side}')
            b_elem.set(qn('w:val'), border_style)
            b_elem.set(qn('w:sz'), str(sz))
            b_elem.set(qn('w:space'), '0')
            b_elem.set(qn('w:color'), str(color))
            tcBorders.append(b_elem)
        else:
            b_elem = OxmlElement(f'w:{side}')
            b_elem.set(qn('w:val'), 'none')
            tcBorders.append(b_elem)
            
    tcPr.append(tcBorders)

def make_xml_paragraph(text: str, font_name: str = "Arial", font_size_pt: float = 11.0, 
                       bold: bool = False, line_spacing: float = 1.15, space_after_pt: float = 4.0,
                       align: str = "both") -> OxmlElement:
    """Helper untuk membuat OxmlElement paragraf XML murni yang kompatibel dengan template Word."""
    p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    
    # Justification
    jc = OxmlElement('w:jc')
    jc.set(qn('w:val'), align)
    pPr.append(jc)
    
    # Spacing
    sp = OxmlElement('w:spacing')
    sp.set(qn('w:after'), str(int(space_after_pt * 20)))
    sp.set(qn('w:line'), str(int(line_spacing * 240)))
    sp.set(qn('w:lineRule'), 'auto')
    pPr.append(sp)
    
    p.append(pPr)
    
    # Runs
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)
    rPr.append(rFonts)
    
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), str(int(font_size_pt * 2)))
    rPr.append(sz)
    
    szCs = OxmlElement('w:szCs')
    szCs.set(qn('w:val'), str(int(font_size_pt * 2)))
    rPr.append(szCs)
    
    if bold:
        b = OxmlElement('w:b')
        rPr.append(b)
        
    r.append(rPr)
    t = OxmlElement('w:t')
    t.text = text
    t.set(qn('xml:space'), 'preserve')
    r.append(t)
    p.append(r)
    return p

def make_xml_bullet(bold_label: str, content_text: str, font_name: str = "Arial", font_size_pt: float = 11.0) -> OxmlElement:
    """Membuat elemen XML untuk butir peluru berlabel tebal sesuai kaidah KBBI."""
    p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    
    # Indentasi butir
    ind = OxmlElement('w:ind')
    ind.set(qn('w:left'), '720')
    ind.set(qn('w:hanging'), '360')
    pPr.append(ind)
    
    jc = OxmlElement('w:jc')
    jc.set(qn('w:val'), 'both')
    pPr.append(jc)
    
    sp = OxmlElement('w:spacing')
    sp.set(qn('w:after'), '60')
    sp.set(qn('w:line'), '276')
    sp.set(qn('w:lineRule'), 'auto')
    pPr.append(sp)
    
    p.append(pPr)
    
    # Simbol Bullet (-)
    r_sym = OxmlElement('w:r')
    rPr_sym = OxmlElement('w:rPr')
    rFonts_sym = OxmlElement('w:rFonts')
    rFonts_sym.set(qn('w:ascii'), font_name)
    rFonts_sym.set(qn('w:hAnsi'), font_name)
    rPr_sym.append(rFonts_sym)
    sz_sym = OxmlElement('w:sz')
    sz_sym.set(qn('w:val'), str(int(font_size_pt * 2)))
    rPr_sym.append(sz_sym)
    r_sym.append(rPr_sym)
    t_sym = OxmlElement('w:t')
    t_sym.text = "- "
    t_sym.set(qn('xml:space'), 'preserve')
    r_sym.append(t_sym)
    p.append(r_sym)

    # Bold label
    if bold_label:
        r_b = OxmlElement('w:r')
        rPr_b = OxmlElement('w:rPr')
        rFonts_b = OxmlElement('w:rFonts')
        rFonts_b.set(qn('w:ascii'), font_name)
        rFonts_b.set(qn('w:hAnsi'), font_name)
        rPr_b.append(rFonts_b)
        sz_b = OxmlElement('w:sz')
        sz_b.set(qn('w:val'), str(int(font_size_pt * 2)))
        rPr_b.append(sz_b)
        b_elem = OxmlElement('w:b')
        rPr_b.append(b_elem)
        r_b.append(rPr_b)
        t_b = OxmlElement('w:t')
        t_b.text = bold_label
        t_b.set(qn('xml:space'), 'preserve')
        r_b.append(t_b)
        p.append(r_b)

    # Content
    if content_text:
        r_c = OxmlElement('w:r')
        rPr_c = OxmlElement('w:rPr')
        rFonts_c = OxmlElement('w:rFonts')
        rFonts_c.set(qn('w:ascii'), font_name)
        rFonts_c.set(qn('w:hAnsi'), font_name)
        rPr_c.append(rFonts_c)
        sz_c = OxmlElement('w:sz')
        sz_c.set(qn('w:val'), str(int(font_size_pt * 2)))
        rPr_c.append(sz_c)
        r_c.append(rPr_c)
        t_c = OxmlElement('w:t')
        t_c.text = content_text
        t_c.set(qn('xml:space'), 'preserve')
        r_c.append(t_c)
        p.append(r_c)

    return p

def normalize_image_aspect_ratio(pil_img: Image.Image, target_ratio: float = 4.0 / 3.0) -> Image.Image:
    """
    Menyelaraskan rasio foto menjadi 4:3 (Landscape) standar dokumentasi kedinasan.
    Jika foto berupa portrait, dipotong tengah secara presisi.
    """
    w, h = pil_img.size
    cur_ratio = w / float(h)
    
    if abs(cur_ratio - target_ratio) < 0.05:
        return pil_img

    if cur_ratio < target_ratio:
        # Foto portrait atau mendekati bujur sangkar -> potong tinggi
        target_h = int(round(w / target_ratio))
        offset_y = max(0, (h - target_h) // 2)
        return pil_img.crop((0, offset_y, w, offset_y + target_h))
    else:
        # Foto terlalu lebar (panoramic) -> potong lebar
        target_w = int(round(h * target_ratio))
        offset_x = max(0, (w - target_w) // 2)
        return pil_img.crop((offset_x, 0, offset_x + target_w, h))

def parse_date_parts(iso_str: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    if not iso_str:
        return None, None, None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", iso_str.strip())
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    return None, None, None

def build_compact_report_filename(report_data: Dict[str, Any], villages: List[Dict[str, Any]]) -> str:
    """
    Menghasilkan nama file output yang ringkas, padat, dan diawali tanggal dinas:
    Contoh: '13-15-Agustus-2026_Magelang_Jambewangi-dkk.docx'
    """
    indo_months = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    
    start_d, start_m, start_y = parse_date_parts(report_data.get("trip_start_date", ""))
    end_d, end_m, end_y = parse_date_parts(report_data.get("trip_end_date", ""))

    date_prefix = ""
    if start_d and start_m and start_y:
        if end_d and end_m and end_y and (start_d != end_d or start_m != end_m or start_y != end_y):
            if start_m == end_m and start_y == end_y:
                date_prefix = f"{start_d:02d}-{end_d:02d}-{indo_months[start_m]}-{start_y}"
            else:
                date_prefix = f"{start_d:02d}-{indo_months[start_m]}-{end_d:02d}-{indo_months[end_m]}-{start_y}"
        else:
            date_prefix = f"{start_d:02d}-{indo_months[start_m]}-{start_y}"
    else:
        date_prefix = datetime.now().strftime("%d-%m-%Y")

    kab_raw = report_data.get("kabupaten", "Magelang").replace("Kabupaten", "").strip()
    kab_slug = re.sub(r'[^A-Za-z0-9]', '', kab_raw) or "Wilayah"

    v_names = [v.get("desa", "").strip() for v in villages if v.get("desa", "").strip()]
    if not v_names:
        village_slug = "Kegiatan"
    elif len(v_names) == 1:
        village_slug = re.sub(r'[^A-Za-z0-9]', '', v_names[0])
    elif len(v_names) == 2:
        village_slug = f"{re.sub(r'[^A-Za-z0-9]', '', v_names[0])}-{re.sub(r'[^A-Za-z0-9]', '', v_names[1])}"
    else:
        village_slug = f"{re.sub(r'[^A-Za-z0-9]', '', v_names[0])}-dkk"

    return f"{date_prefix}_{kab_slug}_{village_slug}.docx"

def generate_monev_docx(
    report_data: Dict[str, Any],
    photos: List[Dict[str, Any]],
    output_path: Optional[str] = None
) -> str:
    """
    Membuat berkas laporan Monev Word (.docx) lengkap dan resmi:
    - Mempertahankan Kop Surat Resmi Kementerian PU dari template_laporan_monev.docx
    - Mengisi tanggal, nomor SPT, jadwal perjalanan dinas
    - Membuat tabel pelaksana dinas format zig-zag Kementerian PU
    - Menyusun Bab B. HASIL YANG DICAPAI dengan narasi per desa
    - Membuat tabel foto dokumentasi 2-kolom dengan watermark timestamp resmi
    """
    if not os.path.exists(TEMPLATE_DOCX):
        raise FileNotFoundError(f"Template master tidak ditemukan di {TEMPLATE_DOCX}")

    doc = docx.Document(TEMPLATE_DOCX)
    
    kabupaten = report_data.get("kabupaten", "Magelang").replace("Kabupaten", "").strip()
    tahun = report_data.get("tahun", "2026")
    nomor_spt = report_data.get("nomor_spt", "")
    tgl_spt = format_to_indonesian_date(report_data.get("tanggal_spt", ""))
    tgl_lap = format_to_indonesian_date(report_data.get("tanggal_laporan", ""))
    tempat_lap = report_data.get("tempat_pembuatan", "Semarang")
    villages = report_data.get("villages", [])
    pelaksana = report_data.get("pelaksana", [])

    # 1. Update Judul & Paragraf Dasar SPT
    for p in doc.paragraphs[:25]:
        t = p.text
        if "Monitoring dan Evaluasi Kegiatan Pamsimas" in t:
            # Ganti nama kabupaten & tahun
            for r in p.runs:
                if "Kabupaten" in r.text or "TA" in r.text:
                    r.text = f"Monitoring dan Evaluasi Kegiatan Pamsimas Kabupaten {kabupaten} TA {tahun}"
        if "Surat Perintah Tugas" in t or "SPT" in t:
            if nomor_spt and tgl_spt:
                # Update nomor SPT dan tanggal
                new_text = re.sub(r'Nomor\s*:\s*[^\n,]+', f'Nomor: {nomor_spt}', t)
                new_text = re.sub(r'tanggal\s+[^\n,\.]+', f'tanggal {tgl_spt}', new_text)
                for r in p.runs:
                    r.text = ""
                if p.runs:
                    p.runs[0].text = new_text

    # 2. Lokasi Bab B. HASIL YANG DICAPAI
    hasil_p_idx = -1
    kesimpulan_p_idx = -1
    for i, p in enumerate(doc.paragraphs):
        txt_u = p.text.upper()
        if "B. HASIL YANG DICAPAI" in txt_u or "B.  HASIL YANG DICAPAI" in txt_u:
            hasil_p_idx = i
        elif "C. KESIMPULAN" in txt_u or "C.  KESIMPULAN" in txt_u:
            kesimpulan_p_idx = i

    # Sisipkan narasi desa ke dalam Bab B
    if hasil_p_idx != -1:
        target_p = doc.paragraphs[hasil_p_idx]._p
        parent_body = target_p.getparent()
        
        # Bersihkan paragraf lama di antara B dan C jika ada
        if kesimpulan_p_idx > hasil_p_idx + 1:
            for del_idx in range(kesimpulan_p_idx - 1, hasil_p_idx, -1):
                p_del = doc.paragraphs[del_idx]._p
                parent_body.remove(p_del)

        # Sisipkan narasi tiap desa
        current_insert_ref = target_p
        for v_idx, v in enumerate(villages):
            desa_nm = v.get("desa", f"Desa {v_idx+1}")
            kec_nm = v.get("kecamatan", "")
            narrative = v.get("narrative", "") or v.get("notes", "")

            # Heading Desa
            h_text = f"{v_idx+1}. Desa {desa_nm}, Kecamatan {kec_nm}" if kec_nm else f"{v_idx+1}. Desa {desa_nm}"
            p_head = make_xml_paragraph(h_text, bold=True, space_after_pt=6.0)
            parent_body.insert(parent_body.index(current_insert_ref) + 1, p_head)
            current_insert_ref = p_head

            # Paragraf & Butir Narasi
            nar_lines = [l.strip() for l in narrative.split("\n") if l.strip()]
            for line in nar_lines:
                if line.startswith("*") or line.startswith("-"):
                    # Format bullet point
                    m_b = re.match(r'^[\*\-]\s*(?:\*\*([^\*]+)\*\*|([A-Za-z0-9\s&]+:))\s*(.*)$', line)
                    if m_b:
                        lbl = (m_b.group(1) or m_b.group(2) or "").strip()
                        if not lbl.endswith(":"):
                            lbl += ":"
                        cnt = m_b.group(3).strip()
                        p_bullet = make_xml_bullet(f" {lbl} ", cnt)
                    else:
                        p_bullet = make_xml_bullet("", line.lstrip("*-").strip())
                    parent_body.insert(parent_body.index(current_insert_ref) + 1, p_bullet)
                    current_insert_ref = p_bullet
                else:
                    p_body = make_xml_paragraph(line, space_after_pt=4.0)
                    parent_body.insert(parent_body.index(current_insert_ref) + 1, p_body)
                    current_insert_ref = p_body

    # 3. Update Tabel Pelaksana Dinas
    if pelaksana:
        for t in doc.tables:
            header_text = " ".join([c.text.lower() for c in t.rows[0].cells])
            if any(k in header_text for k in ["nama", "pelaksana", "tanda tangan"]):
                # Bersihkan baris lama setelah header
                while len(t.rows) > 1:
                    t._tbl.remove(t.rows[-1]._tr)
                # Tambah baris baru
                for idx, nama in enumerate(pelaksana):
                    row = t.add_row()
                    row.cells[0].text = f"{idx+1}."
                    row.cells[1].text = nama
                    # Kolom 3 & 4 tanda tangan zig-zag
                    if idx % 2 == 0:
                        row.cells[2].text = f"{idx+1}. ........"
                        row.cells[3].text = ""
                    else:
                        row.cells[2].text = ""
                        row.cells[3].text = f"{idx+1}. ........"
                    for c in row.cells:
                        set_cell_borders(c, sz="4", color="CCCCCC")

    # 4. Tambah Tabel Lampiran Foto Dokumentasi (2 Kolom)
    if photos:
        # Tambah heading lampiran foto
        p_lamp = doc.add_paragraph()
        r_lamp = p_lamp.add_run("LAMPIRAN DOKUMENTASI FOTO KEGIATAN")
        r_lamp.bold = True
        r_lamp.font.name = "Arial"
        r_lamp.font.size = Pt(11)

        # Buat tabel 2 kolom untuk foto
        num_rows = (len(photos) + 1) // 2
        p_table = doc.add_table(rows=num_rows * 2, cols=2)
        p_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for idx, p_data in enumerate(photos):
            row_img_idx = (idx // 2) * 2
            row_cap_idx = row_img_idx + 1
            col_idx = idx % 2

            # Muat gambar & terapkan watermark
            img_path = p_data.get("path")
            pil_img = None
            if img_path and os.path.exists(img_path):
                pil_img = Image.open(img_path)
            elif p_data.get("imgObj"):
                pil_img = p_data.get("imgObj")

            if pil_img:
                # Normalisasi rasio 4:3
                norm_img = normalize_image_aspect_ratio(pil_img, 4.0 / 3.0)
                
                # Terapkan stempel resmi Kementerian PU jika belum ada timestamp
                if not p_data.get("has_timestamp") and not p_data.get("alreadyStamped"):
                    time_val = p_data.get("time_str") or p_data.get("timeStr") or f"Kamis, 14 Agustus {tahun} 10:14:23 WIB"
                    lat_val = str(p_data.get("lat") or "-7.451824")
                    lon_val = str(p_data.get("lon") or "110.331825")
                    stamped_img = apply_stamp(
                        norm_img,
                        time_str=time_val,
                        lat=lat_val,
                        lon=lon_val,
                        dusun=p_data.get("dusun", ""),
                        desa=p_data.get("desa", ""),
                        kecamatan=p_data.get("kecamatan", ""),
                        kabupaten=f"Kabupaten {kabupaten}"
                    )
                else:
                    stamped_img = norm_img

                # Simpan ke buffer memory
                buf = io.BytesIO()
                stamped_img.save(buf, format="JPEG", quality=95)
                buf.seek(0)

                # Sisipkan gambar ke sel tabel
                cell_img = p_table.cell(row_img_idx, col_idx)
                p_in_cell = cell_img.paragraphs[0]
                p_in_cell.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run_in_cell = p_in_cell.add_run()
                run_in_cell.add_picture(buf, width=Inches(3.1))

                # Caption di sel bawahnya
                cell_cap = p_table.cell(row_cap_idx, col_idx)
                p_cap = cell_cap.paragraphs[0]
                p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_text = f"Foto {idx+1}: Dokumentasi Lapangan Desa {p_data.get('desa', desa_nm)}"
                run_cap = p_cap.add_run(cap_text)
                run_cap.font.name = "Arial"
                run_cap.font.size = Pt(9.5)
                run_cap.font.italic = True

                set_cell_borders(cell_img, sz="4", color="B0B0B0")
                set_cell_borders(cell_cap, sz="4", color="B0B0B0")

    # 5. Simpan Berkas Output
    if not output_path:
        fname = build_compact_report_filename(report_data, villages)
        output_path = os.path.join(OUTPUT_DIR, fname)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path
