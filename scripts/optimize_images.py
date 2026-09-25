#!/usr/bin/env python3
"""Convert teaser images to WebP (max 800 px wide) and update _data/publications.yml.

Usage: python3 scripts/optimize_images.py papers/<id>.png [...]
"""
import os
import sys

import yaml
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_publications import PUBS, dump  # noqa: E402

pubs_text = open(PUBS, encoding="utf-8").read()
header = "".join(l for l in pubs_text.splitlines(True) if l.startswith("#"))
pubs = yaml.safe_load(pubs_text)
for src in sys.argv[1:]:
    dst = os.path.splitext(src)[0] + ".webp"
    im = Image.open(src)
    im = im.convert("RGBA" if im.mode in ("P", "LA", "RGBA") else "RGB")
    if im.width > 800:
        im = im.resize((800, round(im.height * 800 / im.width)), Image.LANCZOS)
    im.save(dst, "WEBP", quality=80, method=6)
    if src != dst:
        os.remove(src)
    for p in pubs:
        if p.get("image") == src:
            p["image"] = dst
    print("%s -> %s (%d KB)" % (src, dst, os.path.getsize(dst) // 1024))
dump(PUBS, pubs, header)
