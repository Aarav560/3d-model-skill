# Milestone 1: scorer validation (ground-truth code vs ground-truth GLB)

Rig-v1 (4 ortho views az 45/135/225/315 el 30, Workbench, 512 px, GT-derived frame). Subset `3dcodebench/factories_geo`, shard `samples-000.tar`, 20 fixed TRAIN samples (no held-out sample touched), SEED=0. Control = same code at SEED=1.

## Summary

| Blender | ran clean | IoU min >= 0.98 | median IoU min (clean) | mean IoU min (crash = 0) |
|---|---|---|---|---|
| 5.1.2 (pip bpy) | 19/20 | 13/20 | 0.9974 | 0.8916 |
| **5.0.1 (official binary, dataset target)** | **20/20** | **15/20** | **0.9985** | **0.9510** |

Exit bar ("close to 1.0 on 20 samples"): **still not met on all 20.** On Blender 5.0.1, 15/20 reach IoU >= 0.98, and a 16th (FanBaseCoral) reaches 0.976.

The other 4 cannot be reproduced by any scorer:
- 2 GT programs are non-deterministic (DiffGrowthBaseCoral, SpinyLobster).
- 2 are deterministic and identical across Blender versions but do not regenerate their own GT GLB (Succulent, ReedBranch). Seeds 0-7 were scanned and seed 0 is the closest; it looks like a dataset-side code/GLB mismatch.

On the 16 reproducible samples: IoU min 0.9759-1.0000, mean 0.9962; chamfer 0.032-0.285 % of diagonal (100k-point sampling floor is about 0.03-0.2 %).

The scorer discriminates: on 17 of 20 clean samples the SEED=1 control scores lower than SEED=0. The other 3 do not use SEED for geometry.

Blender 5.0.1 needs `scipy` and `matplotlib` installed into its bundled Python (the coral and book factories import them).

| sample | IoU min 5.0.1 | IoU min 5.1.2 | IoU mean | SSIM | LPIPS | chamfer % diag | vol ratio | control IoU (SEED=1) | note |
|---|---|---|---|---|---|---|---|---|---|
| Cabinet | 1.0000 | 1.0000 | 1.0000 | 0.9118 | 0.1092 | 0.0454 | 0.8067 | 0.7372 |  |
| BoxComforter | 1.0000 | 1.0000 | 1.0000 | 0.9610 | 0.0590 | 0.1463 | n/a | 0.9274 |  |
| LouverDoor | 1.0000 | 1.0000 | 1.0000 | 0.9196 | 0.0578 | 0.0533 | 1.0009 | 0.8645 |  |
| ArmChair | 0.9999 | 0.0000 | 0.9999 | 0.9981 | 0.0089 | 0.2386 | n/a | 0.8256 | crashed on 5.1.2, passes on 5.0.1 |
| PlateBase | 0.9999 | 0.9999 | 0.9999 | 0.9756 | 0.0422 | 0.1333 | 0.9994 | 0.4080 |  |
| VeratrumEarMonocot | 0.9998 | 0.7718 | 0.9999 | 0.9599 | 0.0328 | 0.2850 | n/a | 0.5988 | 0.77 on 5.1.2, passes on 5.0.1 |
| BushBaseCoral | 0.9993 | 0.9993 | 0.9995 | 0.9972 | 0.0019 | 0.0318 | n/a | 0.9993 |  |
| Cactus | 0.9991 | 0.9991 | 0.9992 | 0.9988 | 0.0008 | 0.0939 | n/a | 0.9991 |  |
| PineNeedle | 0.9990 | 0.9990 | 0.9990 | 1.0000 | 0.0001 | 0.0438 | n/a | 0.1881 |  |
| FlowerPlant | 0.9986 | 0.9986 | 0.9987 | 0.9996 | 0.0009 | 0.0847 | n/a | 0.0094 |  |
| SnakePlant | 0.9983 | 0.9983 | 0.9990 | 0.9998 | 0.0002 | 0.0707 | n/a | 0.1060 |  |
| LeafPalmPlant | 0.9974 | 0.9974 | 0.9985 | 0.9994 | 0.0006 | 0.0804 | n/a | 0.0291 |  |
| GrassesMonocot | 0.9957 | 0.9957 | 0.9962 | 0.9995 | 0.0004 | 0.0637 | n/a | 0.0479 |  |
| TwigCoral | 0.9905 | 0.9905 | 0.9935 | 0.9939 | 0.0079 | 0.1129 | n/a | 0.3160 |  |
| LeafHeart | 0.9851 | 0.9851 | 0.9852 | 0.9924 | 0.0081 | 0.1886 | n/a | 0.9528 |  |
| FanBaseCoral | 0.9759 | 0.9759 | 0.9803 | 0.9852 | 0.0105 | 0.1755 | n/a | 0.9759 | near miss; identical on both versions |
| ReedBranchMonocot | 0.8861 | 0.8861 | 0.8987 | 0.9791 | 0.0214 | 0.1506 | n/a | 0.1413 | deterministic, identical on 5.0.1 and 5.1.2; GT GLB not reproduced (seeds 0-7 scanned, 0 closest) |
| Succulent | 0.8207 | 0.8207 | 0.8438 | 0.8328 | 0.1558 | 0.6809 | n/a | 0.6434 | deterministic, identical on 5.0.1 and 5.1.2; GT GLB not reproduced (seeds 0-7 scanned, 0 closest) |
| SpinyLobster | 0.7125 | 0.7125 | 0.7184 | 0.9670 | 0.0766 | 1.7770 | n/a | 0.3932 | GT code non-deterministic (two SEED=0 runs differ) |
| DiffGrowthBaseCoral | 0.6624 | 0.7014 | 0.6811 | 0.8383 | 0.1826 | 2.5087 | 0.8175 | 0.6561 | GT code non-deterministic (two SEED=0 runs differ) |
