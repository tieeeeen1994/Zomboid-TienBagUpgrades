"""Builds the mod's poster and Workshop preview from our item icons and the game's.

    python3 scripts/make_models.py   # first, if the models changed (it renders the item icons)
    python3 scripts/make_poster.py

Writes Contents/mods/TienBagUpgrades/42/poster.png and preview.png (512x512), in the series' look on a pink glow,
pixel art stickers (whole-number scale, thin dark line, white outline) with soft shadows, no text. An ALICE pack
(the game's icon) with our denim pouch and leather strap icons, the game's thread and needle, and a yellow up arrow.
"""

import os

from PIL import Image, ImageDraw, ImageFilter

from make_models import ICON_OUT, REPO, game_icon

MOD = os.path.join(REPO, "Contents", "mods", "TienBagUpgrades", "42")

SS = 4
GLOW = (248, 178, 206)   # pink, lighter in the middle
DARK = (190, 92, 140)
INK = (12, 12, 12, 255)
ACCENT = (255, 205, 80)


def backdrop(size):
    img = Image.new("RGBA", (size, size))
    px = img.load()
    cx, cy, r = size * 0.5, size * 0.45, size * 0.62
    for y in range(size):
        for x in range(size):
            t = min(1.0, ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / r)
            t = t * t * (3 - 2 * t)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(GLOW, DARK)) + (255,)
    return img


def dilate(alpha, px):
    return alpha.filter(ImageFilter.MaxFilter(2 * px + 1)) if px > 0 else alpha


def sticker(icon, scale, ring):
    """Pixel art scaled by a whole number, a thin dark line, then a white outline."""
    art = icon.resize((icon.width * scale, icon.height * scale), Image.NEAREST)
    pad = ring * 3
    canvas = Image.new("RGBA", (art.width + pad * 2, art.height + pad * 2), (0, 0, 0, 0))
    canvas.alpha_composite(art, (pad, pad))
    alpha = canvas.getchannel("A").point(lambda a: 255 if a > 40 else 0)
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    dark = max(1, ring // 3)
    out.paste(Image.new("RGBA", canvas.size, (255, 255, 255, 255)), (0, 0), dilate(alpha, ring + dark))
    out.paste(Image.new("RGBA", canvas.size, INK), (0, 0), dilate(alpha, dark))
    out.alpha_composite(canvas)
    return out


def drop(img, layer, centre, k):
    """Composite a layer centred on a point, with a soft shadow down and right."""
    at = (round(centre[0] - layer.width / 2), round(centre[1] - layer.height / 2))
    blur = max(2, round(8 * k))
    mask = layer.getchannel("A").point(lambda a: a * 170 // 255)
    pad = blur * 3
    sh = Image.new("RGBA", (layer.width + pad * 2, layer.height + pad * 2), (0, 0, 0, 0))
    sh.paste(Image.new("RGBA", layer.size, (0, 0, 0, 255)), (pad, pad), mask)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(sh, (at[0] - pad + round(8 * k), at[1] - pad + round(11 * k)))
    img.alpha_composite(layer, at)


def arrow(size):
    """A bold up arrow in the accent colour with a dark edge."""
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    outer = [(0.5, 0.04), (0.94, 0.5), (0.68, 0.5), (0.68, 0.96), (0.32, 0.96), (0.32, 0.5), (0.06, 0.5)]
    inner = [(0.5, 0.15), (0.81, 0.46), (0.62, 0.46), (0.62, 0.9), (0.38, 0.9), (0.38, 0.46), (0.19, 0.46)]
    d.polygon([(x * big, y * big) for x, y in outer], fill=INK)
    d.polygon([(x * big, y * big) for x, y in inner], fill=ACCENT + (255,))
    return img.resize((size, size), Image.LANCZOS)


def ours(name):
    return Image.open(os.path.join(ICON_OUT, name + ".png")).convert("RGBA")


def poster(size):
    k = size / 512.0
    img = backdrop(size)
    s = max(1, round(9 * k))
    drop(img, sticker(game_icon("Item_AliceBag"), s, s), (size * 0.47, size * 0.48), k)
    small = max(1, round(3 * k))
    drop(img, sticker(game_icon("Item_Thread"), small, small), (size * 0.17, size * 0.2), k)
    drop(img, sticker(game_icon("Item_Needle"), small, small), (size * 0.27, size * 0.14), k)
    mid = max(1, round(5 * k))
    drop(img, sticker(ours("Item_UpgradeWeightReductionLeather"), mid, mid), (size * 0.21, size * 0.76), k)
    drop(img, sticker(ours("Item_UpgradeCapacityJean"), mid, mid), (size * 0.77, size * 0.74), k)
    drop(img, arrow(round(118 * k)), (size * 0.8, size * 0.21), k)
    return img


def main():
    art = poster(512).convert("RGB")
    art.save(os.path.join(MOD, "poster.png"))
    art.save(os.path.join(REPO, "preview.png"))
    print("Wrote poster.png and preview.png")


if __name__ == "__main__":
    main()
