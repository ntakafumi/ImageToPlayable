# Third-party components

The MIT license in this repository applies to the original tutorial code only.
Dependencies and pretrained weights are downloaded separately; their own licenses apply.
No character meshes, textures, model weights, or upstream source trees are bundled. The included Taka animation reference has separate terms in MOTIONS_LICENSE.md.

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
