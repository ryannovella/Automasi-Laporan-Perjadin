---
name: streamlit
description: "Comprehensive guide and best practices for developing high-performance, beautiful Streamlit web applications."
---

# Streamlit Development Skill

Gunakan panduan ini saat merancang, membangun, mendebug, atau memelihara aplikasi berbasis Python **Streamlit**.

---

## 1. Core Architecture & Execution Model
- **Top-to-Bottom Execution**: Streamlit mengeksekusi skrip Python dari atas ke bawah setiap kali ada interaksi pengguna (widget value change).
- **Session State (`st.session_state`)**:
  - Selalu simpan state yang persisten antar re-run (e.g. daftar foto, metadata formulir, status audit, data yang di-cache) di `st.session_state`.
  - Inisialisasi state di awal aplikasi:
    ```python
    if "key" not in st.session_state:
        st.session_state.key = initial_value
    ```
- **Caching**:
  - Gunakan `@st.cache_data` untuk komputasi berat, parsing file, I/O data, transformasi image.
  - Gunakan `@st.cache_resource` untuk koneksi database, model AI/ML, client library.

---

## 2. Layout & UI Patterns
- **Page Config**:
  ```python
  st.set_page_config(
      page_title="Automasi Laporan Perjadin",
      page_icon="📄",
      layout="wide",
      initial_sidebar_state="expanded"
  )
  ```
- **Responsive Layout**:
  - Gunakan `st.columns([col1_ratio, col2_ratio])` untuk tata letak bersebelahan (misal: formulir kiri, pratinjau kanan).
  - Gunakan `st.tabs(["Tab 1", "Tab 2"])` untuk memisahkan alur kerja logis.
  - Gunakan `st.expander("Judul", expanded=False)` untuk pengaturan lanjutan agar UI tetap bersih.
- **Custom CSS Injection**:
  - Gunakan `st.markdown('<style>...</style>', unsafe_allow_html=True)` untuk styling presisi (font kedinasan, warna badge status, kontras tinggi).

---

## 3. Data & Form Handling
- **Forms (`st.form`)**:
  - Gunakan `with st.form("my_form"):` jika ingin mengelompokkan input banyak agar tidak memicu re-run pada setiap ketukan keyboard, dan sediakan `st.form_submit_button("Simpan / Terapkan")`.
  - Untuk input interaktif real-time (live audit/autofill), gunakan widget mandiri di luar `st.form` dengan callback `on_change`.
- **File Uploader**:
  - Gunakan `st.file_uploader(label, type=["docx", "jpg", "png"], accept_multiple_files=True)` untuk upload dokumen dan foto.
  - Untuk file Word `.docx`, gunakan `io.BytesIO(uploaded_file.read())`.

---

## 4. Modern UX Best Practices
1. **Feedback & Progress**:
   - Gunakan `st.progress(pct)` atau `st.status()` saat memproses ekstraksi Word atau rendering stempel GPS banyak foto.
   - Gunakan `st.toast("Pesan sukses")` untuk notifikasi singkat.
2. **Download Handling**:
   - Gunakan `st.download_button(label="Unduh Dokumen .docx", data=docx_bytes, file_name=filename, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")`.
3. **Dataframe & Metrics**:
   - Gunakan `st.metric(label, value, delta)` untuk ringkasan metrik (misal: Skor Kelengkapan Dokumen, Jumlah Desa, Total Foto).

---

## 5. Command Reference
- Menjalankan aplikasi Streamlit:
  ```powershell
  streamlit run app.py --server.port 8501 --server.headless true
  ```
