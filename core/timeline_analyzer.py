import os
import io
import re
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
from PIL import Image, ExifTags

def _convert_to_degrees(value) -> float:
    """Helper untuk konversi koordinat EXIF ke derajat float."""
    try:
        if isinstance(value, (tuple, list)):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
        return float(value)
    except Exception:
        return 0.0

def extract_exif(image_path_or_bytes) -> Tuple[Optional[float], Optional[float], Optional[datetime]]:
    """Mengekstrak koordinat GPS (lat, lon) dan waktu asli dari EXIF foto."""
    try:
        if isinstance(image_path_or_bytes, (str, os.PathLike)):
            img = Image.open(image_path_or_bytes)
        else:
            img = Image.open(io.BytesIO(image_path_or_bytes))
            
        with img:
            exif_raw = img.getexif()
            if not exif_raw:
                return None, None, None
                
            exif = {}
            for tag_id, value in exif_raw.items():
                tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                exif[tag_name] = value

            gps_info = exif.get("GPSInfo")
            lat, lon = None, None
            if gps_info:
                gps_tags = {}
                for t in gps_info:
                    sub_tag = ExifTags.GPSTAGS.get(t, t)
                    gps_tags[sub_tag] = gps_info[t]
                    
                if "GPSLatitude" in gps_tags and "GPSLongitude" in gps_tags:
                    lat = _convert_to_degrees(gps_tags["GPSLatitude"])
                    if gps_tags.get("GPSLatitudeRef") == "S":
                        lat = -lat
                    lon = _convert_to_degrees(gps_tags["GPSLongitude"])
                    if gps_tags.get("GPSLongitudeRef") == "W":
                        lon = -lon
                        
            dt = None
            dt_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
            if dt_str:
                try:
                    dt = datetime.strptime(str(dt_str)[:19], "%Y:%m:%d %H:%M:%S")
                except Exception:
                    pass
                    
            return lat, lon, dt
    except Exception:
        return None, None, None

def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Menghitung jarak permukaan tanah antar dua koordinat GPS dalam meter."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def compute_dhash(img: Image.Image, hash_size: int = 8) -> List[bool]:
    """Menghitung dHash untuk membandingkan gradien/struktur gambar."""
    tmp = img.convert("L")
    gray = tmp.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    tmp.close()
    try:
        pixels = list(gray.getdata())
        diff = []
        for row in range(hash_size):
            for col in range(hash_size):
                pixel_left = pixels[row * (hash_size + 1) + col]
                pixel_right = pixels[row * (hash_size + 1) + col + 1]
                diff.append(pixel_left > pixel_right)
        return diff
    finally:
        gray.close()

def hamming_distance(h1: List[bool], h2: List[bool]) -> int:
    return sum(b1 != b2 for b1, b2 in zip(h1, h2))

def compute_color_profile(img: Image.Image) -> Tuple[float, float, float]:
    tmp = img.convert("RGB")
    small = tmp.resize((16, 16), Image.Resampling.BILINEAR)
    tmp.close()
    try:
        pixels = list(small.getdata())
        r = sum(p[0] for p in pixels) / len(pixels)
        g = sum(p[1] for p in pixels) / len(pixels)
        b = sum(p[2] for p in pixels) / len(pixels)
        return (r, g, b)
    finally:
        small.close()

def color_distance(c1: Tuple[float, float, float], c2: Tuple[float, float, float]) -> float:
    return math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2)

def cluster_photos(photos: List[Dict[str, Any]], gps_threshold_meters: float = 80.0) -> List[Dict[str, Any]]:
    """
    Mengelompokkan foto-foto ke dalam spot survei lapangan:
    1. Isolasi batas desa (Desa berbeda tidak pernah digabung)
    2. Nama dusun/lokasi
    3. Jarak GPS (jarak >80m = spot berbeda)
    4. Kemiripan visual (dHash & Color profile)
    """
    if not photos:
        return []

    enriched = []
    for p in photos:
        img_obj = p.get("imgObj")
        img_path = p.get("path")
        
        pil_img = None
        should_close = False
        if img_obj:
            pil_img = img_obj
        elif img_path and os.path.exists(img_path):
            try:
                pil_img = Image.open(img_path)
                should_close = True
            except Exception:
                pass
                
        d_hash = compute_dhash(pil_img) if pil_img else None
        c_prof = compute_color_profile(pil_img) if pil_img else None
        if should_close and pil_img:
            try:
                pil_img.close()
            except Exception:
                pass
        
        lat_val = None
        lon_val = None
        try:
            if p.get("lat") and p.get("lon"):
                lat_val = float(str(p["lat"]).replace(",", "."))
                lon_val = float(str(p["lon"]).replace(",", "."))
        except Exception:
            pass

        enriched.append({
            "meta": p,
            "hash": d_hash,
            "color": c_prof,
            "lat": lat_val,
            "lon": lon_val,
            "dusun": (p.get("dusun") or "").strip().lower(),
            "desa": (p.get("desa") or "").strip().lower()
        })

    clusters: List[List[Dict[str, Any]]] = []
    
    for item in enriched:
        matched_cluster = None
        
        for cl in clusters:
            rep = cl[0]
            
            # Jangan gabung antar-desa yang berbeda
            if item["desa"] and rep["desa"] and item["desa"] != rep["desa"]:
                continue
            
            # Cocokkan nama dusun
            if item["dusun"] and rep["dusun"] and item["dusun"] == rep["dusun"]:
                matched_cluster = cl
                break
                
            # Jarak GPS jika tersedia
            if item["lat"] is not None and rep["lat"] is not None:
                dist = haversine_meters(item["lat"], item["lon"], rep["lat"], rep["lon"])
                if dist < gps_threshold_meters:
                    matched_cluster = cl
                    break
                else:
                    continue
                    
            # Kemiripan visual
            if item["hash"] and rep["hash"] and item["color"] and rep["color"]:
                h_dist = hamming_distance(item["hash"], rep["hash"])
                c_dist = color_distance(item["color"], rep["color"])
                if h_dist <= 26 or c_dist <= 22.0:
                    matched_cluster = cl
                    break
                    
        if matched_cluster is not None:
            matched_cluster.append(item)
        else:
            clusters.append([item])

    formatted_clusters = []
    for idx, cl in enumerate(clusters):
        first = cl[0]["meta"]
        spot_name = first.get("dusun") or f"Lokasi #{idx + 1}"
        desa_name = first.get("desa") or ""
        
        formatted_clusters.append({
            "spot_id": idx + 1,
            "title": f"Spot #{idx + 1}: {spot_name}" + (f" ({desa_name})" if desa_name else ""),
            "dusun": spot_name,
            "desa": desa_name,
            "photos": [x["meta"] for x in cl]
        })
        
    return formatted_clusters

def _get_humanized_seconds(min_sec: int, max_sec: int) -> int:
    """Mengembalikan detik tak-bulat (menghindari akhiran 0 atau 5)."""
    valid_pool = [s for s in range(min_sec, max_sec + 1) if s % 5 != 0 and s % 10 != 0]
    if not valid_pool:
        valid_pool = [s for s in range(min_sec, max_sec + 1) if s % 10 != 0]
    return random.choice(valid_pool) if valid_pool else min_sec

def _step_humanized_time(cur_dt: datetime, min_sec: int, max_sec: int) -> Tuple[datetime, int]:
    """Melompatkan waktu dengan jeda tak-bulat, menit & detik terjamin tidak berakhiran 0 atau 5."""
    for _ in range(100):
        delta_sec = _get_humanized_seconds(min_sec, max_sec)
        new_dt = cur_dt + timedelta(seconds=delta_sec)
        if new_dt.second % 5 != 0 and new_dt.minute % 5 != 0 and delta_sec % 5 != 0:
            return new_dt, delta_sec

    for shift in [17, 23, 31, 47, 53, 67, 73, 83]:
        fallback_dt = cur_dt + timedelta(seconds=shift)
        if fallback_dt.second % 5 != 0 and fallback_dt.minute % 5 != 0:
            return fallback_dt, shift

    fallback_dt = cur_dt + timedelta(seconds=17)
    if fallback_dt.minute % 5 == 0:
        fallback_dt += timedelta(minutes=1)
    if fallback_dt.second % 5 == 0:
        fallback_dt += timedelta(seconds=2)
    return fallback_dt, 17

def _jitter_gps_coordinates(lat: Any, lon: Any, min_m: float = 6.0, max_m: float = 24.0) -> Tuple[str, str]:
    """Menghasilkan pergeseran realistis (jitter) koordinat GPS survei (menghindari kelipatan 5 meter)."""
    try:
        lat_f = float(str(lat).replace(",", "."))
        lon_f = float(str(lon).replace(",", "."))
        
        valid_m = [m for m in range(int(math.ceil(min_m)), int(math.floor(max_m)) + 1) if m % 5 != 0]
        base_m = random.choice(valid_m) if valid_m else 13
        frac = random.choice([0.13, 0.27, 0.38, 0.42, 0.63, 0.74, 0.86])
        radius = base_m + frac
        angle = random.uniform(0.0, 2.0 * math.pi)
        
        m_per_deg_lat = 111132.0
        m_per_deg_lon = 111320.0 * math.cos(math.radians(lat_f))
        
        d_lat = (radius * math.cos(angle)) / m_per_deg_lat
        d_lon = (radius * math.sin(angle)) / m_per_deg_lon
        
        new_lat = f"{lat_f + d_lat:.6f}"
        new_lon = f"{lon_f + d_lon:.6f}"
        return new_lat, new_lon
    except Exception:
        return str(lat), str(lon)

INDO_DAYS = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']
INDO_MONTH_NAMES = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

def generate_humanized_timeline(
    clusters: List[Dict[str, Any]],
    start_time_str: str = "09:14:23",
    end_time_str: str = "15:00:00",
    date_tuple: Tuple[int, int, int] = (2026, 8, 14),
    end_date_tuple: Optional[Tuple[int, int, int]] = None,
    day_name: Optional[str] = None,
    intra_min_sec: int = 47,
    intra_max_sec: int = 163,
    transit_min_min: int = 31,
    transit_max_min: int = 49,
    apply_gps_jitter: bool = True,
    min_gps_jitter_m: float = 6.0,
    max_gps_jitter_m: float = 24.0
) -> List[Dict[str, Any]]:
    """
    Menghasilkan linimasa jam kerja dinas yang realistis & manusiawi:
    - Dukungan multi-hari & hari tunggal (alokasi proporsional per hari)
    - Batas jam kerja realistis (misal 09:14 WIB s.d. maks 15:00 WIB)
    - Jeda di spot yang sama: 47 detik s.d. 2m 43s (menghindari kelipatan 5)
    - Jeda transit antar spot/desa: 31 s.d. 49 menit (menghindari kelipatan 5)
    - Menit & detik terjamin tidak berakhir di angka 0 atau 5
    - Koordinat GPS diberi jitter realistis
    """
    time_parts = [int(p) for p in re.findall(r"\d+", start_time_str)]
    base_hh = time_parts[0] if len(time_parts) > 0 else 9
    base_mm = time_parts[1] if len(time_parts) > 1 else 14
    base_ss = time_parts[2] if len(time_parts) > 2 else 23

    end_time_parts = [int(p) for p in re.findall(r"\d+", end_time_str)]
    limit_hh = end_time_parts[0] if len(end_time_parts) > 0 else 15
    limit_mm = end_time_parts[1] if len(end_time_parts) > 1 else 0
    limit_ss = end_time_parts[2] if len(end_time_parts) > 2 else 0
    
    if base_ss % 5 == 0:
        base_ss = (base_ss + 2) % 60
    if base_mm % 5 == 0:
        base_mm = (base_mm + 2) % 60

    from datetime import date as _date
    d1 = _date(date_tuple[0], date_tuple[1], date_tuple[2])
    d2 = _date(end_date_tuple[0], end_date_tuple[1], end_date_tuple[2]) if end_date_tuple else d1
    if d2 < d1:
        d2 = d1
    total_days = max(1, (d2 - d1).days + 1)
    total_clusters = len(clusters)

    timeline_results = []
    global_photo_idx = 0
    current_day_offset = -1
    cur_dt = None

    for c_idx, cluster in enumerate(clusters):
        photos = cluster.get("photos", [])
        spot_title = cluster.get("title", f"Spot #{c_idx + 1}")
        
        day_offset = min(total_days - 1, (c_idx * total_days) // total_clusters) if total_clusters > 0 else 0
        is_new_day = (day_offset != current_day_offset)
        current_day_offset = day_offset

        if is_new_day:
            cur_day = d1 + timedelta(days=day_offset)
            day_hh = base_hh
            day_mm = (base_mm + ((c_idx * 7 + 3) % 15)) % 60
            if day_mm % 5 == 0:
                day_mm = (day_mm + 2) % 60
            day_ss = (base_ss + ((c_idx * 13 + 17) % 30)) % 60
            if day_ss % 5 == 0:
                day_ss = (day_ss + 2) % 60
            cur_dt = datetime(cur_day.year, cur_day.month, cur_day.day, day_hh, day_mm, day_ss)

        for p_idx, p in enumerate(photos):
            global_photo_idx += 1
            transit_note = None
            delta_note = None

            if p_idx == 0:
                if is_new_day:
                    delta_note = f"Awal Hari ke-{day_offset + 1}" if total_days > 1 else "Waktu Awal"
                    if c_idx > 0 and total_days > 1:
                        day_lbl = INDO_DAYS[(cur_dt.weekday() + 1) % 7]
                        m_lbl = INDO_MONTH_NAMES[cur_dt.month]
                        transit_note = f"Hari ke-{day_offset + 1} ({day_lbl}, {cur_dt.day} {m_lbl}): {spot_title}"
                elif c_idx > 0:
                    valid_transit_mins = [m for m in range(transit_min_min, transit_max_min + 1) if m % 5 != 0]
                    t_m = random.choice(valid_transit_mins) if valid_transit_mins else 33
                    t_s_pool = [17, 23, 31, 38, 42, 53]
                    t_s = random.choice(t_s_pool)
                    transit_sec = t_m * 60 + t_s
                    cur_dt += timedelta(seconds=transit_sec)
                    if cur_dt.second % 5 == 0:
                        cur_dt += timedelta(seconds=2 if cur_dt.second < 58 else -2)
                    if cur_dt.minute % 5 == 0:
                        cur_dt += timedelta(minutes=1 if cur_dt.minute < 59 else -1)
                    transit_note = f"Perpindahan ke {spot_title}: +{t_m} menit {t_s} detik"
                    delta_note = f"+{t_m}m {t_s}s"
                else:
                    delta_note = "Waktu Awal"
            else:
                cur_dt, step_sec = _step_humanized_time(cur_dt, intra_min_sec, intra_max_sec)
                s_m = step_sec // 60
                s_s = step_sec % 60
                delta_note = f"+{s_m}m {s_s}s" if s_m > 0 else f"+{s_s}s"

            # Batas atas sore hari (misal maks 15:00 WIB)
            day_limit_dt = datetime(cur_dt.year, cur_dt.month, cur_dt.day, limit_hh, limit_mm, limit_ss)
            if cur_dt > day_limit_dt:
                cur_dt = day_limit_dt - timedelta(minutes=random.choice([2, 3, 4, 6, 7]), seconds=_get_humanized_seconds(18, 54))
                if cur_dt.second % 5 == 0:
                    cur_dt += timedelta(seconds=2 if cur_dt.second < 58 else -2)
                if cur_dt.minute % 5 == 0:
                    cur_dt += timedelta(minutes=1 if cur_dt.minute < 59 else -1)

            h_str = f"{cur_dt.hour:02d}"
            m_str = f"{cur_dt.minute:02d}"
            s_str = f"{cur_dt.second:02d}"

            photo_day_name = INDO_DAYS[(cur_dt.weekday() + 1) % 7]
            photo_month_name = INDO_MONTH_NAMES[cur_dt.month]
            full_time_str = f"{photo_day_name}, {cur_dt.day} {photo_month_name} {cur_dt.year} {h_str}:{m_str}:{s_str} WIB"

            photo_lat = p.get("lat")
            photo_lon = p.get("lon")
            if apply_gps_jitter and photo_lat is not None and photo_lon is not None:
                photo_lat, photo_lon = _jitter_gps_coordinates(photo_lat, photo_lon, min_gps_jitter_m, max_gps_jitter_m)

            timeline_results.append({
                "photo_id": p.get("id"),
                "filename": p.get("filename") or p.get("name"),
                "spot_id": c_idx + 1,
                "spot_title": spot_title,
                "time_str": full_time_str,
                "clock": f"{h_str}:{m_str}:{s_str}",
                "delta_label": delta_note,
                "transit_note": transit_note,
                "url": p.get("url") or p.get("dataUrl"),
                "dusun": p.get("dusun"),
                "desa": p.get("desa"),
                "kecamatan": p.get("kecamatan"),
                "kabupaten": p.get("kabupaten"),
                "provinsi": p.get("provinsi"),
                "lat": photo_lat,
                "lon": photo_lon
            })

    return timeline_results
