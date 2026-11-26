# Full dataset run: every instances_geo sample (recon-learned-v1)

1953 objects (8 shards, 210 categories), processed unattended on the cloud CPU, one shard at a time
(download -> reconstruct + score -> delete; resumable: Milestone 5's cycle). 7 samples failed to process.

| split | n | mean IoU-min | median | >= 0.9 | >= 0.96 | < 0.5 |
|---|---|---|---|---|---|---|
| held-out (honest) | 199 | 0.710 | 0.795 | 30 (15.1%) | 0 | 40 |
| train | 1754 | 0.692 | 0.785 | 215 (12.3%) | 2 | 349 |

Best categories (mean about 0.94): Blanket, Raindrop, Comforter, FruitCoconuthairy, BoxComforter, BlenderRock, Pillow, Lid.
Worst (below 0.15): Branch, ReedMonocot, WheatMonocot, KelpMonocot, FlyingBird, Chopsticks, PlantBananaTree, DandelionSeed.
Per-sample scores: `scores_recon-learned-v1_instances_geo.csv`; per category: `recon_categories_instances_geo.csv`.

The user's targets (>= 0.9, ideally 0.96, for every object) are NOT met. The limit is information, not compute: the 4 reference cameras
form two opposite pairs (about 24/204 and 114/294 deg), so silhouettes constrain each object from effectively two directions;
undersides, cavities and thin parts are not recoverable from them.
