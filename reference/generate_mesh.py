"""単一画像をTRELLISのメッシュへ変換する教材用スクリプト。"""
import argparse,json,os,sys,math
from pathlib import Path
os.environ.setdefault('CUDA_HOME','/usr/local/cuda-12.8')
os.environ['PATH']='/usr/local/cuda-12.8/bin:'+os.environ['PATH']
os.environ.update(ATTN_BACKEND='flash_attn',SPARSE_ATTN_BACKEND='flash_attn',SPARSE_BACKEND='spconv',HF_HUB_DISABLE_XET='1')

def main(engine, source, destination, yaw):
    from PIL import Image
    from huggingface_hub import snapshot_download
    sys.path.insert(0,str(engine/'TRELLIS'))
    from trellis.pipelines import TrellisImageTo3DPipeline
    from trellis.utils import postprocessing_utils
    repository='microsoft/TRELLIS-image-large'
    revision='25e0d31ffbebe4b5a97464dd851910efc3002d96'
    cache=engine/'cache'
    config_dir=Path(snapshot_download(repository,revision=revision,cache_dir=cache,allow_patterns=['pipeline.json']))
    config=json.loads((config_dir/'pipeline.json').read_text())
    config['args']['models'].pop('slat_decoder_rf',None)
    patterns=['pipeline.json']
    for prefix in config['args']['models'].values():
        patterns.extend([prefix+'.json',prefix+'.safetensors'])
    weights=Path(snapshot_download(repository,revision=revision,cache_dir=cache,allow_patterns=patterns))
    selected=engine/'mesh-model';selected.mkdir(exist_ok=True)
    for prefix in config['args']['models'].values():
        for suffix in ['.json','.safetensors']:
            target=selected/(prefix+suffix);target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.symlink_to(weights/(prefix+suffix))
    (selected/'pipeline.json').write_text(json.dumps(config))
    pipeline = TrellisImageTo3DPipeline.from_pretrained(str(selected))
    pipeline.cuda()
    image=pipeline.preprocess_image(Image.open(source))
    outputs=pipeline.run(image,seed=42,preprocess_image=False,formats=['mesh','gaussian'],
        sparse_structure_sampler_params={'steps':25},slat_sampler_params={'steps':25})
    destination.parent.mkdir(parents=True,exist_ok=True)
    asset=postprocessing_utils.to_glb(outputs['gaussian'][0],outputs['mesh'][0],
        simplify=.2,texture_size=2048,verbose=True)
    import trimesh
    if not isinstance(asset,trimesh.Trimesh):
        raise RuntimeError('単一のテクスチャ付きメッシュを想定しています')
    asset.apply_transform(trimesh.transformations.rotation_matrix(math.radians(yaw),[0,1,0]))
    asset.export(str(destination))
    print('メッシュ保存:',destination,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--front-yaw',type=float,default=-90.0)
    a=p.parse_args();main(a.engine,a.image,a.out,a.front_yaw)
