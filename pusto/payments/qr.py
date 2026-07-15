import base64
from io import BytesIO

import qrcode


def generate_qr_data_url(data: str) -> str:
    """
    Генерирует QR-код и возвращает его как data URL (base64 PNG),
    чтобы фронт мог сразу вставить в <img src="...">, без похода
    на отдельный эндпоинт за картинкой.
    """
    img = qrcode.make(data)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    return f"data:image/png;base64,{encoded}"
