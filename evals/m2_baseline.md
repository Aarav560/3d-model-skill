# Milestone 2: baseline (no skill), 50 held-out samples

Fixed sample list: `evals/baseline_list.txt` (25 = every held-out sample of `factories_geo/samples-000`; 25 of the 30 held-out samples of `instances_geo/samples-000`, one per category first, then by salted hash).
Skill version `baseline-noskill`: one attempt per sample, no retrieval, no patterns, no patching, no snippets. Blender 5.0.1, rig-v1.

Input per sample: the 4 reference renders and the dataset `instruction` caption. GT code, GT mesh and GT renders stayed sealed (`runs/sealed/`, never opened); the attempter only saw each attempt's score after all attempts in its subset were written.
Also given: the frame convention (`skill/references/frame_convention.md`, measured on TRAIN samples only).

Primary metric: **aligned** silhouette IoU (worst of 4 rig views). The attempt is translated/scaled to the GT bounding box (center + diagonal, no rotation), because absolute scale is not observable from a render. The absolute-frame IoU is reported alongside.

## Result

| subset | n | mean IoU min | median | pass (>= 0.98) |
|---|---|---|---|---|
| factories_geo | 25 | 0.594 | 0.665 | 0 |
| instances_geo | 25 | 0.751 | 0.804 | 0 |
| **all** | **50** | **0.672** | **0.712** | **0/50** |

- Ran clean: 50/50. Mean chamfer 3.36 % of diagonal (bar is <= 1 %: 9/50 meet it).
- IoU >= 0.95: 5/50; >= 0.90: 13/50; < 0.50: 13/50.
- Strong on boxes and lathe shapes (rocks, aquarium, baskets, bottles, book, fridges, microwave, cell shelf).
- Weak on thin and branching structures (wheat, palm, chameleon, scallop, staircase, augers, beetle, beds, hardware).

## Caveats
- `instances_geo` captions are sometimes for a different sample: Balloon_024 says "AT" but shows "W"; BasketBase_004/030 captions are swapped. Attempts followed the images.
- Reference camera azimuths were inferred, not given (factories_geo ~ 45/135/225/315; instances_geo ~ 20/110/200/290 rotated by view index). An orientation mistake costs IoU directly.
- The attempter wrote all 50 attempts in one session; scores of the first subset were seen before the second subset was attempted (mild leakage of general calibration, no per-sample GT seen).

| sample | subset | IoU min (aligned) | IoU mean | chamfer % | SSIM | LPIPS | IoU min (absolute) |
|---|---|---|---|---|---|---|---|
| BlenderRock_036 | instances_geo | 0.976 | 0.978 | 0.375 | 0.977 | 0.036 | 0.979 |
| BlenderRock_039 | instances_geo | 0.963 | 0.968 | 0.422 | 0.975 | 0.029 | 0.967 |
| AquariumTank_004 | instances_geo | 0.963 | 0.963 | 1.152 | 0.872 | 0.211 | 0.332 |
| BasketBase_004 | instances_geo | 0.956 | 0.956 | 0.528 | 0.896 | 0.117 | 0.355 |
| Bottle_021 | instances_geo | 0.952 | 0.952 | 0.896 | 0.949 | 0.076 | 0.213 |
| Bottle_003 | instances_geo | 0.947 | 0.947 | 1.019 | 0.945 | 0.075 | 0.216 |
| BasketBase_002 | instances_geo | 0.935 | 0.935 | 0.749 | 0.887 | 0.143 | 0.369 |
| Book_010 | instances_geo | 0.933 | 0.933 | 1.101 | 0.918 | 0.098 | 0.245 |
| CellShelf | factories_geo | 0.925 | 0.925 | 0.598 | 0.797 | 0.187 | 0.580 |
| Microwave | factories_geo | 0.923 | 0.930 | 2.446 | 0.893 | 0.162 | 0.175 |
| Bathtub_000 | instances_geo | 0.916 | 0.926 | 1.352 | 0.896 | 0.121 | 0.209 |
| Flower | factories_geo | 0.905 | 0.917 | 2.696 | 0.860 | 0.154 | 0.203 |
| BeverageFridge_008 | instances_geo | 0.902 | 0.904 | 3.065 | 0.852 | 0.262 | 0.255 |
| BeverageFridge_026 | instances_geo | 0.899 | 0.901 | 3.006 | 0.850 | 0.276 | 0.246 |
| Wineglass | factories_geo | 0.865 | 0.865 | 0.835 | 0.928 | 0.072 | 0.164 |
| BasketBase | factories_geo | 0.844 | 0.844 | 3.427 | 0.829 | 0.307 | 0.396 |
| ArmChair_004 | instances_geo | 0.838 | 0.839 | 2.111 | 0.857 | 0.186 | 0.428 |
| Raindrop | factories_geo | 0.832 | 0.832 | 3.308 | 0.932 | 0.120 | 0.207 |
| BathroomSink_013 | instances_geo | 0.804 | 0.814 | 1.319 | 0.874 | 0.200 | 0.257 |
| BasketBase_030 | instances_geo | 0.767 | 0.769 | 5.338 | 0.717 | 0.460 | 0.358 |
| CauliflowerCoral | factories_geo | 0.745 | 0.781 | 3.785 | 0.746 | 0.305 | 0.388 |
| TriangleShelf | factories_geo | 0.744 | 0.831 | 2.576 | 0.852 | 0.262 | 0.031 |
| SidetableDesk | factories_geo | 0.741 | 0.741 | 0.937 | 0.896 | 0.150 | 0.174 |
| Pants | factories_geo | 0.718 | 0.718 | 2.857 | 0.878 | 0.277 | 0.399 |
| CabinetDoorBase | factories_geo | 0.715 | 0.715 | 4.734 | 0.928 | 0.117 | 0.293 |
| FruitStarfruit | factories_geo | 0.708 | 0.756 | 3.308 | 0.867 | 0.190 | 0.000 |
| Boulder_009 | instances_geo | 0.699 | 0.740 | 3.853 | 0.898 | 0.239 | 0.145 |
| Balloon_024 | instances_geo | 0.698 | 0.700 | 3.057 | 0.856 | 0.203 | 0.250 |
| Balloon_027 | instances_geo | 0.697 | 0.706 | 2.699 | 0.823 | 0.228 | 0.227 |
| Bird_029 | instances_geo | 0.695 | 0.702 | 2.181 | 0.896 | 0.142 | 0.341 |
| SimpleDesk | factories_geo | 0.665 | 0.665 | 2.841 | 0.884 | 0.222 | 0.578 |
| FloorLamp | factories_geo | 0.607 | 0.607 | 2.484 | 0.959 | 0.055 | 0.573 |
| SpatulaBase | factories_geo | 0.582 | 0.582 | 1.278 | 0.934 | 0.111 | 0.043 |
| Bird_035 | instances_geo | 0.568 | 0.571 | 4.035 | 0.878 | 0.194 | 0.406 |
| BookColumn_007 | instances_geo | 0.538 | 0.549 | 1.743 | 0.874 | 0.173 | 0.166 |
| BedFrame_005 | instances_geo | 0.537 | 0.545 | 1.432 | 0.743 | 0.172 | 0.120 |
| Window | factories_geo | 0.533 | 0.544 | 19.668 | 0.818 | 0.353 | 0.293 |
| Knife | factories_geo | 0.487 | 0.488 | 0.866 | 0.956 | 0.052 | 0.097 |
| BedFrame_020 | instances_geo | 0.479 | 0.504 | 3.306 | 0.769 | 0.198 | 0.110 |
| CoffeeTable | factories_geo | 0.479 | 0.479 | 7.700 | 0.880 | 0.337 | 0.462 |
| Beetle_048 | instances_geo | 0.466 | 0.497 | 3.594 | 0.858 | 0.210 | 0.000 |
| Auger_026 | instances_geo | 0.445 | 0.491 | 4.593 | 0.880 | 0.191 | 0.152 |
| Mussel | factories_geo | 0.418 | 0.588 | 7.014 | 0.898 | 0.238 | 0.030 |
| Hardware | factories_geo | 0.373 | 0.373 | 7.449 | 0.899 | 0.176 | 0.374 |
| Chameleon | factories_geo | 0.313 | 0.374 | 3.522 | 0.912 | 0.168 | 0.067 |
| LShapedStaircase | factories_geo | 0.310 | 0.355 | 3.091 | 0.809 | 0.173 | 0.135 |
| Auger_001 | instances_geo | 0.193 | 0.332 | 7.712 | 0.905 | 0.206 | 0.176 |
| ScallopBase | factories_geo | 0.169 | 0.468 | 11.667 | 0.912 | 0.216 | 0.000 |
| CoconutTree | factories_geo | 0.131 | 0.159 | 4.547 | 0.901 | 0.166 | 0.070 |
| WheatMonocot | factories_geo | 0.122 | 0.190 | 3.821 | 0.892 | 0.196 | 0.004 |
