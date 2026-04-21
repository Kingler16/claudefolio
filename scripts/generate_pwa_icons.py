"""
Generiert PWA-Icons aus src/web/static/logo.png.

Produziert eine Mobile-optimierte Variante (dunkler Hintergrund + Glow + Prism zentriert)
in verschiedenen Größen für Web-Manifest, Apple Touch Icon und Notification Badge.

Ausführen:
    source venv/bin/activate
    python scripts/generate_pwa_icons.py
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "src" / "web" / "static"
LOGO_SRC = STATIC / "logo.png"
ICONS_DIR = STATIC / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

# Velora-Palette (Design-System-Tokens)
NIGHT_0 = (3, 5, 16, 255)      # --color-night-0
NIGHT_1 = (8, 12, 28, 255)     # --color-night-1
CYAN_500 = (34, 211, 238, 255) # --color-cyan-500
INDIGO_500 = (99, 102, 241, 255)
AZURE_500 = (14, 165, 233, 255)


def radial_bg(size: int) -> Image.Image:
    """Dunkler Hintergrund mit Cyan/Indigo-Glow in oberer linker Ecke."""
    img = Image.new("RGBA", (size, size), NIGHT_0)
    draw = ImageDraw.Draw(img)

    # Subtiler Verlauf: vertikal von Night-0 nach Night-1 (kaum sichtbar, aber Tiefe)
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(NIGHT_0[0] * (1 - t) + NIGHT_1[0] * t)
        g = int(NIGHT_0[1] * (1 - t) + NIGHT_1[1] * t)
        b = int(NIGHT_0[2] * (1 - t) + NIGHT_1[2] * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Cyan-Glow oben links
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    r = int(size * 0.55)
    gd.ellipse(
        [int(-r * 0.2), int(-r * 0.2), r, r],
        fill=(CYAN_500[0], CYAN_500[1], CYAN_500[2], 90),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(int(size * 0.12)))
    img.alpha_composite(glow)

    # Indigo-Glow unten rechts, schwächer
    glow2 = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow2)
    gd2.ellipse(
        [int(size * 0.45), int(size * 0.5), int(size * 1.2), int(size * 1.2)],
        fill=(INDIGO_500[0], INDIGO_500[1], INDIGO_500[2], 70),
    )
    glow2 = glow2.filter(ImageFilter.GaussianBlur(int(size * 0.14)))
    img.alpha_composite(glow2)

    return img


def render_icon(size: int, motif_ratio: float = 0.72) -> Image.Image:
    """Vollständiges Icon: Hintergrund + zentriertes Logo."""
    bg = radial_bg(size)
    if not LOGO_SRC.exists():
        return bg

    logo = Image.open(LOGO_SRC).convert("RGBA")
    # Skaliere auf motif_ratio-Anteil der Canvas-Breite, höhe proportional
    motif_w = int(size * motif_ratio)
    aspect = logo.height / logo.width
    motif_h = int(motif_w * aspect)
    logo = logo.resize((motif_w, motif_h), Image.LANCZOS)

    # Zentrieren
    offset_x = (size - motif_w) // 2
    offset_y = (size - motif_h) // 2
    bg.alpha_composite(logo, (offset_x, offset_y))
    return bg


def render_badge(size: int = 96) -> Image.Image:
    """Monochrom weißes Abzeichen für Android-Notification (iOS ignoriert)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = size // 2
    draw.ellipse([size // 8, size // 8, size - size // 8, size - size // 8], fill=(255, 255, 255, 230))
    return img


def save_png(img: Image.Image, path: Path, flatten_to_rgb: bool = False) -> None:
    if flatten_to_rgb:
        bg = Image.new("RGB", img.size, NIGHT_0[:3])
        bg.paste(img, mask=img.split()[-1])
        bg.save(path, "PNG", optimize=True)
    else:
        img.save(path, "PNG", optimize=True)
    print(f"wrote {path.relative_to(REPO)}  ({path.stat().st_size // 1024} KB)")


def main() -> None:
    # Standard "any purpose" Icons — Motiv füllt bis 72%
    save_png(render_icon(192, motif_ratio=0.72), ICONS_DIR / "icon-192.png")
    save_png(render_icon(512, motif_ratio=0.72), ICONS_DIR / "icon-512.png")

    # Maskable: 80%-Safe-Zone, also Motiv nur 60% (innerhalb der Safe-Area)
    save_png(render_icon(512, motif_ratio=0.60), ICONS_DIR / "icon-maskable-512.png")

    # Apple Touch Icon: 180×180, kein Alpha (iOS ignoriert Transparenz)
    save_png(render_icon(180, motif_ratio=0.74), ICONS_DIR / "apple-touch-icon.png", flatten_to_rgb=True)

    # Notification Badge (Android)
    save_png(render_badge(96), ICONS_DIR / "icon-badge.png")


if __name__ == "__main__":
    main()
