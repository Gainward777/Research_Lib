from io import BytesIO

from PIL import Image, ImageOps


def normalize_image(
    content: bytes, *, max_long_side: int, image_format: str, quality: int
) -> tuple[bytes, str]:
    with Image.open(BytesIO(content)) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((max_long_side, max_long_side), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        output = BytesIO()
        normalized_format = image_format.upper()
        if normalized_format == "JPG":
            normalized_format = "JPEG"
        image.save(output, format=normalized_format, quality=quality, optimize=True)
        extension = "jpg" if normalized_format == "JPEG" else normalized_format.lower()
        return output.getvalue(), extension
