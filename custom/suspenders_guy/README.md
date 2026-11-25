# Stylized character from one reference image ("suspenders guy")

Custom-model track (spec sections 8 and 10): one front-ish reference image, no ground-truth mesh.
The reference image and all renders stay local (`runs/custom/suspenders_guy/`, git-ignored): the image is third-party art.

- `build.py`: parametric build (named dimensions at the top, one function per part): skin-modifier volumes for shirt,
  forearms, trousers and neck; ellipsoid head features; tie strip; NURBS suspender straps with pouches; belt and buckle; shoes.
  It renders a Cycles beauty image, a flat silhouette from the same camera, and with `--final` 860 px plus turnaround views. It exports `.blend` and `.glb`.
- `compare.py`: silhouette IoU against a GrabCut mask of the reference (absolute and bbox-aligned, plus head / torso / leg bands) and a diff overlay.

## Rounds (aligned silhouette IoU vs reference mask)
| round | change | IoU | head | torso+arms | legs |
|---|---|---|---|---|---|
| 1 | first blockout | 0.560 | 0.555 | 0.614 | 0.435 |
| 2 | narrower shoulders, wider stance, bigger head, lighting/camera | 0.640 | 0.564 | 0.753 | 0.432 |
| 3 | barrel chest, asymmetric stance, 70 mm camera | 0.683 | 0.568 | 0.761 | 0.548 |
| 4 | head redesign (jaw, cleft chin, brow, slicked hair), box fists, wider tie | 0.686 | 0.554 | 0.771 | 0.551 |
| 5 | bigger forearms/fists, higher shoulders | 0.683 (plateau, stop) | | | |
| final | fist smoothing, wrist gap fix, dark floor | **0.688** | 0.554 | 0.766 | 0.559 |

## Assumptions and limits (stated honestly)
- Back and sides are invented (one image only): symmetric body, suspenders crossing straight down the back.
- Scale assumed 1.85 m tall; proportions are measured from the image as ratios.
- The reference is a 3/4 view with a slightly twisted torso; the model is built straight and the camera offset approximates it.
- The face, hands, cloth folds and tattoos are far below the reference's sculpted quality. Primitive and skin-modifier
  modelling has no edge flow, so this is a stylized blockout, not a replica.
