# Automatic multi-view reconstruction (recon-hull-v2), instances_geo

Inputs per sample: the 4 reference renders (alpha masks) + one camera model per subset, fitted on TRAIN samples only
(`skill/references/cameras_instances_geo.json`: azimuths ~204/295/24/115, elevation 28.0, lens 64.9 mm,
distance 2.92 x the object's largest dimension; the renderer frames each object by its max extent, measured on 12 train samples).
Method (`skill/scripts/recon.py`): carve a voxel hull from the 4 masks; priors |x|,|y|,|z| <= 0.5 and a z-symmetric bbox;
Gaussian smooth 3 / threshold 0.6 (tuned on 6 train samples); marching cubes. About 20-30 s per sample on 4 CPUs.

| set | n | mean IoU-min | median | >= 0.96 |
|---|---|---|---|---|
| held-out instances_geo (same 25 as M2/M3) | 25 | 0.789 | 0.802 | 0 |
| manual loop v1, same 25 | 25 | 0.785 | 0.804 | 3 |

The two are complementary: the hull wins on organic and irregular shapes (birds, augers, beds, boulder), manual parametric modelling wins on
boxes and lathe shapes (fridges, aquarium, bottles). Choosing the better one per sample would average 0.843, but only if the choice
is made from the input views (never from GT scores).

Why 0.96 is not reached: four views from 28 deg above never see undersides or concavities (basket interiors, bed slats),
and 4-view carving leaves bulges at 45 deg between views, exactly where the scoring rig looks.
