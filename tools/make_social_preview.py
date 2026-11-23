"""Generates docs/social-preview.png (1280x640) for the GitHub repository card.

Run:  .venv\\Scripts\\python tools\\make_social_preview.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1280, 640


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default()


def bold(s):
    return font(["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], s)


def reg(s):
    return font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], s)


def main():
    img = Image.new("RGB", (W, H), "#0b0b10")
    glow = Image.new("RGB", (W, H), "#0b0b10")
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-200, -250, 600, 450), fill="#1d2a55")
    gd.ellipse((800, 300, 1500, 900), fill="#3a1d55")
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(120)), 0.9)
    d = ImageDraw.Draw(img)

    logo = Image.open(ROOT / "web" / "icon-512.png").convert("RGBA").resize((96, 96), Image.LANCZOS)
    img.paste(logo, (64, 70), logo)
    d.text((176, 78), "MiniDesktop", font=bold(68), fill="#ffffff")
    d.text((66, 200), "Turn any tablet into a second", font=reg(36), fill="#e6e6ef")
    d.text((66, 246), "screen for your Windows PC", font=reg(36), fill="#e6e6ef")
    y = 324
    for f in ("Media & volume control", "Discord friends & mic", "Live CPU / GPU stats", "Claude Code & git dashboard"):
        d.ellipse((70, y + 11, 82, y + 23), fill="#4cc2ff")
        d.text((96, y), f, font=reg(27), fill="#c9c9d6")
        y += 44
    x = 66
    for chip in ("Android", "iPad", "HarmonyOS", "Windows 10/11"):
        tw = d.textlength(chip, font=bold(22))
        d.rounded_rectangle((x, 530, x + tw + 32, 572), radius=21, fill="#1f2433", outline="#3a4258")
        d.text((x + 16, 537), chip, font=bold(22), fill="#ffffff")
        x += tw + 46

    shot = Image.open(ROOT / "docs" / "screenshots" / "normal-mode.jpg").convert("RGB")
    sw = 640
    sh = int(shot.height * sw / shot.width)
    shot = shot.resize((sw, sh), Image.LANCZOS)
    fx, fy, pad = 590, (H - sh) // 2 - 12, 18
    frame = Image.new("RGBA", (sw + pad * 2, sh + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, sw + pad * 2 - 1, sh + pad * 2 - 1), radius=28, fill="#16161c", outline="#3a3a46", width=2)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((fx + 10, fy + 24, fx + sw + pad * 2 + 10, fy + sh + pad * 2 + 24), radius=28, fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(18)))
    img.paste(frame, (fx, fy), frame)
    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, sh - 1), radius=10, fill=255)
    img.paste(shot, (fx + pad, fy + pad), mask)
    out = ROOT / "docs" / "social-preview.png"
    img.convert("RGB").save(out, optimize=True)
    print("saved", out)


if __name__ == "__main__":
    main()
