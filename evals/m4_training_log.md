# Milestone 4: training log, batch 1 (aggregate; lesson text and pattern library stay private)

Practice on 10 TRAIN samples of `factories_geo` (held-out samples refused by `skill/scripts/train.py`).
Per sample: attempt -> preview-guided patch rounds -> ground truth revealed only after the final round -> diff -> lessons logged
(`runs/training_log.jsonl`, private). Illustrated report: `runs/reports/training_report_m4_batch1.pdf` (private).

Mean IoU-min: first round 0.627, best 0.634.
Lesson tags: cut x1, missing_part x1, orientation x3, proportion x6, thin_structure x2.

| train sample | rounds | first round | best |
|---|---|---|---|
| TableDining | 1 | 0.720 | 0.720 |
| DeskLamp | 1 | 0.858 | 0.858 |
| StraightStaircase | 2 | 0.242 | 0.242 |
| PalmTree | 2 | 0.444 | 0.523 |
| MaizeMonocot | 2 | 0.250 | 0.250 |
| Clam | 2 | 0.673 | 0.673 |
| SimpleBookcase | 1 | 0.917 | 0.917 |
| Dishwasher | 1 | 0.930 | 0.930 |
| Conch | 1 | 0.482 | 0.482 |
| Sofa | 1 | 0.751 | 0.751 |

## Pattern library status (train evidence only)
- Banked: **0**. No lesson yet has 3 train occurrences or a successful held-out test.
- Candidates: 7 (tilted spiral shells, box depth ~ width, solid stair stringer, no blind 180-deg flips, thin sofa arms, lamp proportions, boolean-apply order).
- Cut: 1. Umbrella palm crown: +0.08 on train PalmTree, but held-out CoconutTree 0.131 -> 0.112.
- Rejected: the 90-deg reference-camera offset hypothesis (yaw probe: yaw 0 is best on TableDining and StraightStaircase).
- Correction: a first draft counted held-out loop experience as evidence for 3 patterns. That violates spec rule 3.2, so it was removed and the status recomputed.

## M4 exit test status: NOT reached
"Held-out beats loop v1" cannot be tested yet: there are no banked patterns. Next: more train batches until candidates reach 3
occurrences, then rerun the fixed 50 held-out samples with the banked library (loop-v2).
