# Milestone 3: loop v1 vs baseline (same 50 held-out samples)

Skill version `loop-v1`. Round 1 = the baseline attempt (identical code), so any gain comes from the loop.
Each later round: the attempter sees the per-view aligned IoU (a scalar per rig view) and a preview sheet
(`skill/scripts/preview.py`: the attempt rendered from the inferred reference cameras next to the reference images). It never sees GT renders, GT masks or GT code.
It then patches one region or proportion (no rewrites). Stop rules: pass (IoU-min >= 0.98), 8 rounds, or two consecutive rounds each gaining < 0.5 %,
plus a logged extra rule `no_hypothesis` (the attempter had no concrete patch; the sample keeps its best round).
Retrieval (`loop.py retrieve`) is wired in but returned nothing: no train sample has been solved yet, and held-out attempts may not feed it.

## Exit test: PASS

| subset | n | baseline | loop v1 (best round) | loop v1 (last round) | pass >= 0.98 |
|---|---|---|---|---|---|
| factories_geo | 25 | 0.594 | **0.686** | 0.666 | 0 |
| instances_geo | 25 | 0.751 | **0.785** | 0.764 | 3 |
| **all** | **50** | **0.672** | **0.735** | 0.715 | **3/50** |

- Mean gain +0.063 IoU (95 % bootstrap CI [0.036, 0.095]). Improved 33/50, unchanged 17/50, worse 0/50 (the best round is kept, so it cannot be worse).
- The final answer is the best-scoring round, chosen with the loop's own score feedback. Taking each sample's last round instead still beats the baseline (0.715 vs 0.672).
- Passes: BeverageFridge_008 (0.982), BeverageFridge_026 (0.987), AquariumTank_004 (0.992). Mean chamfer 3.36 % -> 2.65 % of diagonal.
- 176 rounds in total (mean 3.5 per sample). Stops: plateau 28, no_hypothesis 18, pass 3, max_rounds 1.

## What the loop fixed (failure tags)
- **proportion** (most gains): fridges and aquarium depth, cabinet door height, shelf width, lamp height, spatula aspect, coral base cut.
- **code error, world-space boolean cutter**: two shell attempts (ScallopBase, Mussel) lost a whole valve because the cutter stayed fixed while the part moved. The fix was to apply the modifiers before moving the part (+0.57 and +0.33 IoU). Candidate lesson for M4.
- **orientation**: auger tilt direction (+0.25 / +0.09).
- **missing part**: window curtains (small gain).
- **Not fixed**: thin and branching geometry (wheat 0.12, palm 0.13, staircase 0.31). Silhouette patches did not move these scores.

## Harness issues found during M3 (fixed, reported honestly)
- Loop state was one shared JSON. Two parallel rounds clobbered each other, dropping one round each for CoconutTree and ScallopBase. Their histories were repaired from the round outputs, and state is now one file per sample.
  CoconutTree's `round_02` directory holds its 3rd attempt; the manifest has a duplicate round-2 row for it.
- One Wheat round ran unpatched code: a typo in my patch command meant the edit never happened. The round still counts and plateaued.

| sample | baseline | loop v1 (best) | last round | rounds | stop |
|---|---|---|---|---|---|
| ScallopBase | 0.169 | 0.736 | 0.706 | 4 | plateau |
| Auger_001 | 0.193 | 0.522 | 0.496 | 6 | plateau |
| Mussel | 0.418 | 0.747 | 0.729 | 7 | plateau |
| Hardware | 0.373 | 0.575 | 0.571 | 5 | plateau |
| Knife | 0.487 | 0.667 | 0.644 | 6 | plateau |
| CabinetDoorBase | 0.715 | 0.888 | 0.756 | 3 | no_hypothesis |
| SpatulaBase | 0.582 | 0.732 | 0.700 | 4 | plateau |
| TriangleShelf | 0.744 | 0.886 | 0.868 | 4 | plateau |
| CauliflowerCoral | 0.745 | 0.886 | 0.886 | 4 | plateau |
| Chameleon | 0.313 | 0.453 | 0.449 | 4 | plateau |
| Auger_026 | 0.445 | 0.538 | 0.538 | 8 | max_rounds |
| Bird_035 | 0.568 | 0.660 | 0.657 | 6 | plateau |
| FloorLamp | 0.607 | 0.695 | 0.695 | 4 | plateau |
| BeverageFridge_026 | 0.899 | 0.987 | 0.987 | 4 | pass |
| BeverageFridge_008 | 0.902 | 0.982 | 0.982 | 2 | pass |
| BasketBase | 0.844 | 0.902 | 0.899 | 4 | plateau |
| Balloon_024 | 0.698 | 0.745 | 0.745 | 4 | plateau |
| Microwave | 0.923 | 0.959 | 0.947 | 4 | plateau |
| Book_010 | 0.933 | 0.963 | 0.963 | 4 | plateau |
| AquariumTank_004 | 0.963 | 0.992 | 0.992 | 4 | pass |
| Bird_029 | 0.695 | 0.720 | 0.708 | 4 | plateau |
| Pants | 0.718 | 0.743 | 0.743 | 5 | plateau |
| Window | 0.533 | 0.557 | 0.557 | 5 | plateau |
| CoffeeTable | 0.479 | 0.497 | 0.489 | 4 | plateau |
| CellShelf | 0.925 | 0.942 | 0.941 | 3 | no_hypothesis |
| BedFrame_005 | 0.537 | 0.553 | 0.531 | 4 | plateau |
| Bathtub_000 | 0.916 | 0.926 | 0.922 | 4 | plateau |
| ArmChair_004 | 0.838 | 0.847 | 0.839 | 4 | plateau |
| BasketBase_004 | 0.956 | 0.961 | 0.942 | 4 | plateau |
| BlenderRock_039 | 0.963 | 0.965 | 0.965 | 3 | plateau |
| Balloon_027 | 0.697 | 0.698 | 0.570 | 3 | plateau |
| Bottle_003 | 0.947 | 0.948 | 0.948 | 2 | no_hypothesis |
| Wineglass | 0.865 | 0.866 | 0.866 | 2 | no_hypothesis |
| CoconutTree | 0.131 | 0.131 | 0.101 | 3 | no_hypothesis |
| Raindrop | 0.832 | 0.832 | 0.820 | 3 | plateau |
| LShapedStaircase | 0.310 | 0.310 | 0.260 | 2 | no_hypothesis |
| Flower | 0.905 | 0.905 | 0.881 | 2 | no_hypothesis |
| FruitStarfruit | 0.708 | 0.708 | 0.690 | 2 | no_hypothesis |
| SimpleDesk | 0.665 | 0.665 | 0.660 | 2 | no_hypothesis |
| BasketBase_002 | 0.935 | 0.935 | 0.905 | 2 | no_hypothesis |
| SidetableDesk | 0.741 | 0.741 | 0.674 | 2 | no_hypothesis |
| WheatMonocot | 0.122 | 0.122 | 0.122 | 3 | plateau |
| BasketBase_030 | 0.767 | 0.767 | 0.753 | 2 | no_hypothesis |
| Beetle_048 | 0.466 | 0.466 | 0.367 | 2 | no_hypothesis |
| BathroomSink_013 | 0.804 | 0.804 | 0.804 | 2 | no_hypothesis |
| BedFrame_020 | 0.479 | 0.479 | 0.432 | 2 | no_hypothesis |
| BookColumn_007 | 0.538 | 0.538 | 0.503 | 2 | no_hypothesis |
| BlenderRock_036 | 0.976 | 0.976 | 0.967 | 3 | plateau |
| Bottle_021 | 0.952 | 0.952 | 0.928 | 2 | no_hypothesis |
| Boulder_009 | 0.699 | 0.699 | 0.666 | 2 | no_hypothesis |
