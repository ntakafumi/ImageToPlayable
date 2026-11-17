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

## Place the source tree on Google Drive

Copy the GitHub source tree to:

```text
My Drive/Colab Notebooks/GameCreation/MotionStudio/10_ImageToCharacter/
  01_Image_to_Taka_Motion_L4.ipynb
  02_Existing_Rig_to_Taka_Motion.ipynb
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

## Licensing

Original tutorial code: [MIT](LICENSE). Included motion reference: [MOTIONS_LICENSE.md](MOTIONS_LICENSE.md). Dependencies and model weights have separate terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Takanyan and Taka images, meshes, textures and the game environment are not bundled.

## Related article

Taka is the author's game character with an existing rig, skinning and developed basic animations. See the [Kimodo article](https://zenn.dev/nakanishitf/articles/86ee54b68edee8) for motion-retargeting context.

## Verified environment

The mesh-generation, rigging, five-motion retargeting and animated-GLB export stages were run on a Colab L4. The existing-rig resume path was also run. Browser loading, view changes and paused pose inspection were checked. The motion reference is byte-identical to the previous 10N experiment. Joint-deformation warnings remain in the tested examples; see [VALIDATION.md](VALIDATION.md).
