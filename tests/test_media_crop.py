import base64
import io

from PIL import Image

from ai_work_automation.media_crop import crop_image_bytes, image_bytes_to_html


def test_image_bytes_to_html_embeds_base64_img():
    data = b"PNG-BYTES"
    html = image_bytes_to_html("shot.png", data, mime="image/png", width_px=400)
    encoded = base64.b64encode(data).decode("ascii")
    assert f'src="data:image/png;base64,{encoded}"' in html
    assert 'alt="shot.png"' in html
    assert "width:400px" in html
    assert html.startswith("<p")


def _png_bytes(width: int, height: int, color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_crop_image_bytes_returns_requested_box():
    data = _png_bytes(100, 80)
    cropped = crop_image_bytes(data, left=10, top=5, right=40, bottom=35)
    out = Image.open(io.BytesIO(cropped))
    assert out.size == (30, 30)
