from __future__ import annotations

from io import BytesIO


def build_qr_png(payload: str) -> bytes:
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("qrcode package is required for QR generation") from exc

    image = qrcode.make(payload)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

