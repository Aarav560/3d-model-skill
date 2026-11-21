# Milestone 1: scorer validation (ground-truth code vs ground-truth GLB)

Setup: bpy 5.1.2 (dataset targets Blender 5.0), rig-v1 (4 ortho views, Workbench, 512 px), subset `3dcodebench/factories_geo` shard `samples-000.tar`, 20 fixed TRAIN samples (no held-out sample touched), SEED=0. Control = same code at SEED=1.

## Result: exit bar NOT fully met

- Ran clean: 19/20 (1 crash scores 0).
- Silhouette IoU (min over 4 views) >= 0.98: 13/20.
- Median IoU min over clean runs: 0.9974; mean over all 20 (crash = 0): 0.8916.
- Scorer floor: identical geometry gives IoU 0.999-1.000; chamfer noise floor ~0.03-0.19 % of diagonal (100k-point sampling).
- Discrimination: the SEED=1 control scores lower than SEED=0 on 16/19 clean samples; the rest ignore SEED for geometry.

The rig and scorer behave correctly. The 7 misses come from the GT programs: 1 crash, 2 non-deterministic, 3-4 deterministic but different from the GT GLB under bpy 5.1.2.

| sample | IoU min | IoU mean | SSIM | LPIPS | chamfer % diag | vol ratio | control IoU min (SEED=1) | note |
|---|---|---|---|---|---|---|---|---|
| Cabinet | 1.0000 | 1.0000 | 0.9118 | 0.1092 | 0.0454 | 0.8067 | 0.7372 |  |
| BoxComforter | 1.0000 | 1.0000 | 0.9616 | 0.0587 | 0.1463 | n/a | 0.9274 |  |
| LouverDoor | 1.0000 | 1.0000 | 0.9196 | 0.0578 | 0.0532 | 1.0009 | 0.8645 |  |
| PlateBase | 0.9999 | 0.9999 | 0.9756 | 0.0422 | 0.1333 | 0.9994 | 0.4080 |  |
| BushBaseCoral | 0.9993 | 0.9995 | 0.9972 | 0.0019 | 0.0318 | n/a | 0.9993 |  |
| Cactus | 0.9991 | 0.9992 | 0.9988 | 0.0008 | 0.0939 | n/a | 0.9991 |  |
| PineNeedle | 0.9990 | 0.9990 | 1.0000 | 0.0001 | 0.0438 | n/a | 0.1881 |  |
| FlowerPlant | 0.9986 | 0.9987 | 0.9996 | 0.0009 | 0.0847 | n/a | 0.0094 |  |
| SnakePlant | 0.9983 | 0.9990 | 0.9998 | 0.0002 | 0.0707 | n/a | 0.1060 |  |
| LeafPalmPlant | 0.9974 | 0.9985 | 0.9994 | 0.0006 | 0.0804 | n/a | 0.0291 |  |
| GrassesMonocot | 0.9957 | 0.9962 | 0.9995 | 0.0004 | 0.0637 | n/a | 0.0479 |  |
| TwigCoral | 0.9905 | 0.9935 | 0.9939 | 0.0079 | 0.1129 | n/a | 0.3160 |  |
| LeafHeart | 0.9851 | 0.9852 | 0.9924 | 0.0081 | 0.1886 | n/a | 0.9528 |  |
| FanBaseCoral | 0.9759 | 0.9803 | 0.9852 | 0.0105 | 0.1755 | n/a | 0.9759 |  |
| ReedBranchMonocot | 0.8861 | 0.8987 | 0.9791 | 0.0214 | 0.1506 | n/a | 0.1413 | deterministic, 1.8x GT triangles; differs from GT GLB |
| Succulent | 0.8207 | 0.8438 | 0.8328 | 0.1558 | 0.6809 | n/a | 0.6434 | deterministic, but shape differs from GT GLB (suspect 5.0 vs 5.1.2) |
| VeratrumEarMonocot | 0.7718 | 0.7893 | 0.8045 | 0.1766 | 0.7745 | n/a | 0.6395 | deterministic, but shape differs from GT GLB (suspect 5.0 vs 5.1.2) |
| SpinyLobster | 0.7125 | 0.7181 | 0.9670 | 0.0767 | 1.7799 | n/a | 0.3931 | code non-deterministic (two SEED=0 runs differ) |
| DiffGrowthBaseCoral | 0.7014 | 0.7278 | 0.8415 | 0.1670 | 2.1418 | 0.9671 | 0.6233 | code non-deterministic (two SEED=0 runs differ) |
| ArmChair | 0.0000 | 0.0000 | 0.0000 | 1.0000 | n/a | n/a | 0.0000 | crash: GeoNodes modifier yields no mesh on bpy 5.1.2 |
