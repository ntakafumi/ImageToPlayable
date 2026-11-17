# Taka motion reference

This file contains sampled animation data, not a character model.

| Clip | Samples | Duration |
| --- | ---: | ---: |
| Idle_preview | 93 | 3.067 s |
| Walk_preview | 48 | 1.567 s |
| Jog_preview | 22 | 0.700 s |
| Run_preview | 22 | 0.700 s |
| Jump_preview | 25 | 0.800 s |

Each frame stores normalized world-space limb directions, body orientation matrices
and body translation. The target rig supplies its own joint positions and lengths.
The JSON also stores playback-rate and speed information from the game.
The jump is based on the recorded game trajectory (initial vertical speed 8.1,
gravity 20, discrete step 1/60 s); the viewer must not add another jump trajectory.

Retargeting preserves full source directions, then calibrates the neutral foot frame
and corrects joint-local skin deformation. This is not a transfer of Taka's geometry,
textures, inverse bind matrices or character design. See ../MOTIONS_LICENSE.md.
