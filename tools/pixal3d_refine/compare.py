"""Render controlled before/after images without WebGL or a GPU."""
from dataclasses import replace

import numpy as np
from PIL import Image, ImageDraw

from . import photo_paint as pp, view_align as va


def panel(canvas, rgb, seen, row, col, label, size):
    x, y = col * size, row * (size + 24)
    canvas.paste(Image.fromarray(rgb).convert('RGB'), (x, y + 24), Image.fromarray(seen))
    ImageDraw.Draw(canvas).text((x + 10, y + 5), label, fill='white')


def render_colours(folder, points, uv, faces, textures, view, scale, size=512):
    photo = Image.fromarray(view.image).resize((size, size), Image.Resampling.LANCZOS)
    view = replace(view, image=np.asarray(photo))
    renders = []
    errors = []
    for texture in textures:
        seen, rgb = va.render_own_paint(points, uv, faces, texture, view, pp.PIXAL3D_FRAME, scale)
        renders.append((seen, rgb))
        valid = seen & (view.image[..., 3] >= 245)
        errors.append(float(np.abs(rgb[valid].astype(float) - view.image[valid, :3]).mean()))
    for filename, columns in (
        ('00_projection.jpg', ((0, 'Raw Pixal3D'), (1, 'Source projection'))),
        ('01_colour.jpg', ((1, 'Source projection'), (2, 'Final refinement'))),
    ):
        canvas = Image.new('RGB', (3 * size, size + 24), '#263445')
        canvas.paste(photo, (0, 24), photo)
        ImageDraw.Draw(canvas).text((10, 5), 'Source', fill='white')
        for column, (index, label) in enumerate(columns, 1):
            seen, rgb = renders[index]
            panel(canvas, rgb, seen, 0, column, label, size)
        canvas.save(folder / filename, quality=93)
    return errors
