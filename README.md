# claude-3d-skill

Plan and build spec for a Claude skill that gets measurably better at 3D modeling by practicing on a Blender-code dataset (3DCodeVerse-2M) one shard at a time: write Blender code from a reference image, render, score, fix, bank the lesson.

Goals, in order: replicate dataset samples, replicate any real photo as a 3D model, advanced environment renders, custom models steered by a reference image.

Start here: `3D-SKILL-BUILD.md`. Claude Code reads `CLAUDE.md` automatically.

Status: Milestone 1 harness built; scorer validation partially met (13/20 GT programs reach IoU >= 0.98 on bpy 5.1.2). See `evals/m1_scorer_validation.md`.
