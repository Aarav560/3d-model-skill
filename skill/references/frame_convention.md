# Dataset frame convention (factories_geo), measured on TRAIN samples only

- Z is up; objects rest on z = 0 (flat objects such as blankets may sit just below 0).
- The object's front faces +X (chairs, cabinets). Thin panels such as doors lie in the XZ plane, thin along Y.
- Reference renders view_00..03 are perspective views at roughly azimuth 45/135/225/315 deg
  (view_00 = front-left from +X+Y, view_01 = back-right, view_02 = back-left, view_03 = front-right),
  at lower elevation than rig-v1 and often cropped.
- Absolute scale is not observable from the renders; the aligned score rescales the attempt to the GT
  bounding-box diagonal, so only proportions, orientation and shape count.

## instances_geo (measured on TRAIN instance ArmChair_002)
- Same object frame: Z up, front faces +X. Objects are NOT always resting on z = 0.
- Reference cameras (checked by rendering the train GT at test azimuths): view_02 ~ az 20 (from +X, the front),
  view_00 ~ az 200 (from -X, the back), view_03 ~ az 110 (from +Y), view_01 ~ az 290 (from -Y).
  In view_02 image-right is roughly +Y; in view_00 image-right is roughly -Y.
- Black background, flat grey shading.
