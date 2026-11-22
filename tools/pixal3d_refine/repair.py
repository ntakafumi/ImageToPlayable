"""Project source colors and repair unsupported bright marks on a static Pixal3D mesh."""
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter

from . import photo_paint as pp
from . import view_align as va, compare


def suppress_highlights(positions, uv, faces, texture, view, scale):
    height, width = texture.shape[:2]
    triangles = (uv * [width, height])[faces]
    face_map, bary = pp.rasterize(triangles, np.zeros(faces.shape), (height, width))
    covered = face_map >= 0
    atlas_indices = np.flatnonzero(covered)
    view_points = pp.to_view_space(positions, mesh_scale=scale)
    x, y, depth = pp.project(view_points, view)
    vheight, vwidth = view.image.shape[:2]
    winner, weights = pp.rasterize(np.column_stack((x, y))[faces], depth[faces], (vheight, vwidth))
    zbuffer = np.full(winner.shape, -np.inf)
    seen = winner >= 0
    zbuffer[seen] = (weights[seen] * depth[faces[winner[seen]]]).sum(1)
    # A small window protects real bright strokes despite residual camera error.
    radius = max(1, round(vwidth * .003))
    luminance = np.asarray(view.image[..., :3], dtype=np.float32).mean(2)
    source_max = maximum_filter(luminance, size=2 * radius + 1)
    extent = np.ptp(positions, axis=0).max() / scale
    repaired = texture.copy()
    flat = repaired.reshape(-1, texture.shape[-1])
    face_map = face_map.ravel()
    bary = bary.reshape(-1, 3)
    count = 0
    for start in range(0, len(atlas_indices), 150_000):
        indices = atlas_indices[start:start + 150_000]
        points = (bary[indices, :, None] * view_points[faces[face_map[indices]]]).sum(1)
        px, py, z = pp.project(points, view)
        ix = np.clip(px.astype(int), 0, vwidth-1)
        iy = np.clip(py.astype(int), 0, vheight-1)
        supported = ((px >= 0) & (px < vwidth) & (py >= 0) & (py < vheight) &
                     (view.image[iy, ix, 3] >= 245) & (z > 0) &
                     (np.abs(z - zbuffer[iy, ix]) <= extent * .0015))
        old = flat[indices, :3].astype(np.float32)
        bright = old.mean(1)
        excess = bright - source_max[iy, ix]
        # Only repair strong near-neutral highlights unsupported by the whole source window.
        strength = pp.smoothstep(excess, 36, 76) * pp.smoothstep(bright, 125, 190)
        strength *= pp.smoothstep(65 - np.ptp(old, axis=1), 0, 38) * supported
        active = strength > 0
        rgb = pp.sample_rgb(view.image, px[active], py[active])
        mix = strength[active, None]
        flat[indices[active], :3] = np.rint(old[active] * (1-mix) + rgb * mix).astype(np.uint8)
        count += int(active.sum())
    repaired, _ = pp._grow_into_gutter(repaired, covered.astype(float), covered, 4)
    return repaired, count


def run(model, views_dir, output):
    model, views_dir, output = map(Path, (model, views_dir, output))
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError('Use an empty output folder')
    data = model.read_bytes()
    doc, _ = pp._split_glb(data)
    if doc.get('skins') or doc.get('animations'):
        raise ValueError('Use a static GLB before rigging')
    positions, uv, faces, texture = pp.read_glb(model)
    views, scale = pp.load_views(views_dir)
    if len(views) != 1:
        raise ValueError('Expected a Pixal3D single-view capture')
    aligned, alignment = va.align_view(views[0], positions, uv, faces, texture, pp.PIXAL3D_FRAME, scale)
    if alignment.iou_after < .65:
        raise ValueError('Source silhouette alignment is too weak')
    projected, _ = pp.paint_texture(texture, positions, uv, faces, [aligned], scale,
                                    settings=pp.Settings(align=False))
    repaired, count = suppress_highlights(positions, uv, faces, projected, aligned, scale)
    errors = compare.render_colours(output, positions, uv, faces,
                                    (texture, projected, repaired), views[0], scale)
    destination = output / 'model.refined.glb'
    destination.write_bytes(pp.replace_base_colour(data, pp.encode_png(repaired)))
    report = dict(aligned_outline_iou=float(alignment.iou_after), highlight_texels=count,
                  triangles=len(faces), rgb_mae_raw_projection_and_refined=errors)
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
