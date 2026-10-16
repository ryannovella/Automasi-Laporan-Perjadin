# Agent Guidelines & Operational Rules (Automasi Laporan Perjadin)

Petunjuk operasional agen AI untuk memelihara aplikasi Streamlit Automasi Laporan Perjalanan Dinas Monev Pamsimas.

---

## 1. Arsitektur Proyek
- Framework UI: **Streamlit** (`app.py`).
- Engine Dokumen: `core/report_generator.py` dan `core/docx_inspector.py` (berbasis `python-docx` dan XML OpenXML).
- Computer Vision: `core/stamp_detector.py` (OpenCV) dan `core/stamper.py` (Pillow).
- Master Data: `data/data_lokasi.csv` (Wilayah Jawa Tengah) dan `data/Nama Personel.txt` (Personel BPBPK).
- Template Resmi: `templates/template_laporan_monev.docx`.

---

## 2. Aturan Kritis Domain
1. **Nomenklatur Resmi**: Selalu gunakan **Kementerian PU** (Kementerian Pekerjaan Umum). Jangan gunakan 'PUPR', 'Kementerian PUPR', atau 'Program Pamsimas' (wajib 'Kegiatan Pamsimas').
2. **Anti-Duplikasi Kata/Frasa**: Narasi tidak boleh mengandung kata/frasa berulang berturut-turut.
3. **Date Picker & H+1 Laporan**: Seluruh input tanggal harus date picker, dan default tanggal laporan adalah H+1 dari akhir tanggal perjalanan dinas.
4. **Format Nama File**: Diawali tanggal perjalanan dinas (e.g. `13-15-Agustus-2026_Magelang_Jambewangi-dkk.docx`).
5. **Autofill Desa**: Pemilihan desa harus otomatis mengisi kecamatan terkait.
