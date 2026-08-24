# Brand masters

Full-resolution sources. Not served — `frontend/assets/` holds the optimised
copies the page actually loads.

- `munai-banner-notext.png` — 2544x416 banner with the "Empowering Humans
  through AI..." lettering removed. The type sat on plain brushed metal, so
  the repair rebuilds that area by mirror-tiling the clean band above it:
  brushed grain is a vertical pattern, so tiling reproduces it exactly where
  blurring or diffusion would smear it. The leaves, the robot hand and every
  sparkle are untouched.

Regenerate the served copy after editing a master:

    python -c "from PIL import Image; im=Image.open(r'brand/munai-banner-notext.png'); im.thumbnail((2000,2000), Image.LANCZOS); im.convert('RGB').save(r'frontend/assets/munai-banner.jpg', quality=80, optimize=True, progressive=True)"
