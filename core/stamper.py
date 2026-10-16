import os
import io
import textwrap
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from core.config import (
    STAMP_FONT_PATH, FALLBACK_FONT_PATH, FONT_SIZE_RATIO, LINE_HEIGHT_RATIO,
    MARGIN_RIGHT_RATIO, MARGIN_BOTTOM_RATIO, SHADOW_DX_SCALE, SHADOW_DY_SCALE,
    SHADOW_BLUR_SCALE, SHADOW_OPACITY, TEXT_COLOR
)

def wrap_address_lines(text: str, max_chars: int = 42) -> list:
    """Memotong baris alamat hasil GPS capture secara rapi tanpa merusak kata."""
    result = []
    for para in text.split("\n"):
        p_clean = para.strip()
        if not p_clean:
            continue
        if len(p_clean) <= max_chars:
            result.append(p_clean)
        else:
            wrapped = textwrap.wrap(p_clean, width=max_chars, break_long_words=False, break_on_hyphens=False)
            result.extend(wrapped)
    return result

def apply_stamp(img: Image.Image, time_str: str, lat: str, lon: str, dusun: str = "", 
                desa: str = "", kecamatan: str = "", kabupaten: str = "Kabupaten Magelang", 
                provinsi: str = "Jawa Tengah", font_scale: float = 1.0,
                custom_address: Optional[str] = None, address_mode: str = "auto") -> Image.Image:
    """
    Menerapkan stempel resmi watermark kegiatan Pamsimas Kementerian PU:
    - Font Arial putih bersih dengan drop shadow lembut (tanpa bounding box hitam pekat)
    - Skala proporsional terhadap resolusi foto
    - Rata kanan di sudut kanan bawah
    - Koordinat menggunakan tanda desimal koma sesuai kaidah KBBI/resmi kedinasan
    """
    img = img.convert("RGBA")
    w, h = img.size
    
    # Normalisasi aspek rasio menggunakan geometric mean
    base_dim = (w * h) ** 0.5
    
    scale_multiplier = float(font_scale) if font_scale else 1.0
    font_size = max(10, int(round(base_dim * FONT_SIZE_RATIO * scale_multiplier)))
    line_height = int(round(font_size * LINE_HEIGHT_RATIO))
    margin_right = max(10, int(round(w * MARGIN_RIGHT_RATIO)))
    margin_bottom = max(10, int(round(h * MARGIN_BOTTOM_RATIO)))
    
    # Format koordinat dengan tanda koma desimal
    lat_str = str(lat).strip().replace(".", ",")
    lon_str = str(lon).strip().replace(".", ",")
    coords_line = f"{lat_str} {lon_str}"
    
    custom_addr_str = str(custom_address or "").strip()
    if custom_addr_str and address_mode != "structured":
        # Mode Alamat Bebas / GPS Natural
        addr_lines = wrap_address_lines(custom_addr_str, max_chars=42)
        lines = [time_str.strip(), coords_line] + addr_lines
    else:
        # Mode Hierarki Wilayah Resmi Pamsimas
        kec_clean = kecamatan.strip()
        if not kec_clean.lower().startswith("kecamatan") and kec_clean:
            kec_clean = f"Kecamatan {kec_clean}"
            
        lines = [
            time_str.strip(),
            coords_line,
            dusun.strip(),
            desa.strip(),
            kec_clean,
            kabupaten.strip(),
            provinsi.strip()
        ]
    lines = [l for l in lines if l]
    
    font_path = STAMP_FONT_PATH if os.path.exists(STAMP_FONT_PATH) else FALLBACK_FONT_PATH
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
        
    line_bboxes = [font.getbbox(l) for l in lines]
    total_text_h = len(lines) * line_height
    start_y = h - margin_bottom - total_text_h
    
    scale = font_size / 20.0
    dx = SHADOW_DX_SCALE * scale
    dy = SHADOW_DY_SCALE * scale
    blur_r = SHADOW_BLUR_SCALE * scale
    
    # 1. Soft Shadow Layer
    shadow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_img)
    for i, line in enumerate(lines):
        tb = line_bboxes[i]
        lw = tb[2] - tb[0]
        lx = w - margin_right - lw + dx
        ly = start_y + i * line_height - tb[1] + dy
        sdraw.text((lx, ly), line, font=font, fill=(0, 0, 0, SHADOW_OPACITY))
    del sdraw
        
    shadow_blurred = shadow_img.filter(ImageFilter.GaussianBlur(radius=blur_r))
    shadow_img.close()
    img = Image.alpha_composite(img, shadow_blurred)
    shadow_blurred.close()
    
    # 2. Main Crisp Text Layer
    text_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_img)
    for i, line in enumerate(lines):
        tb = line_bboxes[i]
        lw = tb[2] - tb[0]
        lx = w - margin_right - lw
        ly = start_y + i * line_height - tb[1]
        tdraw.text((lx, ly), line, font=font, fill=TEXT_COLOR)
    del tdraw
        
    img = Image.alpha_composite(img, text_img)
    text_img.close()
    result = img.convert("RGB")
    img.close()
    return result

def stamp_to_bytes(img: Image.Image, time_str: str, lat: str, lon: str, dusun: str = "", 
                   desa: str = "", kecamatan: str = "", kabupaten: str = "Kabupaten Magelang", 
                   provinsi: str = "Jawa Tengah", font_scale: float = 1.0, 
                   custom_address: Optional[str] = None, address_mode: str = "auto",
                   format: str = "JPEG", quality: int = 95) -> bytes:
    """Helper untuk menghasilkan bytes buffer dari gambar berstempel."""
    result = apply_stamp(
        img, time_str, lat, lon, dusun, desa, kecamatan, kabupaten, provinsi,
        font_scale=font_scale, custom_address=custom_address, address_mode=address_mode
    )
    buf = io.BytesIO()
    result.save(buf, format=format, quality=quality)
    return buf.getvalue()
