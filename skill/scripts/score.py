"""Score an attempt capture against a reference capture (both made by render_rig.py).

    python score.py --ref REF_DIR --att ATTEMPT_DIR [--out score.json] [--diff DIFF_DIR]

Both captures must share the reference frame (capture the attempt with
`--frame REF_DIR/frame.json`). Metrics:

    sil_iou[view]   silhouette IoU per canonical view            (main pass/fail)
    sil_iou_min     worst view
    depth_agree[v]  share of covered pixels where both surfaces sit within 1% of the
                    diagonal in depth (catches hidden/inner errors silhouettes miss)
    ssim[view]      structural similarity of the shaded views     (reported)
    far_error[v]    share of the reference silhouette wrong by more than 2 px (a missing
                    or extra part, as opposed to outline jitter)
    chamfer         symmetric mean point-to-surface distance / ref diagonal (pass/fail)
    fscore          F-score of surface points at 1% of diagonal    (pass/fail)
    vol_iou         voxel IoU of the inside/outside grids          (reported)
    ok              attempt program ran and produced geometry

PASS (the definition of "accurate" used everywhere in this project):
    ok AND sil_iou_min >= 0.98 AND depth_agree_min >= 0.98 AND far_error_max <= 0.005
       AND chamfer <= 0.01 AND fscore >= 0.95

A crash or empty result scores 0 on everything.

--diff writes, per view, a colour overlay (green = only in reference, red = only in
attempt, grey = both) and a list of the largest error regions in world units, so the
next round can patch the worst region instead of rewriting.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

PASS_SIL_IOU = 0.98
PASS_CHAMFER = 0.01
FSCORE_TAU = 0.01
PASS_DEPTH = 0.98
PASS_FSCORE = 0.95
DEPTH_TOL = 0.01
FAR_PX = 2.0
PASS_FAR = 0.005
N_SURFACE_SAMPLES = 20000
SEED = 1234
VIEW_NAMES = ("front", "right", "top", "iso")


def sample_surface(verts, faces, n, seed=SEED):
    rng = np.random.default_rng(seed)
    tri = verts[faces]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    if area.sum() <= 0:
        return tri[:, 0]
    idx = rng.choice(len(faces), size=n, p=area / area.sum())
    r1 = np.sqrt(rng.random(n))
    r2 = rng.random(n)
    t = tri[idx]
    return (1 - r1)[:, None] * t[:, 0] + (r1 * (1 - r2))[:, None] * t[:, 1] + (r1 * r2)[:, None] * t[:, 2]


def point_to_surface(pts, verts, faces):
    """Exact distance from each point to the nearest point on a triangle mesh."""
    import bpy  # noqa: F401  (makes mathutils importable from the bpy wheel)
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    bvh = BVHTree.FromPolygons([tuple(v) for v in verts], [tuple(f) for f in faces], all_triangles=True)
    out = np.empty(len(pts))
    for i, p in enumerate(pts):
        hit = bvh.find_nearest(Vector(p))
        out[i] = hit[3] if hit[0] is not None else np.inf
    return out


def chamfer_fscore(ref_pts, att_pts, diag, ref_mesh, att_mesh):
    d_ra = point_to_surface(ref_pts, *att_mesh)
    d_ar = point_to_surface(att_pts, *ref_mesh)
    chamfer = 0.5 * (d_ra.mean() + d_ar.mean()) / diag
    tau = FSCORE_TAU * diag
    recall = float((d_ra < tau).mean())
    precision = float((d_ar < tau).mean())
    f = 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)
    return float(chamfer), float(f), precision, recall, float(np.percentile(d_ra, 95) / diag), float(np.percentile(d_ar, 95) / diag)


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return 1.0 if u == 0 else float(np.logical_and(a, b).sum() / u)


def depth_agree(rm, am, rd, ad, diag, tol=DEPTH_TOL):
    """Share of pixels covered by either view where both hit at nearly the same depth.

    Catches errors silhouettes miss: a missing inner shelf, a hole that is too shallow,
    a part that is in the right outline but at the wrong distance from the camera."""
    u = rm | am
    if u.sum() == 0:
        return 1.0
    both = rm & am
    good = both & (np.abs(np.nan_to_num(rd) - np.nan_to_num(ad)) <= tol * diag)
    return float(good.sum() / u.sum())


def far_error(rm, am, px_tol=FAR_PX):
    """Share of the reference silhouette that is wrong by more than px_tol pixels.

    Outline jitter (a slightly wrong size) stays within a pixel or two of the other
    silhouette and is ignored here; a missing spoke, an extra handle or a part in the
    wrong place leaves pixels far from the other silhouette and is counted."""
    import cv2

    ref_area = max(1, int(rm.sum()))
    far = 0
    for a, b in ((rm, am), (am, rm)):
        err = a & ~b
        if not err.any():
            continue
        if not b.any():
            far += int(err.sum())
            continue
        dist = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 5)
        far += int((err & (dist > px_tol)).sum())
    return far / ref_area


def ssim_gray(a, b):
    from skimage.metrics import structural_similarity

    return float(structural_similarity(a, b, data_range=255))


def error_regions(ref_m, att_m, frame, view, top_k=3):
    """Largest connected regions of disagreement, reported in world units."""
    import cv2

    from render_rig import VIEWS, view_basis  # same folder

    res = ref_m.shape[0]
    px = frame["view_width"] / res
    fwd, right, up = view_basis(*VIEWS[view])
    c = np.array(frame["center"])
    out = []
    for kind, m in (("missing", ref_m & ~att_m), ("extra", att_m & ~ref_m)):
        n, lab, stats, cent = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if area < 4:
                continue
            cx, cy = cent[i]
            u = (cx + 0.5 - res / 2) * px
            v = (res / 2 - (cy + 0.5)) * px
            world = c + right * u + up * v
            out.append({
                "view": view, "kind": kind, "pixels": int(area),
                "share_of_ref": round(area / max(1, ref_m.sum()), 4),
                "centre_world_on_view_plane": [round(float(x_), 4) for x_ in world],
                "size_world": [round(float(w * px), 4), round(float(h * px), 4)],
                "screen_axes": {"right": [round(float(a), 3) for a in right], "up": [round(float(a), 3) for a in up]},
            })
    out.sort(key=lambda r: -r["pixels"])
    return out[:top_k]


def score(ref_dir, att_dir, diff_dir=None):
    att_status = json.load(open(os.path.join(att_dir, "status.json")))
    frame = json.load(open(os.path.join(ref_dir, "frame.json")))
    zero = {"ok": False, "pass": False, "sil_iou": {v: 0.0 for v in VIEW_NAMES}, "sil_iou_min": 0.0,
            "sil_iou_mean": 0.0, "depth_agree_min": 0.0, "far_error_max": 1.0, "chamfer": 1.0, "fscore": 0.0, "vol_iou": 0.0,
            "error": att_status.get("error")}
    if not att_status.get("ok"):
        return zero
    rv = np.load(os.path.join(ref_dir, "views.npz"))
    av = np.load(os.path.join(att_dir, "views.npz"))
    res = {"ok": True, "sil_iou": {}, "depth_agree": {}, "far_error": {}, "ssim": {}}
    import cv2

    for v in VIEW_NAMES:
        res["sil_iou"][v] = round(iou(rv[f"{v}_mask"], av[f"{v}_mask"]), 5)
        res["far_error"][v] = round(far_error(rv[f"{v}_mask"], av[f"{v}_mask"]), 5)
        res["depth_agree"][v] = round(depth_agree(rv[f"{v}_mask"], av[f"{v}_mask"], rv[f"{v}_depth"],
                                                  av[f"{v}_depth"], frame["diag"]), 5)
        a = cv2.imread(os.path.join(ref_dir, f"view_{v}.png"), 0)
        b = cv2.imread(os.path.join(att_dir, f"view_{v}.png"), 0)
        res["ssim"][v] = round(ssim_gray(a, b), 4)
    res["sil_iou_min"] = min(res["sil_iou"].values())
    res["depth_agree_min"] = min(res["depth_agree"].values())
    res["far_error_max"] = max(res["far_error"].values())
    res["sil_iou_mean"] = round(float(np.mean(list(res["sil_iou"].values()))), 5)
    rg = np.load(os.path.join(ref_dir, "geometry.npz"))
    ag = np.load(os.path.join(att_dir, "geometry.npz"))
    rp = sample_surface(rg["verts"], rg["faces"], N_SURFACE_SAMPLES)
    ap_ = sample_surface(ag["verts"], ag["faces"], N_SURFACE_SAMPLES)
    ch, f, p, r, p95_ra, p95_ar = chamfer_fscore(rp, ap_, frame["diag"], (rg["verts"], rg["faces"]),
                                                 (ag["verts"], ag["faces"]))
    res.update(chamfer=round(ch, 6), fscore=round(f, 4), precision=round(p, 4), recall=round(r, 4),
               p95_ref_to_att=round(p95_ra, 5), p95_att_to_ref=round(p95_ar, 5))
    ro, ao = os.path.join(ref_dir, "occupancy.npz"), os.path.join(att_dir, "occupancy.npz")
    if os.path.exists(ro) and os.path.exists(ao):
        res["vol_iou"] = round(iou(np.load(ro)["occ"], np.load(ao)["occ"]), 4)
    a_dims = np.array(att_status.get("own_dims", [0, 0, 0]))
    res["dims_ratio"] = [round(float(x), 4) for x in a_dims / np.maximum(np.array(frame["dims"]), 1e-9)]
    res["pass"] = bool(res["sil_iou_min"] >= PASS_SIL_IOU and res["depth_agree_min"] >= PASS_DEPTH
                       and res["far_error_max"] <= PASS_FAR                       and res["chamfer"] <= PASS_CHAMFER and res["fscore"] >= PASS_FSCORE)
    res["worst_view"] = min(res["sil_iou"], key=res["sil_iou"].get)
    if diff_dir:
        os.makedirs(diff_dir, exist_ok=True)
        regions = []
        tiles = []
        for v in VIEW_NAMES:
            rm, am = rv[f"{v}_mask"], av[f"{v}_mask"]
            img = np.full(rm.shape + (3,), 255, np.uint8)
            img[rm & am] = (170, 170, 170)
            img[rm & ~am] = (60, 200, 60)   # BGR green: missing in attempt
            img[am & ~rm] = (60, 60, 230)   # BGR red: extra in attempt
            cv2.putText(img, f"{v} {res['sil_iou'][v]:.3f}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            cv2.imwrite(os.path.join(diff_dir, f"diff_{v}.png"), img)
            tiles.append(img)
            regions += error_regions(rm, am, frame, v)
        cv2.imwrite(os.path.join(diff_dir, "diff_all.png"), np.hstack(tiles))
        regions.sort(key=lambda r: -r["pixels"])
        res["worst_regions"] = regions[:6]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--att", required=True)
    ap.add_argument("--out")
    ap.add_argument("--diff")
    a = ap.parse_args(argv)
    r = score(a.ref, a.att, a.diff)
    s = json.dumps(r, indent=2)
    if a.out:
        open(a.out, "w").write(s)
    print(s)


if __name__ == "__main__":
    main()
