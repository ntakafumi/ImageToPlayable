"""Calibrate the foot's neutral world frame to the inferred bind mesh frame.
No character IDs or mesh edits. Retains authored foot rotation changes over time.
"""
from pathlib import Path
import argparse,json,numpy as np
from scipy.spatial.transform import Rotation
from glb10 import GLB,digest
from transfer10j import worlds,rot,mapping

def calibrate(folder):
 folder=Path(folder);g=GLB(folder/'character.glb');ar=json.loads((folder/'animation-report.json').read_text());roles,_=mapping(g,ar)
 idle=next(c for c in g.meta['animations']if c['name']=='Idle_preview')
 props=g.pose(idle,0,vertex_limit=1)[1];idleworld=worlds(g,props);bind=worlds(g)
 feet={s:roles[s+'_foot']for s in ['left','right']}
 correction={s:rot(bind[i])@rot(idleworld[i]).T for s,i in feet.items()}
 angles={s:float(np.degrees(Rotation.from_matrix(m).magnitude()))for s,m in correction.items()}
 for clip in g.meta['animations']:
  times=np.unique(np.concatenate([g.acc(s['input']).ravel()for s in clip['samplers']]))
  values={s:[]for s in feet}
  for t in times:
   props=g.pose(clip,float(t),vertex_limit=1)[1];world=worlds(g,props)
   for side,i in feet.items():
    parent=g.parents.get(i);p=rot(world[parent])if parent is not None else np.eye(3)
    q=Rotation.from_matrix(p.T@correction[side]@rot(world[i])).as_quat()
    if values[side] and np.dot(values[side][-1],q)<0:q=-q
    values[side].append(q)
  for side,i in feet.items():
   channel=next(ch for ch in clip['channels']if ch['target'].get('node')==i and ch['target']['path']=='rotation')
   ti=g.add_acc(times[:,None],'SCALAR');oi=g.add_acc(values[side],'VEC4')
   clip['samplers'].append(dict(input=ti,output=oi,interpolation='LINEAR'));channel['sampler']=len(clip['samplers'])-1
 g.write(folder/'character.glb')
 ar['foot_frame_calibration']=dict(method='neutral bind world frame; no global motion scaling',rotation_degrees=angles,assumption='bind mesh feet are flat and forward')
 (folder/'animation-report.json').write_text(json.dumps(ar,indent=2))
 info=json.loads((folder/'character.json').read_text());info['output_sha256']=digest(folder/'character.glb');(folder/'character.json').write_text(json.dumps(info,indent=2))
 print('Neutral foot frame correction:',angles,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args();calibrate(a.folder)
