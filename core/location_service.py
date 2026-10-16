import os
import csv
import re
import difflib
from typing import List, Dict, Tuple, Optional
from core.config import LOCATIONS_CSV, PERSONEL_TXT

KNOWN_LOCATIONS: List[Dict[str, str]] = []
KNOWN_COORDS: Dict[str, Tuple[str, str, str, str]] = {
    "jambewangi": ("-7.451824", "110.331825", "Pakis", "Kabupaten Magelang"),
    "tanjungsari": ("-7.422850", "110.133040", "Windusari", "Kabupaten Magelang"),
    "ketawang": ("-7.408820", "110.324540", "Grabag", "Kabupaten Magelang"),
    "genito": ("-7.397820", "110.156540", "Windusari", "Kabupaten Magelang"),
    "jati": ("-7.510160", "110.380950", "Sawangan", "Kabupaten Magelang"),
    "baleagung": ("-7.391520", "110.312050", "Grabag", "Kabupaten Magelang"),
    "karanggayam": ("-7.585210", "109.612450", "Karanggayam", "Kabupaten Kebumen"),
    "gempolan": ("-7.558320", "111.084530", "Kerjo", "Kabupaten Karanganyar"),
    "bukuran": ("-7.426210", "110.978120", "Kalijambe", "Kabupaten Sragen"),
    "gabus": ("-7.362140", "111.045230", "Ngrampal", "Kabupaten Sragen"),
    "aditirto": ("-7.683412", "109.641238", "Pejagoan", "Kabupaten Kebumen"),
    "tlogosari": ("-7.625124", "109.684125", "Ayah", "Kabupaten Kebumen"),
    "karanganyar": ("-7.596200", "110.952100", "Karanganyar", "Kabupaten Karanganyar"),
    "sragen": ("-7.426600", "111.022200", "Sragen", "Kabupaten Sragen"),
    "mojosari": ("-7.371420", "110.712350", "Karanggede", "Kabupaten Boyolali"),
}

INDONESIAN_COMMON_WORDS = {
    'dan', 'atau', 'serta', 'tetapi', 'namun', 'melainkan', 'sedangkan', 'padahal',
    'karena', 'sebab', 'sehingga', 'sampai', 'hingga', 'jika', 'bila', 'apabila',
    'kalau', 'walaupun', 'meskipun', 'biarpun', 'kendati', 'supaya', 'agar', 'untuk',
    'bagi', 'guna', 'oleh', 'dengan', 'tanpa', 'tentang', 'mengenai', 'terhadap',
    'pada', 'dalam', 'atas', 'bawah', 'antara', 'luar', 'dari', 'ke', 'di',
    'ini', 'itu', 'tersebut', 'berikut', 'tadi', 'sana', 'sini', 'situ',
    'yang', 'apa', 'siapa', 'mana', 'kapan', 'bagaimana', 'mengapa', 'kenapa',
    'saya', 'kami', 'kita', 'anda', 'kamu', 'mereka', 'dia', 'beliau', 'ia',
    'kegiatan', 'pelaksanaan', 'pemantauan', 'evaluasi', 'monitoring', 'pengawasan',
    'progres', 'pekerjaan', 'capaian', 'rekomendasi', 'catatan', 'kondisi', 'hasil',
    'lapangan', 'pembangunan', 'penyediaan', 'sarana', 'prasarana', 'air', 'minum',
    'sanitasi', 'masyarakat', 'bantuan', 'pemerintah', 'desa', 'kecamatan', 'kabupaten'
}

def is_indonesian_word(word: str) -> bool:
    return word.lower().strip() in INDONESIAN_COMMON_WORDS

def _load_locations():
    global KNOWN_LOCATIONS
    if KNOWN_LOCATIONS:
        return
    if os.path.exists(LOCATIONS_CSV):
        try:
            with open(LOCATIONS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    desa = row.get("Desa", "").strip()
                    kec = row.get("Kecamatan", "").strip()
                    kab = row.get("Kabupaten", "").strip()
                    if desa:
                        dkey = desa.lower()
                        kckey = kec.lower()
                        kab_full = f"Kabupaten {kab}" if not kab.lower().startswith(("kabupaten", "kota")) else kab
                        KNOWN_LOCATIONS.append({
                            "desa": desa,
                            "desa_key": dkey,
                            "kecamatan": kec,
                            "kec_key": kckey,
                            "kabupaten": kab_full
                        })
                        if dkey not in KNOWN_COORDS:
                            KNOWN_COORDS[dkey] = ("-7.500000", "110.500000", kec, kab_full)
                        else:
                            lat, lon, _, _ = KNOWN_COORDS[dkey]
                            KNOWN_COORDS[dkey] = (lat, lon, kec, kab_full)
        except Exception as e:
            print(f"Gagal memuat data_lokasi.csv: {e}")

_load_locations()

def get_all_kabupaten() -> List[str]:
    """Mendapatkan daftar unik Kabupaten."""
    kabs = sorted(list(set(loc["kabupaten"].replace("Kabupaten ", "").strip() for loc in KNOWN_LOCATIONS if loc["kabupaten"])))
    if "Magelang" in kabs:
        kabs.remove("Magelang")
        kabs.insert(0, "Magelang")
    return kabs

def get_kecamatan_by_kabupaten(kabupaten: str) -> List[str]:
    """Mendapatkan daftar kecamatan berdasarkan kabupaten."""
    kab_clean = kabupaten.replace("Kabupaten ", "").strip().lower()
    kec_set = set()
    for loc in KNOWN_LOCATIONS:
        if kab_clean in loc["kabupaten"].lower():
            if loc["kecamatan"]:
                kec_set.add(loc["kecamatan"])
    return sorted(list(kec_set))

def get_desa_by_kecamatan(kabupaten: str, kecamatan: str) -> List[str]:
    """Mendapatkan daftar desa berdasarkan kabupaten dan kecamatan."""
    kab_clean = kabupaten.replace("Kabupaten ", "").strip().lower()
    kec_clean = kecamatan.strip().lower()
    desa_set = set()
    for loc in KNOWN_LOCATIONS:
        if kab_clean in loc["kabupaten"].lower() and kec_clean == loc["kec_key"]:
            if loc["desa"]:
                desa_set.add(loc["desa"])
    return sorted(list(desa_set))

def get_all_villages_with_meta() -> List[Dict[str, str]]:
    """Mendapatkan seluruh daftar desa beserta kecamatan dan kabupaten untuk pencarian cepat/autofill."""
    return KNOWN_LOCATIONS

def fuzzy_match_village(desa_name: str, cutoff: float = 0.85) -> str:
    """Mencocokkan nama desa dengan toleransi typo ringan."""
    if not desa_name:
        return ""
    d_clean = re.sub(r'^(?:desa|dsa)\s+', '', desa_name.strip(), flags=re.I).lower().strip()
    if not d_clean or is_indonesian_word(d_clean):
        return desa_name.strip().title()

    all_village_keys = list(set([loc["desa_key"] for loc in KNOWN_LOCATIONS] + list(KNOWN_COORDS.keys())))
    if d_clean in all_village_keys:
        for loc in KNOWN_LOCATIONS:
            if loc["desa_key"] == d_clean:
                return loc["desa"]
        if d_clean in KNOWN_COORDS:
            return d_clean.capitalize()

    matches = difflib.get_close_matches(d_clean, all_village_keys, n=1, cutoff=cutoff)
    if matches:
        matched_key = matches[0]
        for loc in KNOWN_LOCATIONS:
            if loc["desa_key"] == matched_key:
                return loc["desa"]
    return desa_name.strip().title()

def lookup_location(desa_name: str, kec_hint: str = "", kab_hint: str = "") -> Tuple[str, str, str, str]:
    """
    Mencari (lat, lon, kecamatan, kabupaten) untuk suatu desa.
    Mendukung disambiguasi jika ada nama desa yang sama di kecamatan berbeda.
    """
    corrected_desa = fuzzy_match_village(desa_name)
    d_key = corrected_desa.lower().strip()
    if not d_key:
        return ("-7.500000", "110.500000", kec_hint, kab_hint or "Kabupaten Magelang")

    matching = [loc for loc in KNOWN_LOCATIONS if loc["desa_key"] == d_key]
    
    if len(matching) == 1:
        loc = matching[0]
        lat, lon = KNOWN_COORDS.get(d_key, ("-7.500000", "110.500000"))[:2]
        return (lat, lon, loc["kecamatan"], loc["kabupaten"])
    
    elif len(matching) > 1:
        if kec_hint:
            k_hint_key = kec_hint.lower().strip()
            for loc in matching:
                if loc["kec_key"] == k_hint_key or k_hint_key in loc["kec_key"]:
                    lat, lon = KNOWN_COORDS.get(d_key, ("-7.500000", "110.500000"))[:2]
                    return (lat, lon, loc["kecamatan"], loc["kabupaten"])
        
        if kab_hint:
            kab_clean = kab_hint.replace("Kabupaten", "").strip().lower()
            for loc in matching:
                if kab_clean in loc["kabupaten"].lower():
                    lat, lon = KNOWN_COORDS.get(d_key, ("-7.500000", "110.500000"))[:2]
                    return (lat, lon, loc["kecamatan"], loc["kabupaten"])

        loc = matching[0]
        lat, lon = KNOWN_COORDS.get(d_key, ("-7.500000", "110.500000"))[:2]
        return (lat, lon, loc["kecamatan"], loc["kabupaten"])

    if d_key in KNOWN_COORDS:
        lat, lon, def_kec, def_kab = KNOWN_COORDS[d_key]
        return (lat, lon, kec_hint or def_kec, kab_hint or def_kab)

    return ("-7.500000", "110.500000", kec_hint, kab_hint or "Kabupaten Magelang")

def get_personel_list() -> List[str]:
    """Membaca daftar personel resmi BPBPK dari file Nama Personel.txt."""
    if not os.path.exists(PERSONEL_TXT):
        return []
    personel = []
    try:
        with open(PERSONEL_TXT, "r", encoding="utf-8") as f:
            for line in f:
                line_clean = line.strip()
                if line_clean and not line_clean.startswith("#"):
                    # Bersihkan prefix penomoran (misal: "1. ", "15. ") agar nama tampil rapi
                    clean_name = re.sub(r"^\d+[\.\)]\s*", "", line_clean).strip()
                    if clean_name and clean_name not in personel:
                        personel.append(clean_name)
    except Exception as e:
        print(f"Gagal membaca Nama Personel.txt: {e}")
    return personel
