"""Run the shared TokenRig and existing Taka transfer stages for one static GLB."""
from pathlib import Path
import hashlib
import json

from colab_runtime import run_logged

CLIPS = {'Idle_preview', 'Walk_preview', 'Jog_preview', 'Run_preview', 'Jump_preview'}


def metadata(path):
    import struct
    with Path(path).open('rb') as stream:
        magic, version, size, length, chunk = struct.unpack('<4sIII4s', stream.read(20))
        if (magic, version, chunk) != (b'glTF', 2, b'JSON') or size != Path(path).stat().st_size:
            raise ValueError(f'Invalid GLB: {path}')
        return json.loads(stream.read(length))


def run_case(root, engine, source, job, pixal_front=True):
    root, engine, source, job = map(Path, (root, engine, source, job))
    source = source.resolve(strict=True)
    doc = metadata(source)
    if not doc.get('meshes') or doc.get('skins') or doc.get('animations'):
        raise ValueError('リグやアニメーションが入る前の静的GLBを指定してください。')
    job.mkdir(parents=True, exist_ok=True)
    python = engine / 'venv/bin/python'
    normalized = source
    if pixal_front:
        normalized = job / 'mesh.glb'
        run_logged([python, root/'tools/orient_pixal_input.py', source, normalized], job/'orientation.log')
    rig = job / 'rigged.glb'
    run_logged([python, root/'reference/rig_mesh.py', '--engine', engine,
                '--mesh', normalized, '--out', rig, '--seed', 1011], job/'rig.log')
    if not metadata(rig).get('skins'):
        raise ValueError('TokenRigの出力にスキンがありません。')
    transfer = job / 'transfer'
    run_logged([python, root/'tools/prepare_transfer.py', '--source', rig, '--out', transfer],
               job/'transfer.log')
    final = metadata(transfer/'character/character.glb')
    if {a['name'] for a in final.get('animations', [])} != CLIPS:
        raise ValueError('02と同じ5本のTaka動作を確認できません。')
    report = json.loads((transfer/'result.json').read_text())
    reference_sha = hashlib.sha256((root/'motions/taka-motion.json').read_bytes()).hexdigest()
    if report['motion_sha256'] != reference_sha:
        raise ValueError('動作参照が02のtaka-motion.jsonと一致しません。')
    return transfer
