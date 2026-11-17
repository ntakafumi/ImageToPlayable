"""Normalize a predicted rig, then reuse the tested Taka transfer/corrective stages."""
from pathlib import Path
import argparse,json,subprocess,sys,shutil,os
# Bound BLAS threading for many small joint transforms.
os.environ["OPENBLAS_NUM_THREADS"]="2"
os.environ["OMP_NUM_THREADS"]="2"
import numpy as np
from scipy.spatial.transform import Rotation
from glb10 import GLB,digest
from transfer10j import worlds

def align(source,out):
    g=GLB(source);w=worlds(g)
    joints=sorted({j for skin in g.meta['skins'] for j in skin['joints']})
    points=np.array([w[i][:3,3] for i in joints]);xz=points[:,[0,2]];xz-=xz.mean(0)
    cov=xz.T@xz
    phi=.5*np.arctan2(2*cov[0,1],cov[0,0]-cov[1,1])
    lateral=np.array([np.cos(phi),0,np.sin(phi)])
    mesh=np.concatenate([p for _,p in g.pose()[0]]);h=np.ptp(mesh[:,1]);lo=mesh[:,1].min()
    parents={c:i for i,n in enumerate(g.nodes)for c in n.get('children',[])}
    forward=np.zeros(3)
    for i in joints:
        p=parents.get(i)
        if p not in joints:continue
        a,b=w[p][:3,3],w[i][:3,3]
        if max(a[1],b[1])<lo+.15*h:
            d=b-a;d[1]=0;d-=lateral*(d@lateral)
            if np.linalg.norm(d)>.002*h:forward+=d
    yaw=float(phi+(np.pi if -np.sin(phi)*forward[0]+np.cos(phi)*forward[2]<0 else 0))
    scene=g.meta['scenes'][g.meta.get('scene',0)]
    root=len(g.nodes);g.nodes.append(dict(name='InputAxisNormalization',children=list(scene['nodes']),rotation=Rotation.from_euler('y',yaw).as_quat().tolist()))
    scene['nodes']=[root];g.write(out)
    return dict(yaw_degrees=float(np.degrees(yaw)),source_sha256=digest(source))

def restore_completed(source, out, reference):
    """Resume a verified result from this input, without re-rigging its posed bones."""
    imported = source.parent / 'completed-input'
    if not imported.is_dir():
        return False
    info = json.loads((imported / 'character.json').read_text())
    model = imported / 'character.glb'
    if digest(model) != digest(source) or digest(model) != info.get('output_sha256'):
        raise ValueError('保存結果のモデルSHA-256が一致しません。再加工せず停止します。')
    if info.get('motion_reference_sha256') != digest(reference):
        raise ValueError('保存結果のTaka動作参照がこの版と異なります。自動で再移植せず停止します。')
    g = GLB(model)
    expected = {'Idle_preview', 'Walk_preview', 'Jog_preview', 'Run_preview', 'Jump_preview'}
    clips = {a.get('name') for a in g.meta.get('animations', [])}
    if not expected.issubset(clips) or not g.meta.get('skins'):
        raise ValueError('保存結果の5動作またはスキンが不足しています。')
    validation = json.loads((imported / 'validation-report.json').read_text())
    if not validation.get('direction_gate_passed'):
        raise ValueError('保存結果の方向一致検査を確認できません。')
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'character'
    shutil.copytree(imported, target, dirs_exist_ok=True)
    result = dict(status='complete' if validation.get('numeric_gate_passed') else 'complete_with_warnings',
                  model_sha256=digest(model), motion_sha256=digest(reference),
                  global_amplitude=1.0, validation=validation, operation='resume_completed_input')
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print('入力済みの5動作を保持して再表示します。リギング・動作移植は重ねて適用しません。', flush=True)
    return True

def main(source,out):
    out.mkdir(parents=True,exist_ok=True)
    tools=Path(__file__).resolve().parent
    reference=tools.parent/'motions/taka-motion.json'
    if restore_completed(source,out,reference):
        return
    normalization=align(source,out/'aligned.glb')
    def run(name,*args):
        print('Stage:',name,flush=True)
        subprocess.run([sys.executable,str(tools/name),*map(str,args)],check=True)
    prepared=out/'prepared';target=out/'character'
    # Only a normalized bind pose and semantic mapping are produced here.
    run('animate10.py','--source',out/'aligned.glb','--out',prepared,'--profile','humanoid')
    reference=tools.parent/'motions/taka-motion.json'
    run('transfer10j.py','--source',prepared,'--reference',reference,'--out',target)
    shutil.copy2(target/'character.glb',target/'pre-foot-calibration.glb')
    run('calibrate_feet10n.py','--folder',target)
    run('joint_correctives10j.py','--folder',target)
    run('preserve_clearance10n.py','--folder',target,'--reference',target/'pre-foot-calibration.glb')
    run('validate10j.py','--folder',target,'--original',prepared)
    report=json.loads((target/'validation-report.json').read_text())
    if not report.get('direction_gate_passed'):raise RuntimeError('Taka方向一致検査不合格。簡易動作へは置き換えません。')
    info=json.loads((target/'character.json').read_text())
    result=dict(status='complete' if report.get('numeric_gate_passed') else 'complete_with_warnings',model_sha256=digest(target/'character.glb'),motion_sha256=digest(reference),global_amplitude=1.0,normalization=normalization,validation=report)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('OUTPUT',target/'character.glb',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.source,a.out)
