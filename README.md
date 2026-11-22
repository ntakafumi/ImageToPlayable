# Image to a playable character with Taka's tuned motions

[日本語](README.ja.md)

Generate a textured biped mesh from one image, infer its skeleton and skin weights, retarget Taka's tuned game motions, and control it in a browser. Built with TRELLIS, SkinTokens / TokenRig, and Three.js.

## Motions

Includes idle, walk, jog, run and jump. `motions/taka-motion.json` records frame-by-frame bone directions, body orientations, speed information and the game jump trajectory. It contains no Taka mesh or textures. Motions are retargeted rather than replaced by sine-wave animation. Global amplitude stays at 1.0; neutral foot orientation, joint-local weights/deformation and floor clearance are corrected. Different body proportions still lead to different hand and foot positions.

## Notebooks

| Notebook | Purpose | Runtime |
| --- | --- | --- |
| `01_Image_to_Taka_Motion_L4.ipynb` | Image generation, rigging, retargeting and controls | Colab L4 GPU |
| `02_Existing_Rig_to_Taka_Motion.ipynb` | Retarget an existing rigged GLB | Colab CPU is sufficient |
| `03_Pixal3D_Mesh_Refinement.ipynb` | Generate from one PNG/JPEG with Pixal3D, then refine the texture | Colab L4 GPU |
| `04_GLB_to_Taka_Motion.ipynb` | Rig one static GLB and apply the same Taka motions as 02 | Colab L4 GPU |

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ntakafumi/ImageToPlayable/blob/main/03_Pixal3D_Mesh_Refinement.ipynb)

Notebook 03 takes one PNG/JPEG, removes the background when needed, runs CUDA Pixal3D, and uses the saved source camera to refine the base colour. It saves `model.refined.glb`, the original generated GLB, and comparison images. Notebook 04 takes one static GLB and applies the same TokenRig settings as 01 and the same Taka motion reference as 02.

## Place the source tree on Google Drive

Copy the GitHub source tree to:

```text
My Drive/Colab Notebooks/GameCreation/MotionStudio/10_ImageToCharacter/
  01_Image_to_Taka_Motion_L4.ipynb
  02_Existing_Rig_to_Taka_Motion.ipynb
  03_Pixal3D_Mesh_Refinement.ipynb
  reference/
  tools/
  motions/taka-motion.json
  integration/
  MOTIONS_LICENSE.md
```

If using the downloadable source ZIP, extract it before placing the folder on Drive.
The notebooks do not ask you to upload the source ZIP or generate source files from
embedded code. They execute the ordinary source files on mounted Drive.

## Run

1. Open a notebook from Drive in Google Colab.
2. Select an L4 GPU for notebook 01; notebook 02 does not need a GPU.
3. Mount Drive in the first cell and set `PROJECT_DIR` to the source-tree folder.
4. Run the environment setup cell.
5. Set `IMAGE_PATH` or `RIG_PATH` to a Drive file. Leave it empty to choose an input file for upload.
6. Run retargeting and viewer cells, then inspect the result.
7. Save the result ZIP under `PROJECT_DIR/outputs/<run-id>/`. Downloading it to your PC is optional.

Default source path:

```python
PROJECT_DIR = '/content/drive/MyDrive/Colab Notebooks/GameCreation/MotionStudio/10_ImageToCharacter'
```

Other paths, including shared drives, can be used. Code and the Taka motion reference
are read directly from Drive. Dependencies, model weights, intermediate results and
the local viewer run in Colab's temporary storage. The source tree is not rewritten.
Weights are obtained from official sources. No paid generation API is used, but Colab
compute may incur charges.

## Controls

WASD moves; Shift runs; Space jumps. Drag and wheel control the camera. Buttons preview each motion in place and select front/side/back views. Pause and the slider inspect an exact pose. The recording button saves a walk/run/jump WebM or MP4 (browser dependent).

The jump trajectory is already baked into the GLB and is not added again by the viewer. Validation warnings remain in the diagnostic JSON. Failed transfers are not replaced with another character or simple fallback animations.

## Inputs and limitations

Use an authorized full-body, front-facing A/T-pose image with separated arms. Unseen surfaces and depth are inferred. Rigging failures, collapsed joints, foot sliding and intersections can remain, particularly with unusual proportions and clothing. Direction checks do not guarantee visual quality or collision-free geometry.

## Sources

- `reference/`: L4 setup, TRELLIS generation, TokenRig and viewer
- `tools/colab_runtime.py`: notebook input, process, viewer and result-saving helpers
- `tools/`: semantic mapping, motion transfer, foot calibration, joint-local correctives and validation
- `motions/taka-motion.json`: animation reference without Taka geometry
- `build_notebook.py`: generate notebooks
- `check_release.py`: source and release checks

## Licensing and generation-use restrictions

Original independent tutorial code and documentation: MIT. The Blender API script `tools/animate10.py`: GPL-3.0-or-later. Full texts are in `LICENSES/`. Combinations with Blender must comply with the applicable GPL terms. Ordinary GLB or video output does not automatically become GPL-licensed.

**The image-generation environment in notebook 01 is not commercially unrestricted.** The pinned nvdiffrast and Gaussian rasterizer components limit use to non-commercial research and evaluation. Commercial asset production or generation services require appropriate separate permissions or replacement and validation of the restricted components. MIT/GPL licensing of the tutorial does not remove upstream use restrictions.

Notebook 02 reopens completed results without rerunning image generation. This does not settle permissions for the original generation purpose, input artwork or motion data.
See [LICENSING.md](LICENSING.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and the separate motion terms in [MOTIONS_LICENSE.md](MOTIONS_LICENSE.md).
Takanyan and Taka images, meshes, textures and the game environment are not bundled.


### Commercial-use scope of notebooks 03 and 04

| Notebook | Relevant terms |
| --- | --- |
| 03 (Pixal3D generation and refinement) | The selected Pixal3D components and BiRefNet-lite weights have permissive licenses. DINOv3 uses its own license, which allows commercial use subject to conditions including use restrictions. NAF and the adapted texture-projection code are Apache-2.0. |
| 04 (TokenRig and motion transfer) | The published TokenRig code and checkpoints are MIT. The rig-only setup skips the TRELLIS image-generation path used in 01. The rigging dependencies and the bundled Taka motion reference (CC BY 4.0) keep their own terms. |

See [LICENSING.md](LICENSING.md), [third-party notices](THIRD_PARTY_NOTICES.md) and [motion terms](MOTIONS_LICENSE.md). Clear rights to the input artwork and any third-party content separately. See [validation](VALIDATION.md) for what has run on Colab.

## Related article

Taka is the author's game character with an existing rig, skinning and developed basic animations. See the [Kimodo article](https://zenn.dev/nakanishitf/articles/86ee54b68edee8) for motion-retargeting context.

## Verified environment

The mesh-generation, rigging, five-motion retargeting and animated-GLB export stages were run on a Colab L4. The existing-rig resume path was also run. Browser loading, view changes and paused pose inspection were checked. The motion reference is byte-identical to the previous 10N experiment. Joint-deformation warnings remain in the tested examples; see [VALIDATION.md](VALIDATION.md).

Completed `character-taka-result.zip` files can be reopened in notebook 02. The model hash, motion reference, five clips and direction report are checked before reuse; the existing animation is not applied twice.
