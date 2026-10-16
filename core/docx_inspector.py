import os
import io
import re
import uuid
import zipfile
import docx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

from core.config import UPLOADS_DIR, TEMP_MEDIA_DIR
from core.logger import log_error
from core.location_service import lookup_location, fuzzy_match_village
from core.stamp_detector import detect_timestamp

def parse_indo_date_to_iso(text: str) -> str:
    """Mengonversi teks tanggal Indonesia (misal '18 September 2026') ke format ISO '2026-09-18'."""
    if not text:
        return ""
    m_range = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if m_range:
        day = int(m_range.group(1))
        m_str = m_range.group(3).lower()
        year = int(m_range.group(4))
    else:
        m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
        if not m:
            return ""
        day = int(m.group(1))
        m_str = m.group(2).lower()
        year = int(m.group(3))

    indo_month_map = {
        'januari': 1, 'jan': 1, 'februari': 2, 'feb': 2, 'maret': 3, 'mar': 3,
        'april': 4, 'apr': 4, 'mei': 5, 'juni': 6, 'jun': 6, 'juli': 7, 'jul': 7,
        'agustus': 8, 'agt': 8, 'agust': 8, 'september': 9, 'sep': 9, 'sept': 9,
        'oktober': 10, 'okt': 10, 'november': 11, 'nov': 11, 'desember': 12, 'des': 12
    }
    if m_str in indo_month_map:
        month = indo_month_map[m_str]
        return f"{year:04d}-{month:02d}-{day:02d}"
    return ""

def get_hplus1_iso(iso_date: str) -> str:
    """Menghitung tanggal H+1 dari tanggal ISO YYYY-MM-DD."""
    if not iso_date:
        return ""
    try:
        parts = [int(p) for p in iso_date.split("-")]
        d = datetime(parts[0], parts[1], parts[2]) + timedelta(days=1)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return ""

def _safe_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default

def extract_docx_photos(docx_path: str) -> List[Dict[str, Any]]:
    """Mengekstrak gambar dari berkas .docx beserta deteksi timestamp dan crop DrawingML."""
    photos = []
    session_id = uuid.uuid4().hex[:10]
    out_dir = os.path.join(TEMP_MEDIA_DIR, session_id)
    os.makedirs(out_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(docx_path, "r") as zin:
            namelist = zin.namelist()
            media_files = [n for n in namelist if n.startswith("word/media/")]
            
            def sort_key(name):
                m = re.search(r"image(\d+)", name)
                return int(m.group(1)) if m else 999
            media_files.sort(key=sort_key)

            # Relasi gambar ke DrawingML
            rel_map = {}
            if "word/_rels/document.xml.rels" in namelist:
                rels_xml = zin.read("word/_rels/document.xml.rels").decode("utf-8", errors="ignore")
                for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels_xml):
                    rel_map[m.group(1)] = m.group(2)

            crop_map = {}
            if "word/document.xml" in namelist:
                root = ET.fromstring(zin.read("word/document.xml"))
                for elem in root.iter():
                    if elem.tag.endswith('blipFill'):
                        blip = None
                        srcRect = None
                        for child in elem:
                            if child.tag.endswith('blip'):
                                blip = child
                            elif child.tag.endswith('srcRect'):
                                srcRect = child
                        if blip is not None and srcRect is not None and srcRect.attrib:
                            embed = blip.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                            target = rel_map.get(embed, '')
                            bname = os.path.basename(target)
                            if bname:
                                crop_map[bname] = {
                                    'l': _safe_int(srcRect.attrib.get('l', 0)),
                                    't': _safe_int(srcRect.attrib.get('t', 0)),
                                    'r': _safe_int(srcRect.attrib.get('r', 0)),
                                    'b': _safe_int(srcRect.attrib.get('b', 0)),
                                }

            for idx, mf in enumerate(media_files):
                bname = os.path.basename(mf)
                ext = os.path.splitext(bname)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                    continue
                
                raw_bytes = zin.read(mf)
                # Terapkan crop jika ada info srcRect DrawingML
                img_obj = None
                try:
                    pil_img = Image.open(io.BytesIO(raw_bytes))
                    if bname in crop_map:
                        cm = crop_map[bname]
                        w, h = pil_img.size
                        l_px = int(w * (cm['l'] / 100000.0))
                        t_px = int(h * (cm['t'] / 100000.0))
                        r_px = int(w * (1.0 - (cm['r'] / 100000.0)))
                        b_px = int(h * (1.0 - (cm['b'] / 100000.0)))
                        if r_px > l_px and b_px > t_px:
                            pil_img = pil_img.crop((l_px, t_px, r_px, b_px))
                    img_obj = pil_img
                except Exception:
                    pass

                # Simpan gambar ke file sementara
                local_fname = f"extracted_{idx+1}_{bname}"
                local_path = os.path.join(out_dir, local_fname)
                if img_obj:
                    if img_obj.mode in ("RGBA", "P"):
                        img_obj = img_obj.convert("RGB")
                    img_obj.save(local_path, format="JPEG", quality=95)
                else:
                    with open(local_path, "wb") as f_out:
                        f_out.write(raw_bytes)

                # Deteksi timestamp bawaan
                stamp_meta = detect_timestamp(local_path)
                photos.append({
                    "id": f"p_{idx+1}",
                    "filename": local_fname,
                    "path": local_path,
                    "has_timestamp": stamp_meta.get("has_timestamp", False),
                    "suggested_crop_bottom": stamp_meta.get("suggested_crop_bottom", 0.18),
                    "desa": "",
                    "kecamatan": "",
                    "dusun": "",
                    "lat": None,
                    "lon": None
                })
    except Exception as e:
        log_error("extract_docx_photos", e)

    return photos

def inspect_and_import_monev_docx(docx_path: str) -> Dict[str, Any]:
    """
    Menganalisis dokumen Monev Word eksisting (.docx), mengekstrak data administrasi,
    jadwal dinas, tabel pelaksana, daftar desa beserta narasi capaian, dan galeri foto,
    serta menghasilkan laporan audit kelengkapan dokumen.
    """
    if not os.path.exists(docx_path):
        return {"success": False, "error": f"File tidak ditemukan: {docx_path}"}

    doc = docx.Document(docx_path)
    filename = os.path.basename(docx_path)

    # 1. Judul & Kabupaten
    kabupaten = ""
    tahun = "2026"
    for p in doc.paragraphs[:15]:
        t = p.text.strip()
        m_title = re.search(r"Monitoring dan Evaluasi Kegiatan Pamsimas\s+(?:Kabupaten|Kota)?\s*([A-Za-z\s]+?)\s+TA\s*(\d{4})", t, re.I)
        if m_title:
            kabupaten = m_title.group(1).strip()
            tahun = m_title.group(2).strip()
            break
    if not kabupaten:
        m_fn = re.search(r"Kabupaten\s+([A-Za-z]+)", filename, re.I)
        if m_fn:
            kabupaten = m_fn.group(1).strip()
    if not kabupaten:
        m_fn2 = re.search(r"-\s*([A-Za-z]+)(?:\.docx|\s*\()", filename)
        if m_fn2 and m_fn2.group(1).lower() not in ["geotagged", "monev", "laporan"]:
            kabupaten = m_fn2.group(1).strip()

    # 2. Nomor & Tanggal SPT
    nomor_spt = ""
    tanggal_spt_raw = ""
    for p in doc.paragraphs[:50]:
        t = p.text.strip()
        m_spt = re.search(r"\b(CK\d+[A-Za-z0-9\/\-\.]+202\d[A-Za-z0-9\/\-\.]*)\b", t)
        if m_spt and not nomor_spt:
            nomor_spt = m_spt.group(1).strip()
        m_tspt = re.search(r"tanggal\s+([0-9]{1,2}(?:\s*[-–—]\s*[0-9]{1,2})?\s+[A-Za-z]+\s+[0-9]{4})", t, re.I)
        if m_tspt and not tanggal_spt_raw:
            tanggal_spt_raw = m_tspt.group(1).strip()

    tanggal_spt_iso = parse_indo_date_to_iso(tanggal_spt_raw)

    # 3. Tanggal Laporan & Dibuat di
    tempat_pembuatan = "Semarang"
    tanggal_laporan_raw = ""
    for p in doc.paragraphs[-35:]:
        t = p.text.strip()
        m_tempat = re.search(r"Dibuat di\s+([A-Za-z]+)", t, re.I)
        if m_tempat:
            tempat_pembuatan = m_tempat.group(1).strip()
        m_tlap = re.search(r"pada tanggal\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", t, re.I)
        if m_tlap:
            tanggal_laporan_raw = m_tlap.group(1).strip()

    tanggal_laporan_iso = parse_indo_date_to_iso(tanggal_laporan_raw)

    # 4. Tanggal Dinas (Mulai & Selesai)
    trip_start_iso = ""
    trip_end_iso = ""
    combined_date_src = filename + " " + tanggal_spt_raw
    m_trip = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", combined_date_src)
    if m_trip:
        trip_start_iso = parse_indo_date_to_iso(f"{m_trip.group(1)} {m_trip.group(3)} {m_trip.group(4)}")
        trip_end_iso = parse_indo_date_to_iso(f"{m_trip.group(2)} {m_trip.group(3)} {m_trip.group(4)}")
    else:
        m_single = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", combined_date_src)
        if m_single:
            trip_start_iso = parse_indo_date_to_iso(f"{m_single.group(1)} {m_single.group(2)} {m_single.group(3)}")

    # Otomatisasi H+1 jika Tanggal Laporan belum ada di dokumen
    auto_hplus1 = False
    if not tanggal_laporan_iso:
        last_dinas = trip_end_iso or trip_start_iso
        if last_dinas:
            tanggal_laporan_iso = get_hplus1_iso(last_dinas)
            auto_hplus1 = True

    # 5. Tabel Pelaksana
    pelaksana = []
    has_pelaksana_table = False
    for t in doc.tables:
        header_text = " ".join([c.text.lower() for c in t.rows[0].cells])
        if any(k in header_text for k in ["nama", "pelaksana", "tanda tangan", "ttd", "jabatan"]):
            has_pelaksana_table = True
            for r in t.rows[1:]:
                c_texts = [c.text.strip() for c in r.cells if c.text.strip()]
                for val in c_texts:
                    if not re.match(r"^\d+\.?$", val) and len(val) > 3 and not re.search(r"^\d+\.\s*$", val):
                        if val not in pelaksana and not any(k in val.lower() for k in ["tanda tangan", "jabatan", "nip"]):
                            pelaksana.append(val)
                        break
        elif len(t.columns) == 4 and len(t.rows) >= 1:
            first_row = [c.text.strip() for c in t.rows[0].cells]
            if re.match(r"^\d+\.", first_row[0]) and len(first_row[1]) > 3:
                has_pelaksana_table = True
                for r in t.rows:
                    name_val = r.cells[1].text.strip()
                    if name_val and name_val not in pelaksana:
                        pelaksana.append(name_val)

    # 6. Parse Photos
    parsed_photos = extract_docx_photos(docx_path)

    # 7. Section B. Hasil yang Dicapai (Desa & Narasi)
    villages = []
    current_desa = None
    current_narrative_paras = []
    in_hasil_section = False

    for p in doc.paragraphs:
        txt = p.text.strip()
        if "B. HASIL YANG DICAPAI" in txt.upper():
            in_hasil_section = True
            continue
        if any(k in txt.upper() for k in ["C. KESIMPULAN", "PENUTUP", "DOKUMENTASI KEGIATAN", "LAMPIRAN FOTO"]):
            if current_desa:
                current_desa["narrative"] = "\n".join(current_narrative_paras).strip()
                current_desa["notes"] = current_desa["narrative"]
                villages.append(current_desa)
                current_desa = None
                current_narrative_paras = []
            break

        if in_hasil_section and txt:
            m_des = re.search(r"(?:^\d+[\.\)]\s*)?Desa\s+([A-Za-z0-9]+)(?:\s+(?:Kecamatan|Kec\.?)\s+([A-Za-z0-9]+))?", txt, re.I)
            is_heading = m_des and (len(txt.split()) <= 6 or p.style.name.startswith("Heading") or any(r.bold for r in p.runs[:2]))
            if is_heading:
                if current_desa:
                    current_desa["narrative"] = "\n".join(current_narrative_paras).strip()
                    current_desa["notes"] = current_desa["narrative"]
                    villages.append(current_desa)
                    current_narrative_paras = []
                desa_name = fuzzy_match_village(m_des.group(1).strip())
                kec_name = m_des.group(2).strip() if m_des.group(2) else ""
                if not kec_name:
                    _, _, looked_kec, _ = lookup_location(desa_name, "", kabupaten)
                    kec_name = looked_kec
                current_desa = {
                    "id": f"v_{desa_name.lower()}",
                    "desa": desa_name,
                    "kecamatan": kec_name,
                    "notes": "",
                    "narrative": ""
                }
            elif current_desa:
                current_narrative_paras.append(txt)

    if current_desa:
        current_desa["narrative"] = "\n".join(current_narrative_paras).strip()
        current_desa["notes"] = current_desa["narrative"]
        villages.append(current_desa)

    # Jika belum ada desa dari heading B, cari di paragraf atau tabel
    if not villages:
        villages.append({
            "id": "v_init",
            "desa": "",
            "kecamatan": "",
            "notes": "",
            "narrative": ""
        })

    # Petakan desa ke foto jika ada
    if len(villages) == 1 and villages[0].get("desa"):
        v_only = villages[0]["desa"]
        k_only = villages[0]["kecamatan"]
        for p in parsed_photos:
            p["desa"] = v_only
            p["kecamatan"] = k_only
            _, _, _, kab_val = lookup_location(v_only, k_only, kabupaten)
            p["kabupaten"] = kab_val

    # 8. Checklist Audit Kelengkapan Dokumen
    audit_items = calculate_audit_items(
        kabupaten=kabupaten,
        nomor_spt=nomor_spt,
        tanggal_spt_iso=tanggal_spt_iso,
        tanggal_spt_raw=tanggal_spt_raw,
        trip_start_iso=trip_start_iso,
        trip_end_iso=trip_end_iso,
        tanggal_laporan_iso=tanggal_laporan_iso,
        tanggal_laporan_raw=tanggal_laporan_raw,
        auto_hplus1=auto_hplus1,
        pelaksana=pelaksana,
        villages=villages,
        photos=parsed_photos
    )

    completed_cnt = sum(1 for a in audit_items if a["status"] == "complete")
    total_cnt = len(audit_items)
    score_pct = int((completed_cnt / total_cnt) * 100)
    summary_text = f"Dokumen berhasil dibuka ({score_pct}% Terisi). {completed_cnt} data terisi lengkap, {total_cnt - completed_cnt} data belum lengkap dan siap dilengkapi."

    return {
        "success": True,
        "filename": filename,
        "report_data": {
            "kabupaten": kabupaten,
            "tahun": tahun,
            "nomor_spt": nomor_spt,
            "tanggal_spt": tanggal_spt_iso,
            "tanggal_laporan": tanggal_laporan_iso,
            "tempat_pembuatan": tempat_pembuatan,
            "trip_start_date": trip_start_iso,
            "trip_end_date": trip_end_iso,
            "include_pelaksana": has_pelaksana_table and len(pelaksana) > 0,
            "pelaksana": pelaksana,
            "villages": villages
        },
        "photos": parsed_photos,
        "audit_report": {
            "score_percent": score_pct,
            "completed_count": completed_cnt,
            "incomplete_count": total_cnt - completed_cnt,
            "summary": summary_text,
            "items": audit_items
        }
    }

def calculate_audit_items(
    kabupaten: str,
    nomor_spt: str,
    tanggal_spt_iso: str,
    tanggal_spt_raw: str,
    trip_start_iso: str,
    trip_end_iso: str,
    tanggal_laporan_iso: str,
    tanggal_laporan_raw: str,
    auto_hplus1: bool,
    pelaksana: List[str],
    villages: List[Dict[str, Any]],
    photos: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Menghasilkan 8 butir checklist audit kelengkapan dokumen laporan."""
    audit_items = []

    # 1. Kabupaten
    if kabupaten:
        audit_items.append({"field": "kabupaten", "status": "complete", "label": "Kabupaten", "message": f"Terdeteksi: Kabupaten {kabupaten}"})
    else:
        audit_items.append({"field": "kabupaten", "status": "incomplete", "label": "Kabupaten", "message": "Belum terdeteksi di dokumen"})

    # 2. Nomor SPT
    if nomor_spt:
        audit_items.append({"field": "nomor_spt", "status": "complete", "label": "Nomor SPT", "message": f"Terdeteksi: {nomor_spt}"})
    else:
        audit_items.append({"field": "nomor_spt", "status": "incomplete", "label": "Nomor SPT", "message": "Belum tercantum di dokumen"})

    # 3. Tanggal SPT
    if tanggal_spt_iso:
        audit_items.append({"field": "tanggal_spt", "status": "complete", "label": "Tanggal SPT", "message": f"Terdeteksi: {tanggal_spt_raw or tanggal_spt_iso}"})
    else:
        audit_items.append({"field": "tanggal_spt", "status": "incomplete", "label": "Tanggal SPT", "message": "Belum tercantum di dokumen"})

    # 4. Jadwal Dinas
    if trip_start_iso:
        trip_txt = f"{trip_start_iso} s/d {trip_end_iso}" if trip_end_iso and trip_end_iso != trip_start_iso else f"{trip_start_iso} (1 Hari)"
        audit_items.append({"field": "trip_dates", "status": "complete", "label": "Jadwal Dinas", "message": f"Terdeteksi: {trip_txt}"})
    else:
        audit_items.append({"field": "trip_dates", "status": "incomplete", "label": "Jadwal Dinas", "message": "Belum tercantum di dokumen"})

    # 5. Tanggal Laporan
    if auto_hplus1:
        audit_items.append({"field": "tanggal_laporan", "status": "incomplete", "label": "Tanggal Laporan", "message": f"Belum ada di dokumen (Otomatis diset default H+1 Dinas: {tanggal_laporan_iso})"})
    elif tanggal_laporan_iso:
        audit_items.append({"field": "tanggal_laporan", "status": "complete", "label": "Tanggal Laporan", "message": f"Terdeteksi: {tanggal_laporan_raw or tanggal_laporan_iso}"})
    else:
        audit_items.append({"field": "tanggal_laporan", "status": "incomplete", "label": "Tanggal Laporan", "message": "Belum tercantum di dokumen"})

    # 6. Tabel Pelaksana
    if len(pelaksana) > 0:
        audit_items.append({"field": "pelaksana", "status": "complete", "label": "Tabel Pelaksana", "message": f"Ditemukan {len(pelaksana)} personil pelaksana dinas"})
    else:
        audit_items.append({"field": "pelaksana", "status": "incomplete", "label": "Tabel Pelaksana", "message": "Belum ada tabel personil / tanda tangan pelaksana dinas"})

    # 7. Desa & Narasi
    valid_villages = [v for v in villages if v.get("desa")]
    if len(valid_villages) > 0:
        has_narrative = any(len(v.get("narrative", "") or v.get("notes", "")) > 30 for v in valid_villages)
        v_names = ", ".join([v["desa"] for v in valid_villages[:3]]) + ("..." if len(valid_villages) > 3 else "")
        if has_narrative:
            audit_items.append({"field": "villages", "status": "complete", "label": "Desa & Narasi", "message": f"Ditemukan {len(valid_villages)} desa ({v_names}) beserta catatan capaian"})
        else:
            audit_items.append({"field": "villages", "status": "incomplete", "label": "Desa & Narasi", "message": f"Ditemukan {len(valid_villages)} desa ({v_names}), namun uraian narasi masih kosong"})
    else:
        audit_items.append({"field": "villages", "status": "incomplete", "label": "Desa & Narasi", "message": "Belum ada desa yang teridentifikasi"})

    # 8. Foto Dokumentasi
    if len(photos) > 0:
        stamped_cnt = sum(1 for p in photos if p.get("has_timestamp") or p.get("alreadyStamped"))
        if stamped_cnt == len(photos):
            audit_items.append({"field": "photos", "status": "complete", "label": "Foto Dokumentasi", "message": f"Ditemukan {len(photos)} foto (seluruh foto telah memiliki timestamp)"})
        elif stamped_cnt > 0:
            audit_items.append({"field": "photos", "status": "incomplete", "label": "Foto Dokumentasi", "message": f"Ditemukan {len(photos)} foto ({stamped_cnt} foto bertimestamp, {len(photos)-stamped_cnt} foto belum bertimestamp)"})
        else:
            audit_items.append({"field": "photos", "status": "incomplete", "label": "Foto Dokumentasi", "message": f"Ditemukan {len(photos)} foto di dokumen (BELUM memiliki timestamp GPS)"})
    else:
        audit_items.append({"field": "photos", "status": "incomplete", "label": "Foto Dokumentasi", "message": "Belum ada foto dokumentasi lapangan di dalam dokumen"})

    return audit_items
