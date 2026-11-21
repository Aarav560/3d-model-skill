# 3D Modeling Self-Improvement Skill: Build Spec for Claude Code

Read this whole file before writing any code. Build one milestone at a time, run its exit test, report the result, then stop and wait unless told to continue.

## 1. Goal

Build a Claude skill that measurably improves at turning reference images into Blender-built 3D replicas. Claude's weights do not change. The "learning" lives in files: a skill folder, a pattern library, and a scoreboard that proves progress on a held-out test set.

Four capabilities, in this order:

1. Replicate a dataset sample from its reference render, scored against sealed ground truth.
2. Replicate any real photo as a 3D model.
3. Produce advanced environment renders (lighting, materials, camera).
4. Build custom models steered by a reference image.

## 2. Verified facts (checked Nov 21, 2026)

- Dataset: `3dcodeverse/3dcodeverse-2m` on Hugging Face. 2.03M executable 3D programs (Blender Python, CadQuery, Three.js, GLSL, OpenSCAD, URDF). Repo storage about 1.45 TB total.
- Layout: `.tar` shards plus a `metadata.parquet` per subset, e.g. `3dcodebench/factories_geo/samples-000.tar`. Subsets of interest: `factories_geo`, `factories_tex`, `instances_geo`, `thingiverse/blender_5_0`, `thingiverse/blender_5_1_2_parametric`.
- License: CC BY-NC-SA 4.0, non-commercial research. Per-source licenses also apply. The dataset card has an access form; the user may need to submit it and accept the terms with their Hugging Face account.
- Related, smaller: `YipengGao/3DCode` (Blender 5.0 procedural objects with renders, code, captions), `FreedomIntelligence/BlendNet` (0.02 GB of Blender scripts).
- The user's "36 GB dataset" was NOT identified. Ask which repo if it matters; otherwise start with `3dcodeverse/3dcodeverse-2m`.
- `pip install bpy` works (5.3.0 was tested on Linux, Python 3.13). The dataset code targets Blender 5.0 and 5.1.2, so pin the local version to match and log it per run.
- Cloud sandbox: CPU only, about 29 GB free disk, files lost at session end, first 640x480 render took about 80 s. Bulk work belongs on the user's machine, ideally with a GPU.

## 3. Hard rules

1. **No ground-truth peeking.** While attempting a sample, never read its ground-truth code or mesh. Reveal only after the final attempt, then diff.
2. **Held-out split.** On first touch of a shard, assign 10% of samples to a held-out set. Held-out samples never feed the pattern library.
3. **Never print, log, commit or store the Hugging Face token.** Read it from the `HF_TOKEN` environment variable only.
4. **One shard at a time.** Download one shard, practice, keep scores and lessons and small thumbnails, delete the shard. Keep working disk under about 5 GB.
5. **Non-commercial.** Keep shards and the derived library private. Do not put derived data into anything sold.
6. **Pin versions.** Record the Blender version and the skill version in every score row.
7. **Validate the scorer first.** The dataset's own ground-truth code must score close to 1.0 through the rig before any learning is measured.
8. **Report honestly.** Say plainly when a metric is below the bar. Never round up or hide failures.

## 4. Project layout

```
3d-skill/
  data/                 # downloaded shards (deleted after use)
  runs/                 # renders, per-attempt code, scores
  skill/                # the skill being built (becomes the deliverable)
    SKILL.md            # workflow, rules, stop conditions (< ~500 lines)
    references/patterns.md   # lessons grouped by category
    snippets/           # verified Blender helpers
    scripts/            # run_sample.py score.py render_rig.py shard_manager.py fit_params.py
  evals/
    manifest.sqlite     # shards, samples, status, attempts, best score, category, split
    scoreboard.csv      # per skill version and category
  CHANGELOG.md
  .env.example          # HF_TOKEN= (never commit a real one)
```

## 5. Scoring rig (fixed, separate from pretty renders)

- 4 canonical cameras, one neutral light, white background, fixed resolution, fixed seed.
- Metrics:
  - Silhouette IoU per view (main pass/fail).
  - SSIM plus LPIPS or DreamSim on the shaded render.
  - Chamfer distance and volume ratio vs the ground-truth mesh (only when ground truth exists).
  - Code runs clean (a crash scores 0).
  - Rounds to threshold.
- Proposed pass bars (confirm with the user before relying on them):
  - Dataset samples: silhouette IoU >= 0.98 on 4 views, chamfer <= 1% of bounding-box diagonal.
  - Clean product photo: visible-view IoU >= 0.95 from the photo's camera; hidden sides declared as assumptions.
  - Photo with user dimensions: every stated dimension within 1%.
- Stop per sample at: pass bar reached, 8 rounds used, or two consecutive rounds improving less than 0.5%.
- Tag every failure: proportion, missing part, boolean error, material, camera, code error. Recurring tags decide what to teach next.

## 6. The core loop (used by every phase)

1. Pick a sample from the manifest. Ground truth stays sealed.
2. Retrieve 3 to 5 closest solved examples and lessons from `references/patterns.md`.
3. Analyze: parts, proportions as ratios, materials. Write a short build plan before code.
4. Write parametric Blender code: named dimensions at the top, one function per part.
5. Run headless in `bpy`, render on the fixed rig matching the reference camera.
6. Score.
7. Patch the worst region (do not rewrite), re-render, repeat within the stop rules.
8. Reveal ground truth, diff, record what differed.
9. Bank the lesson only if it fixed a failure that recurred at least 3 times, or raised the held-out score when tested alone. Update the scoreboard.

## 7. Milestones and exit tests

| # | Milestone | Exit test |
| --- | --- | --- |
| 1 | Harness: venv, shard manager, manifest, render rig, scorer | Ground-truth code scores close to 1.0 on 20 `factories_geo` samples; report the numbers |
| 2 | Baseline: attempt 50 held-out samples with no skill | Scores written to `scoreboard.csv` |
| 3 | Loop v1: retrieval, patching, stop rules | Held-out score beats baseline on the same fixed sample list |
| 4 | Pattern library v1 from first shards | Held-out score beats Loop v1, otherwise cut the patterns |
| 5 | Scale: shard-by-shard unattended cycle | One full cycle (download, practice, score, delete) runs without help and resumes after a kill |
| 6 | Photo track: 20 real objects with known dimensions | Dimensions within 1%; silhouette IoU reported; assumptions listed |
| 7 | Environment recipes: studio, interior, landscape, night city, sci-fi | Each renders from one command; preview (EEVEE) and final (Cycles, denoised) presets; render time logged |
| 8 | Custom-model workflow: reference board, spec sheet, blockout, detail passes, feedback rounds, export | One reference-to-print model delivered end to end (watertight check, wall thickness, STL) |
| 9 | Package the skill | A fresh session loads the skill and reproduces a baseline score |

## 8. Photo to 3D (Milestone 6 design)

1. Intake: image, any known dimension or scale object, which sides are visible. Ask for a second photo if the back matters.
2. Perception: segment the object, estimate the camera from edges and known sizes; optionally add a depth or normal estimate from a local model (verify which model and that it runs before depending on it).
3. Plan parts, symmetry, ratios, materials.
4. Build parametric Blender code.
5. Camera match: place the Blender camera at the estimated pose, render, overlay the silhouette on the photo.
6. Fit: optimize the named dimensions with `scipy.optimize` against silhouette overlap. Claude fixes topology and missing parts; the optimizer fixes millimeters.
7. Materials: project photo colors or match with procedural materials.
8. Hidden sides: default to symmetry, state every assumption in the report.
9. Deliver `.blend`, GLB, STL when printable, and a one-page report with score and assumptions.

Known limits: a single photo cannot reveal the back; organic shapes (faces, characters) stay weak because there is no sense of edge flow. Do not claim "100% accurate" for hidden geometry.

## 9. Environment renders (Milestone 7 design)

Judge by look, so scoring is looser: color histogram, brightness distribution, CLIP similarity to the reference, then a side-by-side for the human. Each recipe is a tested parametric script that records its settings and render time.

## 10. Custom models (Milestone 8 design)

Modes: Replica, Inspired-by, Modify (edit an existing mesh). Flow: reference board, spec sheet the user confirms, blockout at correct proportions, detail passes with a render after each, feedback rounds changing only what the user marks, variants by changing parameters, export. For exact mechanical parts, switch to CadQuery or FreeCAD.

## 11. Open decisions (ask the user, do not assume)

- Which exact repo is the "36 GB" dataset? Has the access form been submitted?
- Will bulk runs happen on a local machine with a GPU?
- Pin Blender 5.0 or 5.1.x?
- Are the pass bars in section 5 right?
- Start the CadQuery/FreeCAD mechanical track early for 3D printing, or after Blender results are stable?

## 12. First task

Build Milestone 1 only:

1. Create a Python venv with `bpy` (pinned), `huggingface_hub`, `trimesh`, `numpy`, `scipy`, `opencv-python`, `scikit-image`, and one perceptual-similarity package.
2. Write `scripts/shard_manager.py`: download ONE shard (`3dcodebench/factories_geo/samples-000.tar`), extract it, create the SQLite manifest, assign the 10% held-out split.
3. Write `scripts/render_rig.py` and `scripts/score.py` per section 5.
4. Run the dataset's own ground-truth code through the rig on 20 samples and print the scores in a table.
5. Stop. Do not start the learning loop. Delete the shard when done.
