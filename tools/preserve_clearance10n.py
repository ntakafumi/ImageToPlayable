"""After foot-frame and mesh corrections, preserve the prior vertical clearance.
The reference is a snapshot from the same newly generated character, not a saved substitute.
"""
from pathlib import Path
import argparse,json,numpy as np
from glb10 import GLB,digest
from transfer10j import worlds

def preserve(folder,reference):
 folder=Path(folder);reference=Path(reference);source=GLB(reference);g=GLB(folder/'character.glb')
 root=next(i for i,n in enumerate(g.nodes)if n.get('name')=='Armature');records=[]
 for clip in g.meta['animations']:
  original=next(c for c in source.meta['animations']if c['name']==clip['name'])
  times=np.unique(np.concatenate([g.acc(s['input']).ravel()for s in clip['samplers']]))
  values=[];deltas=[];heights=[]
  for t in times:
   target=max(0.0,min(P[:,1].min()for _,P in source.pose(original,float(t))[0]))
   posed,props=g.pose(clip,float(t));bottom=min(P[:,1].min()for _,P in posed);shift=target-bottom
   world=worlds(g,props);parent=g.parents.get(root);basis=world[parent][:3,:3]if parent is not None else np.eye(3)
   values.append(np.array(props[root]['translation'])+np.linalg.solve(basis,[0,shift,0]));deltas.append(float(shift));heights.append(float(target))
  channel=next(ch for ch in clip['channels']if ch['target'].get('node')==root and ch['target']['path']=='translation')
  ti=g.add_acc(times[:,None],'SCALAR');oi=g.add_acc(values,'VEC3');clip['samplers'].append(dict(input=ti,output=oi,interpolation='LINEAR'));channel['sampler']=len(clip['samplers'])-1
  records.append(dict(clip=clip['name'],maximum_vertical_adjustment=max(abs(v)for v in deltas),preserved_source_clearance_peak=max(heights)))
  print('Contact recalibration:',records[-1],flush=True)
 g.write(folder/'character.glb');info=json.loads((folder/'character.json').read_text());info['output_sha256']=digest(folder/'character.glb');(folder/'character.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
 (folder/'foot-contact-report.json').write_text(json.dumps(dict(reference_sha256=digest(reference),method='same-character source clearance preservation',records=records),indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);a=p.parse_args();preserve(a.folder,a.reference)
