# Third-party components

Original independent tutorial code is MIT-licensed. The Blender API script tools/animate10.py is GPL-3.0-or-later; see LICENSE and LICENSING.md.
Dependencies and pretrained weights are downloaded separately; their own licenses apply.
No character meshes, textures, model weights, or complete upstream source trees are bundled. The included Taka animation reference has separate terms in MOTIONS_LICENSE.md.

| Component | Role | Official source |
| --- | --- | --- |
| TRELLIS / TRELLIS-image-large | Image to textured mesh | https://github.com/microsoft/TRELLIS |
| SkinTokens / TokenRig | Skeleton and skin weights | https://github.com/VAST-AI-Research/SkinTokens |
| Qwen3-0.6B | TokenRig dependency | https://huggingface.co/Qwen/Qwen3-0.6B |
| DINOv2 | TRELLIS image encoder | https://github.com/facebookresearch/dinov2 |
| PyTorch / torchvision | GPU inference | https://pytorch.org/ |
| nvdiffrast / Kaolin | GPU geometry and rendering | https://github.com/NVlabs/nvdiffrast ; https://github.com/NVIDIAGameWorks/kaolin |
| mip-splatting rasterizer | Texture extraction | https://github.com/autonomousvision/mip-splatting |
| FlashAttention / spconv | GPU operators | https://github.com/Dao-AILab/flash-attention ; https://github.com/traveller59/spconv |
| bpy | Rig export via Blender | https://www.blender.org/about/license/ |
| trimesh / xatlas / Pillow / NumPy / SciPy | Geometry and images | https://trimesh.org/ ; https://github.com/jpcy/xatlas-python ; https://python-pillow.org/ ; https://numpy.org/ ; https://scipy.org/ |
| Three.js | Viewer, controls and GLB export | https://github.com/mrdoob/three.js (MIT) |

Pinned source commits and weight revisions are specified in reference/setup_l4.py,
reference/generate_mesh.py and reference/rig_mesh.py. Transitive dependencies have
additional terms. A permissive tutorial-code license does not replace those terms.
The viewer fetches Three.js from jsDelivr at runtime; internet access is required.

## Restrictions in the installed image-generation environment

The environment is not wholly MIT-licensed and is not offered as a commercially unrestricted stack.

* nvdiffrast at 253ac4fcea7de5f396371124af597e6cc957bfae uses the [NVIDIA Source Code License](https://raw.githubusercontent.com/NVlabs/nvdiffrast/253ac4fcea7de5f396371124af597e6cc957bfae/LICENSE.txt). Section 3.3 limits use to non-commercial research or evaluation without direct or indirect monetary gain.
* The rasterizer actually built from mip-splatting at dda02ab5ecf45d6edb8c540d9bb65c7e451345a9 has its own [Gaussian-Splatting License](https://raw.githubusercontent.com/autonomousvision/mip-splatting/dda02ab5ecf45d6edb8c540d9bb65c7e451345a9/submodules/diff-gaussian-rasterization/LICENSE.md), restricting use to non-commercial research or evaluation unless separately permitted.
* Blender Python API scripts have GPL-related distribution requirements. The script and complete GPL text are provided in this source tree; see LICENSING.md.

The MIT license of TRELLIS or SkinTokens does not override these dependencies.
No commercial-use permission for these components is supplied by this repository.

## Notebook 03

`tools/pixal3d_refine/{photo_paint,view_align}.py` are adapted from
[AssetFurnace / image-to-3dlab](https://github.com/Bingeljell/image-to-3dlab/tree/a319975821a6437258cf299e8154aa286a63d9ad)
at commit `a319975821a6437258cf299e8154aa286a63d9ad` (Apache-2.0).
Imports were adjusted to use this package.
See [license](LICENSES/AssetFurnace-LICENSE.txt) and [upstream notice](LICENSES/AssetFurnace-NOTICE.txt).
Notebook 03 builds [pixal3d.cpp](https://github.com/raven38/pixal3d.cpp) with CUDA and GGML.
It downloads single-view Pixal3D weights with DINOv3 and NAF, and uses the
[BiRefNet-lite ONNX conversion](https://huggingface.co/AssetFurnace/birefnet-lite-onnx) for opaque inputs.
Pinned weights and hashes are listed in `reference/pixal3d_models.json`.
The corresponding generation and matting notices are under `LICENSES/Pixal3D/`.
NumPy, SciPy, Pillow, OpenCV Python and ONNX Runtime are installed separately.

## Notebook 05 Paint3D

| Runtime component | Source and terms |
| --- | --- |
| Paint3D code | [OpenTexture/Paint3D at d5545d3](https://github.com/OpenTexture/Paint3D/tree/d5545d38db6aaf78efc563269f70177688a4218e), Apache-2.0. See [license text](LICENSES/Paint3D-LICENSE.txt). |
| UV Position ControlNet | [GeorgeQi/Paint3d_UVPos_Control](https://huggingface.co/GeorgeQi/Paint3d_UVPos_Control), model card tagged Apache-2.0. |
| Tile ControlNet | [lllyasviel/control_v11f1e_sd15_tile](https://huggingface.co/lllyasviel/control_v11f1e_sd15_tile), model card tagged OpenRAIL. |
| Realistic Vision V1.3 | [GeorgeQi's conversion](https://huggingface.co/GeorgeQi/realisticVisionV13_v13) is tagged Apache-2.0. The [original SG161222 release](https://huggingface.co/SG161222/Realistic_Vision_V1.3) is tagged CreativeML Open RAIL-M. The original model's use restrictions are relevant to the conversion. |
| Python GPU runtime | [NVIDIA Kaolin 0.13.0](https://github.com/NVIDIAGameWorks/kaolin/blob/v0.13.0/LICENSE), [PyTorch 1.12.1](https://github.com/pytorch/pytorch/blob/v1.12.1/LICENSE), [NVIDIA CUDA terms](https://docs.nvidia.com/cuda/archive/11.6.2/eula/index.html), and [Diffusers 0.25.0](https://github.com/huggingface/diffusers/blob/v0.25.0/LICENSE). |

Paint3D was developed by Xianfang Zeng and colleagues. See [Paint3D at CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Zeng_Paint3D_Paint_Anything_3D_with_Lighting-Less_Texture_Diffusion_Models_CVPR_2024_paper.html). The notebook fetches the code, packages and weights at runtime and the repository includes a copy of Paint3D's license for reference.
