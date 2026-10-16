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

<!-- antislop:start -->
## antislop
For UI, copy, people, mobile layout, or code comments work, read these installed skill files directly (use these paths even if a same-named global skill exists):
- Core filter, always on: `antislop`: `.agents/skills/antislop/SKILL.md`
- UI / visual: `antislop-ui`: `.agents/skills/antislop-ui/SKILL.md`
- Copy & text: `antislop-copywriting`: `.agents/skills/antislop-copywriting/SKILL.md`
- People: `antislop-human`: `.agents/skills/antislop-human/SKILL.md`
- Mobile / responsive: `antislop-layoutmobile`: `.agents/skills/antislop-layoutmobile/SKILL.md`
- Code comments: `antislop-code`: `.agents/skills/antislop-code/SKILL.md`
Before starting, follow the core's "Two Usage Modes" section in strict order: explicit session instruction first, then global preference, then ask. A session instruction always wins. For a resolved mode, say `antislop active: <mode> (session override).` or `antislop active: <mode> (global preference).` once before presenting findings or making edits, using the actual mode and source. Acknowledging the user's request without naming the source does not replace this notice.
Only an explicit choice of antislop during or after selects a session mode. A request to review, audit, or avoid file edits does not select a mode; read the global preference in that case. Another skill's mode does not select antislop's mode.
If the mode is unresolved, ask during/after and end the response; wait for the answer before any UI review, planning, or concept. For read-only tasks, put the active-mode notice only at the start of the final answer, never in progress messages. For editing tasks, announce before the first edit and omit it from the final answer.
To update antislop later: `npx antislop-ai --update`, or run `npx antislop-ai` and pick Overwrite them.
<!-- antislop:end -->

