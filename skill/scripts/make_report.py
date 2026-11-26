"""Illustrated PDF reports (matplotlib PdfPages).

  python skill/scripts/make_report.py character  OUT.pdf
  python skill/scripts/make_report.py dataset    OUT.pdf [--versions baseline-noskill loop-v1 ...]

character: reference vs every character version, silhouette overlays, metrics and round history, turnarounds.
dataset:   per held-out sample: reference input, the best attempt's preview render, and the revealed GT
           (rig view 0, GT vs attempt aligned), with per-version scores; plus summary charts.
Reports contain dataset-derived images (CC BY-NC-SA) or third-party reference art: keep them private, never commit.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
A4 = (8.27, 11.69)


def img(path):
    import cv2
    p = Path(path)
    if not p.exists():
        return None
    im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 3 and im.shape[2] == 4:  # RGBA render -> composite on white
        a = im[..., 3:4] / 255.0
        im = (im[..., :3] * a + 255 * (1 - a)).astype(np.uint8)
    return im[..., ::-1] if im.ndim == 3 else im


def show(ax, im, title=""):
    ax.axis("off")
    if im is not None:
        ax.imshow(im, cmap="gray" if im.ndim == 2 else None)
    ax.set_title(title, fontsize=8)


def text_page(pdf, title, lines):
    fig = plt.figure(figsize=A4)
    fig.text(0.07, 0.95, title, fontsize=16, weight="bold", va="top")
    fig.text(0.07, 0.90, "\n".join(lines), fontsize=9, va="top", family="monospace", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


# ----------------------------------------------------------------------------- character
def character(out):
    D = ROOT / "runs" / "custom" / "suspenders_guy"
    versions = [("v1 parametric (r1)", D / "r1", "beauty.png"), ("v1 parametric (final)", D / "final", "beauty.png"),
                ("v2 photo-fit", D / "v2", "front.png")]
    metrics = {name: json.loads((d / "compare.json").read_text()) for name, d, _ in versions if (d / "compare.json").exists()}
    with PdfPages(out) as pdf:
        lines = ["Reference: single front 3/4 image of a stylized character (third-party art, kept private).", "",
                 f"{'version':26s} {'IoU':>6s} {'head':>6s} {'torso':>6s} {'legs':>6s} {'SSIM':>6s} {'LPIPS':>6s} {'colErr':>6s}"]
        for n, m in metrics.items():
            lines.append(f"{n:26s} {m.get('iou_aligned', 0):6.3f} {m.get('iou_head', 0):6.3f} {m.get('iou_torso_arms', 0):6.3f} "
                         f"{m.get('iou_legs', 0):6.3f} {m.get('ssim', float('nan')):6.3f} {m.get('lpips', float('nan')):6.3f} "
                         f"{m.get('color_err_in_mask', float('nan')):6.3f}")
        lines += ["", "IoU = silhouette overlap with the reference (1.0 = identical outline).",
                  "SSIM higher = more similar; LPIPS lower = more similar (perceptual); colErr = mean |RGB diff| in the silhouette.", "",
                  "v1: primitives + skin-modifier volumes, flat procedural colours, built only from measured proportions.",
                  "v2: geometry inflated from the reference silhouette (round cross-sections), colours projected from",
                  "    the photo through the front camera. The front view therefore matches closely BY CONSTRUCTION;",
                  "    back and sides are inferred (front texture smears across the sides).",
                  "Neither version is a sculpted replica: no edge flow, no real back view, no cloth simulation."]
        text_page(pdf, "Character replica report", lines)
        fig, axs = plt.subplots(2, 2, figsize=A4)
        show(axs[0, 0], img(D / "reference.jpg"), "reference")
        show(axs[0, 1], img(D / "final" / "beauty.png"), f"v1 final  IoU {metrics.get('v1 parametric (final)', {}).get('iou_aligned', 0):.3f}")
        show(axs[1, 0], img(D / "v2" / "front.png"), f"v2 photo-fit  IoU {metrics.get('v2 photo-fit', {}).get('iou_aligned', 0):.3f}")
        show(axs[1, 1], img(D / "ref_mask_clean.png"), "reference silhouette (mask used for scoring)")
        fig.suptitle("Front view: reference vs models", fontsize=12)
        pdf.savefig(fig); plt.close(fig)
        fig, axs = plt.subplots(len(versions), 1, figsize=A4)
        for ax, (n, d, _) in zip(axs, versions):
            show(ax, img(d / "compare.jpg"), f"{n}: reference | model | overlay (white both, green ref only, red model only)")
        pdf.savefig(fig); plt.close(fig)
        rounds = [(f"r{i}", D / f"r{i}") for i in range(1, 6)] + [("final", D / "final"), ("v2", D / "v2")]
        vals = [(n, json.loads((d / "compare.json").read_text())["iou_aligned"]) for n, d in rounds if (d / "compare.json").exists()]
        fig, ax = plt.subplots(figsize=(8.27, 4))
        ax.plot([v[0] for v in vals], [v[1] for v in vals], "o-")
        ax.set_ylim(0, 1); ax.set_ylabel("silhouette IoU vs reference"); ax.grid(alpha=0.3)
        ax.set_title("Improvement log by round")
        pdf.savefig(fig); plt.close(fig)
        for n, d in (("v1 parametric", D / "final"), ("v2 photo-fit", D / "v2")):
            turns = sorted(d.glob("turn_*.png"))
            if turns:
                fig, axs = plt.subplots(1, len(turns), figsize=(11.69, 4))
                for ax, t in zip(np.atleast_1d(axs), turns):
                    show(ax, img(t), t.stem.replace("turn_", "azimuth "))
                fig.suptitle(f"{n}: turnaround (shows how much of the 3D shape is real vs inferred)")
                pdf.savefig(fig); plt.close(fig)


# ----------------------------------------------------------------------------- dataset
def load_scores(version):
    p = ROOT / "evals" / f"scores_{version}.csv"
    return {r["sample"]: r for r in csv.DictReader(open(p))} if p.exists() else {}


def best_round(key, version):
    best, br = -1, None
    for d in sorted((ROOT / "runs" / "attempts" / key).glob("round_*")):
        s = d / "score.json"
        if s.exists():
            j = json.loads(s.read_text())
            if j.get("skill_version", version) in (version, "baseline-noskill") or version == "any":
                v = j["aligned"].get("iou_min", 0)
                if v > best:
                    best, br = v, d
    return br


def dataset(out, versions):
    ids = [l.strip() for l in open(ROOT / "evals" / "baseline_list.txt") if l.strip()]
    scores = {v: load_scores(v) for v in versions}
    with PdfPages(out) as pdf:
        lines = [f"Fixed held-out list: {len(ids)} samples (evals/baseline_list.txt). Metric: aligned silhouette IoU,",
                 "worst of 4 rig views (1.0 = identical). Pass bar 0.98.", ""]
        for v in versions:
            vals = [float(scores[v][i]["iou_min"]) for i in ids if i in scores[v] and scores[v][i].get("iou_min")]
            if vals:
                lines.append(f"{v:20s} mean {np.mean(vals):.3f}  median {np.median(vals):.3f}  pass {sum(x >= 0.98 for x in vals)}/{len(vals)}")
        lines += ["", "Per-sample pages: reference input (what the attempter saw) | best attempt (preview render) |",
                  "ground truth revealed AFTER the final attempt (rig view, GT) | attempt on the same rig view.",
                  "Dataset images are CC BY-NC-SA 4.0: this PDF is private, non-commercial, never committed."]
        text_page(pdf, "3D replication benchmark report", lines)
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        x = np.arange(len(ids))
        w = 0.8 / max(len(versions), 1)
        for j, v in enumerate(versions):
            ax.bar(x + j * w, [float(scores[v].get(i, {}).get("iou_min") or 0) for i in ids], w, label=v)
        ax.set_xticks(x + w * (len(versions) - 1) / 2)
        ax.set_xticklabels([i.split("/")[-1].replace("Factory_geo", "").replace("_geo", "") for i in ids], rotation=90, fontsize=6)
        ax.axhline(0.98, color="k", ls="--", lw=0.8, label="pass bar")
        ax.set_ylim(0, 1); ax.legend(); ax.set_title("Aligned IoU per held-out sample")
        fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
        per_page = 4
        for k in range(0, len(ids), per_page):
            fig, axs = plt.subplots(per_page, 4, figsize=A4)
            for row, sid in enumerate(ids[k:k + per_page]):
                key = sid.split("/")[-1]
                att = ROOT / "runs" / "attempts" / key
                br = best_round(key, "any")
                sc = "  ".join(f"{v}:{float(scores[v].get(sid, {}).get('iou_min') or 0):.3f}" for v in versions)
                show(axs[row, 0], img(att / "input" / "view_00.png"), f"{key[:28]}\nreference")
                pv = img(br / "preview.jpg") if br else None
                show(axs[row, 1], pv[: pv.shape[0] // 2, pv.shape[1] // 4: pv.shape[1] // 2] if pv is not None else None, f"attempt ({br.name if br else '-'})")
                show(axs[row, 2], img(ROOT / "runs" / "sealed" / key / "gt_r" / "view_00.png"), "GT (revealed)")
                show(axs[row, 3], img(br / "aligned_r" / "view_00.png") if br else None, sc)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)


def training(out):
    """Practice log: per train sample, reference | best attempt | GT (revealed) | diff, scores per round, lessons."""
    log = [json.loads(l) for l in open(ROOT / "runs" / "training_log.jsonl")]
    samples = list(dict.fromkeys(r["sample"] for r in log if r["event"] == "round"))
    with PdfPages(out) as pdf:
        lines = [f"Practice samples (TRAIN split only): {len(samples)}. Ground truth revealed only after the final round.", ""]
        lines.append(f"{'sample':30s} {'rounds':>6s} {'first':>6s} {'best':>6s}")
        for sid in samples:
            sc = [r["iou_min"] or 0 for r in log if r["event"] == "round" and r["sample"] == sid]
            lines.append(f"{sid.split('/')[-1].replace('Factory_geo', ''):30s} {len(sc):6d} {sc[0]:6.3f} {max(sc):6.3f}")
        tags = {}
        for r in log:
            if r["event"] == "lesson":
                tags[r["tag"]] = tags.get(r["tag"], 0) + 1
        lines += ["", "Lesson tags: " + ", ".join(f"{k} x{v}" for k, v in sorted(tags.items())), "",
                  "Pattern library status (train evidence only): 0 banked, 7 candidates, 1 cut after a failed held-out test.",
                  "See skill/references/patterns.md (private)."]
        text_page(pdf, "Training log (Milestone 4 practice)", lines)
        for sid in samples:
            k = sid.split("/")[-1]
            att = ROOT / "runs" / "attempts" / k
            fig = plt.figure(figsize=A4)
            gs = fig.add_gridspec(3, 2, height_ratios=[1, 2.2, 0.9])
            show(fig.add_subplot(gs[0, 0]), img(att / "input" / "sheet.jpg"), "reference inputs (4 views)")
            br = max(att.glob("round_*"), key=lambda d: json.loads((d / "score.json").read_text())["aligned"].get("iou_min", 0))
            show(fig.add_subplot(gs[0, 1]), img(br / "preview.jpg"), f"best attempt {br.name} (ref | mine per view)")
            show(fig.add_subplot(gs[1, :]), img(att / "reveal.jpg"), "GT (revealed) | best attempt | diff (green GT only, red attempt only)")
            sc = [f"r{r['round']}: {r['iou_min']:.3f}" for r in log if r["event"] == "round" and r["sample"] == sid]
            ls = [f"[{r['tag']}] {r['text']}" for r in log if r["event"] == "lesson" and r["sample"] == sid]
            import textwrap
            body = "rounds: " + ", ".join(sc) + "\n" + "\n".join(textwrap.fill(x, 110) for x in ls)
            ax = fig.add_subplot(gs[2, :]); ax.axis("off")
            ax.text(0, 1, body, fontsize=7, va="top", family="monospace")
            fig.suptitle(k, fontsize=11)
            pdf.savefig(fig); plt.close(fig)


if __name__ == "__main__":
    kind, out = sys.argv[1], sys.argv[2]
    if kind == "character":
        character(out)
    elif kind == "training":
        training(out)
    else:
        vs = sys.argv[sys.argv.index("--versions") + 1:] if "--versions" in sys.argv else ["baseline-noskill", "loop-v1"]
        dataset(out, vs)
    print(f"wrote {out}")
