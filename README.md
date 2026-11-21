# claude-3d-skill

Plan and build spec for a Claude skill that gets measurably better at 3D modeling by practicing on a Blender-code dataset (3DCodeVerse-2M) one shard at a time: write Blender code from a reference image, render, score, fix, bank the lesson.

Goals, in order: replicate dataset samples, replicate any real photo as a 3D model, advanced environment renders, custom models steered by a reference image.

Start here: `3D-SKILL-BUILD.md`. Claude Code reads `CLAUDE.md` automatically.

Status: Milestones 1-2 done. Baseline (no skill) on 50 held-out samples: mean aligned IoU 0.672, 0/50 pass. See `evals/m2_baseline.md`. Next: Milestone 3 (loop v1).
