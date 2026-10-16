# Automasi Laporan Perjadin (Monev Pamsimas)

Aplikasi berbasis **Streamlit** khusus untuk menyusun, mengaudit, dan mengotomasi pembuatan dokumen laporan perjalanan dinas Monitoring dan Evaluasi (Monev) Kegiatan Pamsimas, Balai Prasarana Permukiman Wilayah (BPPW / BPBPK) Jawa Tengah, **Kementerian Pekerjaan Umum (Kementerian PU)**.

---

## 🌟 Fitur Utama

1. **Audit & Deteksi Kelengkapan Dokumen Eksisting (.docx)**
   - Upload dokumen Word yang belum lengkap.
   - Sistem secara cerdas mendeteksi 8 komponen penting: Kabupaten, Nomor SPT, Tanggal SPT, Jadwal Dinas, Tanggal Laporan, Tabel Pelaksana, Desa & Narasi Capaian, serta Foto Dokumentasi.
   - Memberikan persentase skor kelengkapan (0–100%) dan memuat data yang ada langsung ke formulir dengan sekali klik.

2. **Deteksi Real-time Progres Kelengkapan Dokumen**
   - Live progress bar dan checklist dinamis yang langsung memperbarui status kelengkapan setiap kali kolom formulir diisi/diedit.

3. **Formulir Administrasi & Tanggal Cerdas**
   - Seluruh input tanggal menggunakan **Date Picker**.
   - Tanggal Laporan otomatis terisi default **H+1 dari hari terakhir perjalanan dinas**.
   - Format tanda tangan pelaksana dinas berformat **zig-zag resmi kedinasan Kementerian PU** dengan auto-suggest dari master data personel BPBPK Jawa Tengah (one-click add).

4. **Multi-Desa & Autofill Wilayah**
   - Penambahan multi-desa secara dinamis.
   - Fitur **Autofill Otomatis**: Memilih nama desa langsung mengisi nama kecamatan dan kabupaten dari database master Jawa Tengah.

5. **Elaborasi Catatan Lapangan Resmi (AI & Fallback KBBI)**
   - Mengubah catatan mentah menjadi narasi teknis kedinasan resmi Kementerian PU.
   - **Anti-Slop & Anti-Proyek**: Dilarang keras menggunakan kata 'proyek', 'program pamsimas', dan 'pupr' (resmi digantikan 'Kementerian PU').
   - **Anti-Duplikasi Kalimat**: Menghilangkan pengulangan kata atau frasa berturut-turut (contoh: 'dialirkan menuju dialirkan menuju').
   - Standar tanda baca KBBI (1 spasi setelah titik dua, desimal dengan tanda koma).

6. **Galeri Foto & Timestamp Watermark Resmi PU**
   - Deteksi stempel GPS lama bawaan kamera & smart bottom cropping.
   - Normalisasi aspek rasio foto ke standar **4:3 (Landscape)**.
   - Generator jadwal kerja realistis: jam kerja lapangan (09:14 – 15:00 WIB), jeda intra-spot dan transit antar-desa menghindari kelipatan 5, serta GPS Jitter pergeseran autentik tiap foto.
   - Live Preview Stamping resmi Kementerian PU (Arial putih bersih + soft drop shadow).

7. **Ekspor Word (.docx) dengan Nama Ringkas & Padat**
   - Menjaga Kop Surat Resmi Kementerian PU dan format penomoran dokumen master.
   - Tabel lampiran foto 2-kolom dengan outline tabel resmi.
   - Nama berkas otomatis ringkas, padat, dan **diawali rentang tanggal perjalanan dinas** (contoh: `13-15-Agustus-2026_Magelang_Jambewangi-dkk.docx`).

---

## 🚀 Cara Menjalankan

### Cara 1: Sekali Klik (Windows)
Cukup klik ganda file `run_app.bat`.

### Cara 2: Lewat Terminal / Command Prompt
```bash
cd /d "d:\Apps\Automasi Laporan Perjadin"
python -m streamlit run app.py
```
Aplikasi akan terbuka otomatis di peramban web pada alamat `http://localhost:8501`.

---

## 📁 Struktur Direktori

```text
Automasi Laporan Perjadin/
├── .agents/
│   └── skills/
│       └── streamlit/
│           └── SKILL.md
├── core/
│   ├── __init__.py
│   ├── config.py             # Konfigurasi path, font, dan API key
│   ├── docx_inspector.py     # Engine inspeksi & audit dokumen eksisting
│   ├── location_service.py   # Master data wilayah & personel BPBPK
│   ├── logger.py             # Sistem logging error
│   ├── report_generator.py   # Engine penyusun docx, KBBI narasi & sanitasi
│   ├── stamp_detector.py     # Deteksi & crop stempel lama kamera
│   ├── stamper.py            # Watermark resmi Kementerian PU
│   └── timeline_analyzer.py  # Linimasa jam dinas & GPS jitter realistis
├── data/
│   ├── data_lokasi.csv       # Master data desa, kecamatan, kabupaten Jateng
│   ├── Nama Personel.txt     # Master nama & NIP personel BPBPK
│   ├── uploads/              # Direktori penyimpanan unggahan sementara
│   └── output/               # Direktori hasil berkas laporan .docx
├── templates/
│   └── template_laporan_monev.docx  # Master template resmi Kementerian PU
├── app.py                    # Aplikasi web utama Streamlit
├── requirements.txt          # Dependensi Python
├── run_app.bat               # Skrip peluncuran instan
└── README.md
```
