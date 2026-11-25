"""Compare a render round with the reference photo.

  python custom/suspenders_guy/compare.py REF.jpg REF_MASK.png ROUND_DIR
Prints silhouette IoU (absolute and bbox-aligned) and per-band IoU (head / torso / legs),
and writes ROUND_DIR/compare.jpg: reference | beauty render | overlay (green = reference only,
red = model only, white = both).
"""
import json
import sys

import cv2
import numpy as np


def bbox(m):
    ys, xs = np.nonzero(m)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def align(src, ref):
    """Scale/translate src mask so its bbox matches ref's bbox (aspect kept, height matched)."""
    x0, y0, x1, y1 = bbox(src)
    rx0, ry0, rx1, ry1 = bbox(ref)
    s = (ry1 - ry0) / (y1 - y0)
    crop = src[y0:y1, x0:x1].astype(np.uint8) * 255
    crop = cv2.resize(crop, (max(1, int(round((x1 - x0) * s))), ry1 - ry0), interpolation=cv2.INTER_AREA) > 127
    out = np.zeros_like(ref)
    cx = (rx0 + rx1) // 2 - crop.shape[1] // 2
    xa, xb = max(cx, 0), min(cx + crop.shape[1], ref.shape[1])
    out[ry0:ry1, xa:xb] = crop[:, xa - cx:xb - cx]
    return out


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def main(ref_p, mask_p, rd):
    ref = cv2.imread(ref_p)
    rm = cv2.imread(mask_p, cv2.IMREAD_GRAYSCALE) > 127
    sil = cv2.imread(f"{rd}/silhouette.png", cv2.IMREAD_UNCHANGED)[..., 3] > 127
    sil = cv2.resize(sil.astype(np.uint8), rm.shape[::-1], interpolation=cv2.INTER_NEAREST) > 0
    al = align(sil, rm)
    y0, y1 = bbox(rm)[1], bbox(rm)[3]
    h = y1 - y0
    bands = {"head": (0, 0.18), "torso_arms": (0.18, 0.6), "legs": (0.6, 1.0)}
    res = {"iou_abs": round(iou(sil, rm), 4), "iou_aligned": round(iou(al, rm), 4)}
    for k, (a, b) in bands.items():
        sl = slice(y0 + int(a * h), y0 + int(b * h))
        res[f"iou_{k}"] = round(iou(al[sl], rm[sl]), 4)
    ov = np.zeros((*rm.shape, 3), np.uint8)
    ov[rm & ~al] = (0, 200, 0)
    ov[al & ~rm] = (0, 0, 220)
    ov[al & rm] = (230, 230, 230)
    beauty = cv2.resize(cv2.imread(f"{rd}/beauty.png"), rm.shape[::-1])
    cv2.imwrite(f"{rd}/compare.jpg", np.hstack([ref, beauty, ov]), [cv2.IMWRITE_JPEG_QUALITY, 88])
    (__import__("pathlib").Path(rd) / "compare.json").write_text(json.dumps(res))
    print(json.dumps(res))


if __name__ == "__main__":
    main(*sys.argv[1:4])
