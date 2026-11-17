# License scope and generation restrictions

## Independent code and Blender scripts

The original independent tutorial code and documentation are MIT-licensed.
`tools/animate10.py`, which calls the Blender Python API, is provided under GPL-3.0-or-later.
The complete GPL text and the script source are included. MIT helper modules remain MIT-licensed and retain their notices; when combined with Blender, comply with the GPL requirements for that combination.
Blender and bpy binaries are downloaded separately and are not included in this repository.
See [Blender's licensing explanation](https://www.blender.org/about/license/) and [FAQ](https://www.blender.org/support/faq/).
A GPL-licensed production tool does not automatically make its ordinary GLB or video outputs GPL-licensed.

## Restricted dependencies in notebook 01

TRELLIS and SkinTokens code and the selected model cards identify their own licenses as MIT.
This does not describe the entire execution environment.
The mesh-generation path downloads, builds and uses the following restricted components:

| Component and pinned source | Terms relevant to use |
| --- | --- |
| [nvdiffrast, 253ac4f](https://raw.githubusercontent.com/NVlabs/nvdiffrast/253ac4fcea7de5f396371124af597e6cc957bfae/LICENSE.txt) | NVIDIA Source Code License, section 3.3: non-commercial research or evaluation, without direct or indirect monetary gain |
| [diff-gaussian-rasterization inside mip-splatting, dda02ab](https://raw.githubusercontent.com/autonomousvision/mip-splatting/dda02ab5ecf45d6edb8c540d9bb65c7e451345a9/submodules/diff-gaussian-rasterization/LICENSE.md) | Gaussian-Splatting License: non-commercial research and evaluation; other uses require permission |

Run this image-generation configuration only within the upstream permissions you hold.
For commercial production, obtain appropriate permissions or replace and validate the restricted components.
Downloading these dependencies separately does not remove their use restrictions.
Adding this notice does not authorize an otherwise prohibited use.

Notebook 02 can reopen an already completed result without executing the image-generation stage.
This distinction does not retrospectively authorize the purpose for which an asset was generated.

## Motions, characters and outputs

The Taka reference contains the creator's newly generated and subsequently adjusted motions, not MotionBricks sample-dataset clips, as confirmed by the creator.
Its separate license is specified in MOTIONS_LICENSE.md.
No third-party motion dataset, model weights, Taka/Takanyan meshes, textures or game environment are bundled.

Code licensing, permission to run a generation tool, and rights in an input or output are distinct.
Neither MIT nor GPL grants rights to someone else's input artwork, character or motion data.
The research-use terms above concern use of the respective software; they do not by themselves establish a new copyright license for every generated output.
Do not interpret this distinction as permission to use a research-only tool for commercial asset production.
