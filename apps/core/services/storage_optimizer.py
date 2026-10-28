"""
# // ==============================================================================
# // KCC CLASSSTAMP - STORAGE OPTIMIZER SERVICE
# // ==============================================================================
# // Subsystem: Upload Pipeline Media Optimization (A-16)
# // Description: Converts uploaded COR/ID proof images to compact WebP on
# //   ingestion. Raster images are downscaled to a max dimension and re-encoded
# //   at quality 80. Non-image files (PDFs, etc.) and unreadable/corrupt files
# //   pass through unchanged so registration never breaks on a bad upload.
# // ==============================================================================
"""

import io

from django.core.files.base import ContentFile

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - Pillow is pinned in requirements.txt
    Image = None
    UnidentifiedImageError = (OSError,)

WEBP_MAX_DIMENSION = 1600
WEBP_QUALITY = 80

RASTER_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff')


def optimize_proof_upload(uploaded_file):
    """
    // Convert an uploaded proof image to WebP; return non-images untouched.
    // Returns the original file object when conversion fails or is not applicable.
    """
    if uploaded_file is None:
        return None

    name = getattr(uploaded_file, 'name', '') or ''
    if not name.lower().endswith(RASTER_EXTENSIONS):
        return uploaded_file

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()
        image = image.convert('RGB')
        image.thumbnail((WEBP_MAX_DIMENSION, WEBP_MAX_DIMENSION))

        buffer = io.BytesIO()
        image.save(buffer, format='WEBP', quality=WEBP_QUALITY, method=6)
        buffer.seek(0)

        stem = name.rsplit('.', 1)[0]
        return ContentFile(buffer.read(), name=f'{stem}.webp')
    except (UnidentifiedImageError, OSError, ValueError):
        uploaded_file.seek(0)
        return uploaded_file
