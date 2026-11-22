"""Bake the standard single-view Pixal3D front into the Taka +Z convention."""
import sys
from pathlib import Path
import numpy as np
from pixal3d_refine import photo_paint as pp


def main(source, output):
    pp.read_glb(source)  # Reject node transforms and multiple primitives.
    doc, blob = pp._split_glb(source.read_bytes())
    binary = bytearray(blob)
    attrs = doc['meshes'][0]['primitives'][0]['attributes']
    for kind, width in [('POSITION', 3), ('NORMAL', 3), ('TANGENT', 4)]:
        if kind not in attrs:
            continue
        accessor = doc['accessors'][attrs[kind]]
        view = doc['bufferViews'][accessor['bufferView']]
        values = np.ndarray((accessor['count'], width), dtype='<f4', buffer=binary,
                            offset=view.get('byteOffset', 0) + accessor.get('byteOffset', 0),
                            strides=(view.get('byteStride', 4 * width), 4))
        values[:, [0, 2]] *= -1
        if 'min' in accessor or kind == 'POSITION':
            accessor['min'] = values.min(axis=0).tolist()
            accessor['max'] = values.max(axis=0).tolist()
    output.write_bytes(pp._join_glb(doc, bytes(binary)))


if __name__ == '__main__':
    main(*map(Path, sys.argv[1:]))
