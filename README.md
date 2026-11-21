# claude-3d-skill

Plan and build spec for a Claude skill that gets measurably better at 3D modeling by practicing on a Blender-code dataset (3DCodeVerse-2M) one shard at a time: write Blender code from a reference image, render, score, fix, bank the lesson.

Goals, in order: replicate dataset samples, replicate any real photo as a 3D model, advanced environment renders, custom models steered by a reference image.

Start here: `3D-SKILL-BUILD.md`. Claude Code reads `CLAUDE.md` automatically.

Status: Milestone 1 harness built. On Blender 5.0.1, 15/20 GT programs reach IoU >= 0.98 (16/16 of the reproducible ones reach >= 0.975). See `evals/m1_scorer_validation.md`.
