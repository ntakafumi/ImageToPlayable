"""CPU-only transfer environment for an already generated rig."""
from pathlib import Path
import subprocess,sys,argparse

def main(base):
    base.mkdir(parents=True,exist_ok=True)
    def run(*args):subprocess.run(list(map(str,args)),check=True)
    run(sys.executable,'-m','pip','install','-q','--target',base/'bootstrap','uv==0.9.5')
    uv=base/'bootstrap/bin/uv'
    run(uv,'python','install','3.11.14')
    if not (base/'venv/bin/python').exists():run(uv,'venv','--seed','--python','3.11.14',base/'venv')
    run(uv,'pip','install','--python',base/'venv/bin/python','bpy==4.3.0','numpy==1.26.4','scipy==1.15.2','Pillow==11.1.0')
    run(base/'venv/bin/python','-c','import bpy,numpy,scipy;print("Transfer environment ready",bpy.app.version_string)')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);main(p.parse_args().base)
