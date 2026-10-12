"""Server-side image validation, EXIF stripping and thumbnailing (Pillow)."""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import bad_request

Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass
class ProcessedImage:
    data: bytes
    width: int
    height: int


def _encode(img: Image.Image, max_side: int, quality: int) -> ProcessedImage:
    img = ImageOps.exif_transpose(img)  # bake in orientation, then drop all metadata on save
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)  # no exif= → metadata stripped
    return ProcessedImage(out.getvalue(), img.width, img.height)


def process_image(data: bytes, max_side: int = 2048, quality: int = 85, thumb_side: int | None = None):
    """Validate that `data` is a real JPEG/PNG/WEBP; return (processed, thumb|None)."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise bad_request("unsupported_image", "Only JPEG, PNG or WEBP images are allowed")
        img.load()
    except UnidentifiedImageError as e:
        raise bad_request("invalid_image", "File is not a valid image") from e
    except (Image.DecompressionBombError, OSError, SyntaxError) as e:
        raise bad_request("invalid_image", "Image is corrupt or too large") from e
    main = _encode(img.copy(), max_side, quality)
    thumb = _encode(img.copy(), thumb_side, 78) if thumb_side else None
    return main, thumb
