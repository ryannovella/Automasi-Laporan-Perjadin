import os
import io
import cv2
import numpy as np
from PIL import Image
from typing import Union, Dict, Any, Tuple

def _to_cv2_image(source: Union[str, bytes, Image.Image, np.ndarray]) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Konversi input gambar ke OpenCV BGR numpy array dan tuple (w, h)."""
    if isinstance(source, str):
        if not os.path.exists(source):
            raise FileNotFoundError(f"File gambar tidak ditemukan: {source}")
        img = cv2.imread(source)
        if img is None:
            raise ValueError(f"OpenCV gagal membaca gambar dari {source}")
        h, w = img.shape[:2]
        return img, (w, h)
    elif isinstance(source, bytes):
        nparr = np.frombuffer(source, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("OpenCV gagal mendecode bytes gambar")
        h, w = img.shape[:2]
        return img, (w, h)
    elif isinstance(source, Image.Image):
        pil_rgb = source.convert("RGB")
        w, h = pil_rgb.size
        img = cv2.cvtColor(np.array(pil_rgb), cv2.COLOR_RGB2BGR)
        return img, (w, h)
    elif isinstance(source, np.ndarray):
        h, w = source.shape[:2]
        return source, (w, h)
    else:
        raise TypeError(f"Tipe gambar tidak didukung: {type(source)}")

def detect_timestamp(source: Union[str, bytes, Image.Image, np.ndarray]) -> Dict[str, Any]:
    """
    Mendeteksi apakah gambar memiliki stempel timestamp/GPS bawaan kamera:
    - Memeriksa 35% batas bawah foto.
    - Mencari kluster teks bertumpuk horizontal (putih/kuning dengan bayangan gelap).
    - Memverifikasi kedekatan dasar dan densitas font untuk mencegah deteksi palsu (besi tulangan cor, dsb).
    - Menghitung persentase crop optimal untuk membuang stempel lama secara bersih.
    """
    try:
        img, (w, h) = _to_cv2_image(source)
    except Exception as e:
        return {
            "has_timestamp": False,
            "confidence": 0.0,
            "detected_lines_count": 0,
            "shadowed_pixels": 0,
            "suggested_crop_bottom": 0.18,
            "error": str(e)
        }

    bot_ratio = 0.35
    bot_h = int(h * bot_ratio)
    if bot_h <= 10 or w <= 20:
        return {
            "has_timestamp": False,
            "confidence": 0.0,
            "detected_lines_count": 0,
            "shadowed_pixels": 0,
            "suggested_crop_bottom": 0.18
        }

    crop = img[h - bot_h:, int(w * 0.20):]
    ch, cw = crop.shape[:2]

    b, g, r = crop[:, :, 0].astype(int), crop[:, :, 1].astype(int), crop[:, :, 2].astype(int)

    # 1. Warna teks putih / terang
    is_white = (r > 205) & (g > 205) & (b > 205) & (np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b]) < 40)
    is_yellow = (r > 195) & (g > 195) & (b < 145)
    stamp_colors = is_white | is_yellow

    # 2. Deteksi drop shadow gelap di sekeliling karakter
    is_dark = (r < 115) & (g < 115) & (b < 115)
    kernel_shadow = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dark_dilated = cv2.dilate(is_dark.astype(np.uint8), kernel_shadow)

    shadowed_text = stamp_colors & (dark_dilated > 0)
    shadowed_count = int(np.sum(shadowed_text))

    if shadowed_count < 650:
        return {
            "has_timestamp": False,
            "confidence": 0.0,
            "detected_lines_count": 0,
            "shadowed_pixels": shadowed_count,
            "suggested_crop_bottom": 0.18
        }

    # 3. Morfologi horizontal untuk menggabungkan karakter satu baris teks
    kw = max(8, int(cw * 0.02))
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, 2))
    closed = cv2.morphologyEx(shadowed_text.astype(np.uint8) * 255, cv2.MORPH_CLOSE, kernel_h)

    # 4. Kontur garis teks
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_line_width = max(35, int(cw * 0.08))
    max_line_height = max(28, int(ch * 0.22))

    valid_lines = []
    for c in contours:
        x, y, lw, lh = cv2.boundingRect(c)
        aspect = lw / max(1, lh)
        if lw >= min_line_width and 6 <= lh <= max_line_height and aspect >= 2.2:
            roi = shadowed_text[y:y+lh, x:x+lw]
            density = np.sum(roi) / max(1, lw * lh)
            if 0.07 <= density <= 0.48:
                valid_lines.append({
                    "x": x, "y": y, "w": lw, "h": lh,
                    "density": density,
                    "x_right": x + lw,
                    "y_bottom": y + lh,
                    "dist_to_bot": ch - (y + lh)
                })

    if len(valid_lines) < 2:
        return {
            "has_timestamp": False,
            "confidence": 0.0,
            "detected_lines_count": len(valid_lines),
            "shadowed_pixels": shadowed_count,
            "suggested_crop_bottom": 0.18
        }

    valid_lines.sort(key=lambda item: item["y"])

    # 5. Kluster paragraf teks bertumpuk
    clusters = []
    for vl in valid_lines:
        placed = False
        for cl in clusters:
            for member in cl:
                v_gap = vl["y"] - member["y_bottom"]
                if -6 <= v_gap <= max(24, int(ch * 0.16)):
                    overlap_x = min(vl["x_right"], member["x_right"]) - max(vl["x"], member["x"])
                    min_w = min(vl["w"], member["w"])
                    if overlap_x >= min_w * 0.25 or abs(vl["x"] - member["x"]) <= 40 or abs(vl["x_right"] - member["x_right"]) <= 40:
                        cl.append(vl)
                        placed = True
                        break
            if placed: break
        if not placed:
            clusters.append([vl])

    # 6. Verifikasi kedekatan dasar
    genuine_clusters = []
    topmost_line_y = ch
    for cl in clusters:
        cl.sort(key=lambda item: item["y"])
        min_dist_to_bot = min(item["dist_to_bot"] for item in cl)
        is_near_bottom = min_dist_to_bot <= max(35, int(ch * 0.22))

        if is_near_bottom:
            if len(cl) >= 3:
                genuine_clusters.append(cl)
                for item in cl: topmost_line_y = min(topmost_line_y, item["y"])
            elif len(cl) == 2:
                l1, l2 = cl[0], cl[1]
                h_ratio = max(l1["h"], l2["h"]) / max(1, min(l1["h"], l2["h"]))
                v_gap = l2["y"] - l1["y_bottom"]
                if h_ratio <= 2.2 and v_gap <= 20 and min_dist_to_bot <= max(25, int(ch * 0.15)):
                    genuine_clusters.append(cl)
                    for item in cl: topmost_line_y = min(topmost_line_y, item["y"])

    has_timestamp = len(genuine_clusters) > 0 and shadowed_count >= 650

    if has_timestamp and topmost_line_y < ch:
        stamp_span_px = ch - topmost_line_y
        safe_crop_px = min(int(h * 0.38), int(stamp_span_px * 1.15))
        suggested_crop_bottom = round(safe_crop_px / h, 3)
        confidence = min(0.99, round(0.70 + (len(genuine_clusters[0]) * 0.05) + (shadowed_count / 15000.0), 2))
    else:
        suggested_crop_bottom = 0.18
        confidence = 0.0

    return {
        "has_timestamp": bool(has_timestamp),
        "confidence": float(confidence),
        "detected_lines_count": int(len(valid_lines)),
        "shadowed_pixels": int(shadowed_count),
        "suggested_crop_bottom": float(suggested_crop_bottom)
    }

def crop_image_bottom(source: Union[str, bytes, Image.Image], crop_bottom_pct: float = 0.18) -> Tuple[Image.Image, bytes]:
    """
    Memotong bagian bawah gambar (misal 0.18 = memotong 18% dari dasar)
    untuk menghilangkan timestamp lama.
    """
    if isinstance(source, str):
        pil_img = Image.open(source)
    elif isinstance(source, bytes):
        pil_img = Image.open(io.BytesIO(source))
    elif isinstance(source, Image.Image):
        pil_img = source.copy()
    else:
        raise TypeError(f"Tipe sumber tidak didukung untuk crop: {type(source)}")

    w, h = pil_img.size
    crop_pct = max(0.02, min(0.45, float(crop_bottom_pct)))
    new_h = int(round(h * (1.0 - crop_pct)))

    if pil_img.mode in ("RGBA", "P"):
        pil_img = pil_img.convert("RGB")

    cropped = pil_img.crop((0, 0, w, new_h))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=95)
    img_bytes = buf.getvalue()

    return cropped, img_bytes
