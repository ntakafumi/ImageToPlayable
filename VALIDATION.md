# Validation scope

Checked on November 17, 2026.

| Stage | Result |
| --- | --- |
| Colab L4 environment setup | Completed on a fresh runtime |
| New authorized biped image → TRELLIS mesh | Completed |
| New mesh → TokenRig skeleton and skin weights | Completed |
| New rig → five Taka animations and GLB export | Completed with deformation warnings |
| Existing independently generated rig → Taka animations | Completed with deformation warnings |
| Browser loading, front/side views, walk/run and paused jump inspection | Checked on the existing-rig result |
| Scene-neutral v8 loader, model SHA-256 and clip validation | Checked through the viewer |
| Whole MotionStudio v8 or Game v8 integration | Not installed; adapter and contract supplied |

Environment: NVIDIA L4, Python 3.11, PyTorch 2.7.0 / CUDA 12.8, bpy 4.3.0;
Three.js 0.180.0 in the browser. The reference data hash is
`016cd45bc168f2fda471d5081fdef7377bca4ab7f8b40edd05f944e547bb8b7a`.

The source limb-direction transfer keeps global amplitude at 1.0. Neutral foot-frame
calibration changes the resting foot orientation; joint-local morph corrections do
not attenuate bone animation tracks. A direction check alone does not certify mesh
quality. The strict deformation gate remained false in both examples, while the
transfer direction gate passed and floor samples stayed near zero.

The two examples reached `complete_with_warnings`, not a claim of zero distortion,
zero self-intersection, universal rig compatibility or release-quality character art.

The exact Colab GUI upload dialogs were not automated. CLI verification ran the same
source scripts used by the notebooks. Browser recording and file-download behavior
vary by browser; the full recorded-download path was not confirmed in the test browser.

The current notebook entry points mount Drive and execute the ordinary source tree;
they contain no embedded source-file payloads or companion-ZIP extraction step.
Drive-path validation, input handling, viewer-file preparation and result persistence
were tested locally with an isolated orchestration fixture. The authenticated Drive
mount and current notebook GUI flow were not automated on Colab. Inference and
retargeting scripts remain those exercised by the preceding L4 CLI validation.

## Notebook 03: image to refined Pixal3D mesh

Pixal3D generation and source projection have been run on the two examples
using the pinned native Metal build on Mac. The new notebook route checks the
same nine GGUF weights and uses the saved camera from its own generation stage.
The image preprocessing was tested with transparent PNG and opaque JPEG.
A fixture substituted for the CUDA executable to check that notebook-stage
generation paths and camera files are passed through to refinement successfully.
The Linux CUDA build and complete L4 run in hosted Colab are pending validation.

## Notebook 04: single-GLB TokenRig and motion transfer

The input orientation stage was checked on the two refined Pixal3D GLBs.
The Taka motion reference and the five clip names were checked against prior
animated outputs. New TokenRig inference and retargeting on these
refined meshes require a Colab GPU and have not been exercised yet.

### Notebook 03 environment setup on Python 3.13

Following a Colab report that the standard-library venv command returned exit
code 1, notebook 03 now creates an unseeded environment with uv and installs
packages using uv pip. The environment creation was checked on Python 3.13,
and the pinned packages resolved for Linux x86-64 with Python 3.13. The CUDA
build and image-to-GLB run in hosted Colab remain to be exercised.

## Notebook 05 Paint3D

One animated yellow robot GLB completed the UV Tile experiment on a Colab NVIDIA L4 at 1024 × 1024 with maximum attention slicing applied to the UNet and both ControlNets. The downloaded ZIP's generated PNG matched the output GLB's embedded base colour byte for byte. Local checks confirmed that the mesh, skin, animation and metallic-roughness texture matched the input. This is a single-asset run. The public notebook was checked locally for syntax after editing its documentation.
