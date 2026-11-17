"""教材用の独立環境。生成APIとゲーム素材を使わず、公開モデルを実行する。"""

from pathlib import Path
import subprocess, sys, os, json, urllib.request, argparse, hashlib

PINS = {'TRELLIS': {'url': 'https://github.com/microsoft/TRELLIS.git', 'commit': '193e0502b5cb3eb5997ec457d5340e95d09b158e'}, 'nvdiffrast': {'url': 'https://github.com/NVlabs/nvdiffrast.git', 'commit': '253ac4fcea7de5f396371124af597e6cc957bfae'}, 'mip-splatting': {'url': 'https://github.com/autonomousvision/mip-splatting.git', 'commit': 'dda02ab5ecf45d6edb8c540d9bb65c7e451345a9'}}

SKIN = "273b691d35989d71cd17ff2895fdc735097b92d1"


def run(args, **kw):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kw)


def setup(base):
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    gpu_line = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=name,compute_cap,memory.total",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    ).strip()
    name, cap, memory = [part.strip() for part in gpu_line.split(",")]
    if not any(kind in name for kind in ["L4", "A100"]):
        raise RuntimeError("この版の対応GPUはL4またはA100です: " + name)
    if float(memory) < 20000:
        raise RuntimeError("20GB以上のGPUメモリが必要です")
    gpu = dict(name=name, compute_capability=cap, memory_mib=float(memory))
    fingerprint = hashlib.sha256(
        (
            Path(__file__).read_text()
            + json.dumps(PINS,sort_keys=True)
            + cap
        ).encode()
    ).hexdigest()
    marker = base / "ready.json"
    print("専用環境の対象GPU:", gpu, flush=True)
    if (
        marker.is_file()
        and json.loads(marker.read_text()).get("setup_sha256") == fingerprint
    ):
        py = base / "venv/bin/python"
        run(
            [
                py,
                "-c",
                "import torch,bpy,flash_attn,kaolin,spconv.pytorch,nvdiffrast.torch,diff_gaussian_rasterization; assert torch.cuda.is_available(); print(torch.cuda.get_device_name())",
            ]
        )
        print("検査済みの専用環境を使います。", flush=True)
        return
    os.environ.update(
        MAX_JOBS="2", TORCH_CUDA_ARCH_LIST=cap, CUDA_HOME="/usr/local/cuda-12.8"
    )
    os.environ["PATH"] = "/usr/local/cuda-12.8/bin:" + os.environ["PATH"]
    apt = [
        "apt-get",
        "-o",
        "Acquire::ForceIPv4=true",
        "-o",
        "Acquire::Retries=2",
        "-o",
        "Acquire::https::Timeout=60",
        "-o",
        "Acquire::http::Timeout=60",
    ]
    run(apt + ["update", "-qq"])
    run(
        apt
        + [
            "install",
            "-y",
            "-qq",
            "--no-install-recommends",
            "cuda-compiler-12-8",
            "cuda-libraries-dev-12-8",
            "libegl1",
            "libgl1",
            "libopengl0",
            "libglib2.0-0",
            "libxrender1",
            "libsm6",
            "libxi6",
            "libxxf86vm1",
            "libxfixes3",
            "libxcursor1",
            "libxinerama1",
            "libxrandr2",
        ]
    )
    boot = base / "bootstrap"
    run([sys.executable, "-m", "pip", "install", "-q", "--target", boot, "uv==0.9.5"])
    uv = boot / "bin/uv"
    os.environ["UV_PYTHON_INSTALL_DIR"] = str(base / "python")
    run([uv, "python", "install", "3.11.14"])
    env = base / "venv"
    py = env / "bin/python"
    if not py.exists():
        run([uv, "venv", "--seed", "--python", "3.11.14", env])

    def pip(*a):
        run([uv, "pip", "install", "--python", py, *a])

    pip(
        "torch==2.7.0",
        "torchvision==0.22.0",
        "torchaudio==2.7.0",
        "--index-url",
        "https://download.pytorch.org/whl/cu128",
    )
    pip(
        "numpy==1.26.4",
        "transformers==4.57.6",
        "diffusers==0.35.2",
        "huggingface-hub==0.36.0",
        "bpy==4.3.0",
        "omegaconf==2.3.0",
        "Pillow==11.1.0",
        "einops",
        "trimesh==4.6.8",
        "xatlas==0.0.9",
        "moderngl==5.10.0",
        "rembg==2.0.65",
        "onnxruntime==1.21.0",
        "imageio[ffmpeg]",
        "matplotlib==3.11.2",
        "gradio==5.50.0",
        "python-box",
        "lightning",
        "addict",
        "fast-simplification",
        "open3d",
        "bottle",
        "tornado",
        "scipy",
        "scikit-image",
        "ninja",
        "packaging",
        "psutil",
        "setuptools<81",
        "wheel",
        "pybind11",
        "tensorboard",
    )
    pip(
        "scikit-build-core",
        "cmake",
        "easydict",
        "plyfile",
        "pyvista==0.46.4",
        "pymeshfix==0.17.1",
        "igraph",
        "opencv-python-headless==4.10.0.84",
        "spconv-cu120==2.3.6",
    )
    pip(
        "git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8"
    )
    release = json.load(
        urllib.request.urlopen(
            "https://api.github.com/repos/Dao-AILab/flash-attention/releases/tags/v2.8.3"
        )
    )
    urls = [
        a["browser_download_url"]
        for a in release["assets"]
        if "cu12torch2.7cxx11abiTRUE-cp311-cp311-linux_x86_64" in a["name"]
    ]
    if not urls:
        raise RuntimeError(
            "対応するFlashAttention wheelがありません。版を確認してください。"
        )
    pip(urls[0])
    for repo, sha in [("SkinTokens", SKIN)]:
        path = base / repo
        if not (path / ".git").exists():
            run(
                [
                    "git",
                    "clone",
                    "--filter=blob:none",
                    "--no-checkout",
                    "https://github.com/VAST-AI-Research/" + repo + ".git",
                    path,
                ]
            )
        run(["git", "-C", path, "fetch", "--depth", "1", "origin", sha])
        run(["git", "-C", path, "checkout", "--detach", sha])
    run(
        [
            py,
            "-c",
            "import torch,bpy,flash_attn; print(torch.cuda.get_device_name(),torch.__version__); assert torch.cuda.is_available()",
        ]
    )
    pip(
        "https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.7.0_cu128/kaolin-0.18.0-cp311-cp311-linux_x86_64.whl"
    )
    setup_trellis(base, py, pip, run)
    with (base / "packages.txt").open("w") as f:
        subprocess.run([py, "-m", "pip", "freeze"], stdout=f, check=True)
    marker.write_text(
        json.dumps(
            dict(setup_sha256=fingerprint, skin_commit=SKIN, gpu=gpu),
            indent=2,
        )
    )
    print("専用環境の準備完了", flush=True)


def setup_trellis(base, py, pip, run):
    pins = PINS
    for name in ["TRELLIS", "nvdiffrast", "mip-splatting"]:
        pin = pins[name]
        path = base / name
        if not (path / ".git").exists():
            run(
                [
                    "git",
                    "clone",
                    "--filter=blob:none",
                    "--no-checkout",
                    pin["url"],
                    path,
                ]
            )
        run(["git", "-C", path, "fetch", "--depth", "1", "origin", pin["commit"]])
        run(["git", "-C", path, "checkout", "--detach", pin["commit"]])
        run(["git", "-C", path, "submodule", "update", "--init", "--recursive"])
    pip("--no-build-isolation", str(base / "nvdiffrast"))
    pip(
        "--no-build-isolation",
        str(base / "mip-splatting/submodules/diff-gaussian-rasterization"),
    )
    run(
        [
            py,
            "-c",
            'import spconv.pytorch, nvdiffrast.torch, diff_gaussian_rasterization; print("TRELLIS rendering dependencies OK")',
        ]
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    setup(p.parse_args().base)
