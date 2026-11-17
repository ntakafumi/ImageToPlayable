"""Validate the public package without shipping the author's character assets."""
from pathlib import Path
import ast,json,hashlib
r=Path(__file__).resolve().parent
for p in r.rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
for p in r.glob('*.ipynb'):
    n=json.loads(p.read_text())
    for i,c in enumerate(n['cells']):
        assert not c.get('outputs'),p.name
        if c['cell_type']=='code':
            source=''.join(c['source'])
            assert not source.startswith('%'),f'Notebook must call the Drive source tree: {p.name}'
            ast.parse(source,filename=f'{p.name}:{i}')
    first=next(c for c in n['cells']if c['cell_type']=='code')
    assert 'drive.mount' in ''.join(first['source'])
    assert 'files.upload' not in ''.join(first['source'])
motion=json.loads((r/'motions/taka-motion.json').read_text())
assert motion['geometry_included'] is False and motion['global_amplitude']==1
assert set(motion['clips'])=={'Idle_preview','Walk_preview','Jog_preview','Run_preview','Jump_preview'}
for clip in motion['clips'].values():
    assert clip['frames'] and clip['duration']>0
    for frame in clip['frames']:
        for side in ['left','right']:
            for role in ['arm','forearm','thigh','knee','foot']:
                d=frame[f'{side}_{role}'];assert len(d)==3 and abs(sum(x*x for x in d)-1)<1e-5
blocked={'.png','.jpg','.jpeg','.gif','.mp4','.mov','.glb','.gltf','.bin','.safetensors','.ckpt','.zip','.blend'}
for p in r.rglob('*'):
    if p.is_file():assert p.suffix.lower() not in blocked,f'Bundled character asset: {p}'
print('PASS: syntax, clean notebook outputs, five full-amplitude motion references, no character binary assets')
