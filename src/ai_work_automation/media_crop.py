from __future__ import annotations

import base64
import io


def image_bytes_to_html(
    filename: str,
    data: bytes,
    *,
    mime: str = "image/png",
    width_px: int = 600,
) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return (
        f'<p style="margin:0;line-height:1.2">'
        f'<img src="data:{mime};base64,{encoded}" '
        f'style="width:{width_px}px;max-width:100%" alt="{filename}" /></p>'
    )


def crop_image_bytes(
    data: bytes,
    *,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    width, height = img.size
    left = max(0, min(int(left), width))
    top = max(0, min(int(top), height))
    right = max(0, min(int(right), width))
    bottom = max(0, min(int(bottom), height))
    if right <= left or bottom <= top:
        buf = io.BytesIO()
        img.save(buf, format=img.format or "PNG")
        return buf.getvalue()
    cropped = img.crop((left, top, right, bottom))
    fmt = "JPEG" if (img.format or "").upper() in {"JPEG", "JPG"} else "PNG"
    if fmt == "JPEG" and cropped.mode in {"RGBA", "P", "LA"}:
        cropped = cropped.convert("RGB")
    buf = io.BytesIO()
    cropped.save(buf, format=fmt)
    return buf.getvalue()
