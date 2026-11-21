# Changelog

## m1-harness (Milestone 1)
- venv (Python 3.13, `bpy==5.1.2`; PyPI has no 5.0 build), pinned in `requirements.txt`.
- `skill/scripts/shard_manager.py`: one-shard download/extract/delete, SQLite manifest, exact 10% held-out split (salted hash rank, assigned on first touch).
- `skill/scripts/run_sample.py`: isolated subprocess runner for Blender code or GLB import -> world-space triangle mesh (.npz).
- `skill/scripts/render_rig.py`: rig-v1, 4 ortho views (az 45/135/225/315, el 30), Workbench studio light, 512 px, GT-derived frame.
- `skill/scripts/score.py`: silhouette IoU per view, SSIM, LPIPS (AlexNet), chamfer (% of GT bbox diagonal), volume ratio (watertight only), crash = 0.
- `skill/scripts/validate_scorer.py`: Milestone 1 exit test with a SEED=1 negative control.
- Blender pinned to the official 5.0.1 binary (`BLENDER_BIN`), the dataset's target version; scipy + matplotlib installed into its bundled Python. The pip `bpy` 5.1.2 path is kept as a fallback.

## baseline-noskill (Milestone 2)
- `skill/scripts/attempt.py`: sealed attempt workflow (inputs copied out, GT preprocessed into `runs/sealed/`), aligned + absolute scoring, logged to the manifest.
- `skill/scripts/scoreboard.py`: per-sample scores CSV + aggregate scoreboard rows.
- `skill/scripts/calibrate_ref_camera.py`: experimental reference-camera fit (background masks proved unreliable; not used for scoring).
- `skill/references/frame_convention.md`: dataset frame / reference camera convention, measured on train samples.
- Baseline on 50 held-out samples: mean aligned IoU-min 0.672, 0/50 pass (see `evals/m2_baseline.md`).
