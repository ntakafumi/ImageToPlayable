"""公開TokenRigを呼び出す。ゲーム固有の補正は含まない。"""
import argparse,os,sys,subprocess,socket,signal
from pathlib import Path

def main(engine, source, destination, seed):
    import random,numpy as np,torch
    from huggingface_hub import snapshot_download
    repo=engine/'SkinTokens';os.chdir(repo);sys.path.insert(0,str(repo))
    snapshot_download('VAST-AI/SkinTokens',revision='79736cad0fd84de384d5eede659b4ebd24effe33',
        cache_dir=engine/'cache',local_dir=repo,allow_patterns=[
        'experiments/articulation_xl_quantization_256_token_4/grpo_1400.ckpt',
        'experiments/skin_vae_2_10_32768/last.ckpt'])
    snapshot_download('Qwen/Qwen3-0.6B',revision='c1899de289a04d12100db370d81485cdf75e47ca',
        cache_dir=engine/'cache',local_dir=repo/'models/Qwen3-0.6B',
        allow_patterns=['config.json','generation_config.json','tokenizer*','vocab.json','merges.txt','LICENSE'])
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    from src.server import spec
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    spec.BPY_PORT=port;spec.BPY_SERVER=f'http://localhost:{port}'
    import demo
    server_script=(f'from src.server import spec; spec.BPY_PORT={port}; '
        f'spec.BPY_SERVER="http://localhost:{port}"; '
        'from src.server.bpy_server import run; run()')
    server=subprocess.Popen([sys.executable,'-c',server_script],cwd=repo,start_new_session=True)
    destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        demo.wait_for_bpy_server(timeout=90)
        demo.run_rig([source],top_k=5,top_p=.95,temperature=1.0,repetition_penalty=2,
            num_beams=10,use_skeleton=False,use_transfer=True,use_postprocess=True,
            output_paths=[destination],
            model_ckpt='experiments/articulation_xl_quantization_256_token_4/grpo_1400.ckpt',hf_path=None)
    finally:
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=30)
    if not destination.is_file():raise RuntimeError('リグ付きGLBが作成されませんでした')
    print('リグ付きメッシュ保存:',destination,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True)
    p.add_argument('--mesh',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,default=1011)
    a=p.parse_args();main(a.engine.resolve(),a.mesh.resolve(),a.out.resolve(),a.seed)
