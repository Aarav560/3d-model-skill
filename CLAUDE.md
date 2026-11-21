# Project: Claude 3D modeling self-improvement skill

Before doing anything, read `3D-SKILL-BUILD.md` in full. It is the source of truth: goal, verified facts, hard rules, scoring rig, milestones with exit tests.

Quick rules (details in the spec):
- Build ONE milestone at a time. Run its exit test, report numbers honestly, then stop and wait.
- Start with Milestone 1 (harness + scorer validation). Do not start the learning loop until the scorer reproduces ~1.0 on ground-truth code.
- Never read ground truth while attempting a sample. Keep a 10% held-out split.
- Never print, log or commit the Hugging Face token; read it from `HF_TOKEN`.
- One dataset shard at a time; delete it after use. Dataset license is CC BY-NC-SA 4.0 (non-commercial); keep derived data private.
- Open decisions in section 11 of the spec: ask the user, do not assume.
- This GitHub repo may be PUBLIC and is MIT licensed. Never commit dataset shards, extracted dataset files, renders of dataset samples, or the derived pattern library built from dataset code (CC BY-NC-SA, non-commercial). Keep those local or in a private store; commit only original scripts, the spec, and aggregate score tables.
