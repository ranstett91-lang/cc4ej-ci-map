#!/usr/bin/env python3
"""Build the CC4EJ header logo and PWA icon set from the approved badge art."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = ROOT / "assets" / "logo"
RASTER_SOURCE_PATH = LOGO_DIR / "cc4ej-badge-source-raster.png"
NORMALIZED_BADGE_PATH = LOGO_DIR / "cc4ej-badge-source.png"
ASSET_VERSION = "9"
CREAM = "#f8f6ef"


def versioned_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}-v{ASSET_VERSION}{path.suffix}")


def crop_non_black_edges(img: Image.Image) -> Image.Image:
    """Remove export letterboxing while preserving the full badge artwork."""
    pixels = img.load()
    min_x, min_y = img.size
    max_x = max_y = -1

    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            if a > 0 and (r > 20 or g > 20 or b > 20):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if max_x < 0 or max_y < 0:
        raise ValueError(f"source image has no visible content: {RASTER_SOURCE_PATH}")

    return img.crop((min_x, min_y, max_x + 1, max_y + 1))


def load_badge(size: int) -> Image.Image:
    if not RASTER_SOURCE_PATH.exists():
        raise FileNotFoundError(f"missing raster source: {RASTER_SOURCE_PATH}")

    source = Image.open(RASTER_SOURCE_PATH).convert("RGBA")
    badge = crop_non_black_edges(source)
    return ImageOps.pad(
        badge,
        (size, size),
        method=Image.Resampling.LANCZOS,
        color=ImageColor.getrgb(CREAM),
        centering=(0.5, 0.5),
    )


def build_icon(badge: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), ImageColor.getrgb(CREAM) + (255,))

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        [size * 0.18, size * 0.22, size * 0.82, size * 0.86],
        fill=(9, 35, 54, 56),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=size * 0.03))
    canvas.alpha_composite(shadow)

    fitted_badge = badge.resize((round(size * 0.94), round(size * 0.94)), Image.Resampling.LANCZOS)
    x = (size - fitted_badge.width) // 2
    y = round(size * 0.03)
    canvas.alpha_composite(fitted_badge, (x, y))
    return canvas


def write_asset(image: Image.Image, path: Path, *, write_versioned: bool = True) -> None:
    image.save(path)
    if write_versioned:
        image.save(versioned_path(path))


def main() -> None:
    LOGO_DIR.mkdir(parents=True, exist_ok=True)

    badge = load_badge(1400)
    badge.save(NORMALIZED_BADGE_PATH)

    header_logo_path = ROOT / "cc4ej-logo.png"
    icon_512_path = ROOT / "icon-512.png"
    icon_192_path = ROOT / "icon-192.png"
    icon_apple_2_path = ROOT / "icon-apple-2.png"
    icon_apple_path = ROOT / "icon-apple.png"

    write_asset(badge.resize((1024, 1024), Image.Resampling.LANCZOS), header_logo_path)
    write_asset(build_icon(badge, 512), icon_512_path)
    write_asset(build_icon(badge, 192), icon_192_path)
    write_asset(build_icon(badge, 180), icon_apple_2_path)
    write_asset(build_icon(badge, 180), icon_apple_path, write_versioned=False)

    print("Wrote logo assets:")
    for path in [
        NORMALIZED_BADGE_PATH,
        header_logo_path,
        versioned_path(header_logo_path),
        icon_512_path,
        versioned_path(icon_512_path),
        icon_192_path,
        versioned_path(icon_192_path),
        icon_apple_2_path,
        versioned_path(icon_apple_2_path),
        icon_apple_path,
    ]:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
