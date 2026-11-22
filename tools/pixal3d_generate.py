"""Build pinned pixal3d.cpp for Colab CUDA and generate one static GLB."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

COMMIT = 'd1b4926452f9e09702b891db5f05acc845e153ed'
GGML_COMMIT = '737e88f25d4f62254f3b7a726fd9663036cc94da'
REPO = 'https://github.com/raven38/pixal3d.cpp.git'
MANIFEST = Path(__file__).resolve().parents[1] / 'reference/pixal3d_models.json'


def command(*args):
    subprocess.run([str(a) for a in args], check=True)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(directory, repo, revision, item):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / item['file']

    def valid(p):
        return p.is_file() and p.stat().st_size == item['bytes'] and sha256(p) == item['sha256']

    if valid(target):
        return target
    temp = target.with_suffix(target.suffix + '.part')
    url = f"https://huggingface.co/{repo}/resolve/{revision}/{item['file']}"
    command('curl', '--fail', '--location', '--retry', '3', '--connect-timeout', '30',
            '--silent', '--show-error', '--output', temp, url)
    if not valid(temp):
        raise ValueError(f"重みのサイズまたはSHA-256が一致しません: {item['file']}")
    temp.replace(target)
    return target


def setup(base):
    gpu = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=name,compute_cap', '--format=csv,noheader'],
        text=True).splitlines()[0]
    name, capability = (x.strip() for x in gpu.split(','))
    if 'L4' not in name and 'A100' not in name:
        raise RuntimeError(f'ColabのL4またはA100ランタイムを選んでください: {name}')
    nvcc = shutil.which('nvcc')
    for candidate in ('/usr/local/cuda/bin/nvcc', '/usr/local/cuda-12.8/bin/nvcc'):
        if not nvcc and Path(candidate).is_file():
            nvcc = candidate
    packages = [package for tool, package in [('cmake', 'cmake'), ('ninja', 'ninja-build'),
                ('c++', 'build-essential')] if shutil.which(tool) is None]
    if not nvcc:
        packages.extend(['cuda-compiler-12-8', 'cuda-libraries-dev-12-8'])
    if packages:
        command('apt-get', 'update', '-qq')
        command('apt-get', 'install', '-y', '--no-install-recommends', *packages)
    nvcc = nvcc or '/usr/local/cuda-12.8/bin/nvcc'
    if not Path(nvcc).is_file():
        raise RuntimeError('CUDAコンパイラ nvcc を確認できません。')
    base.mkdir(parents=True, exist_ok=True)
    arch = capability.replace('.', '')
    source = base / 'source'
    build = base / f'build-sm{arch}'
    executable = build / 'trellis-cli'
    if not (source / '.git').is_dir():
        command('git', 'init', source)
        command('git', '-C', source, 'remote', 'add', 'origin', REPO)
    if not executable.is_file() or not (build / 'ready.json').is_file():
        command('git', '-C', source, 'fetch', '--depth', '1', 'origin', COMMIT)
        command('git', '-C', source, 'checkout', '--detach', COMMIT)
        command('git', '-C', source, 'submodule', 'update', '--init', '--recursive')
        for directory, revision in ((source, COMMIT), (source/'thirdparty/ggml', GGML_COMMIT)):
            head = subprocess.check_output(['git', '-C', str(directory), 'rev-parse', 'HEAD'], text=True).strip()
            if head != revision:
                raise RuntimeError(f'Unexpected source revision: {head}')
        command('cmake', '-S', source, '-B', build, '-G', 'Ninja',
                '-DCMAKE_BUILD_TYPE=Release', '-DGGML_CUDA=ON', '-DGGML_NATIVE=OFF',
                '-DGGML_CUDA_NCCL=OFF', '-DTRELLIS_WEBP=OFF', '-DGGML_KLEIDIAI=OFF',
                f'-DCMAKE_CUDA_COMPILER={nvcc}', f'-DCMAKE_CUDA_ARCHITECTURES={arch}')
        command('cmake', '--build', build, '--target', 'trellis-cli', '--parallel', '2')
        command(executable, '--help')
        (build / 'ready.json').write_text(json.dumps(dict(runtime=COMMIT, ggml=GGML_COMMIT,
                                          gpu=name, cuda_arch=arch)))
    print('Pixal3D CUDA:', executable, flush=True)
    return executable


def cutout(source, out, cache, manifest):
    import numpy as np
    from PIL import Image, ImageOps
    from scipy.special import expit

    with Image.open(source) as image:
        if image.format not in {'PNG', 'JPEG'} or max(image.size) > 8192:
            raise ValueError('8192px以下のPNGまたはJPEGを指定してください。')
        rgba = ImageOps.exif_transpose(image).convert('RGBA')
    low, high = rgba.getchannel('A').getextrema()
    if high == 0:
        raise ValueError('画像が完全に透明です。')
    if low == 255:
        import onnxruntime as ort

        item = manifest['matte']
        model = fetch(cache / 'matte', item['repo'], item['revision'], item)
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        session = ort.InferenceSession(str(model), options, providers=['CPUExecutionProvider'])
        rgb = rgba.convert('RGB').resize((1024, 1024), Image.Resampling.LANCZOS)
        pixels = np.asarray(rgb, dtype=np.float32) / 255
        pixels -= np.array([.485, .456, .406], dtype=np.float32)
        pixels /= np.array([.229, .224, .225], dtype=np.float32)
        logits = session.run(None, {'input_image': pixels.transpose(2, 0, 1)[None]})[0]
        alpha = expit(logits[0, 0])
        if not np.isfinite(alpha).all() or alpha.max() < .5 or alpha.min() > .5:
            raise ValueError('背景と被写体を分離できませんでした。')
        mask = Image.fromarray(np.rint(alpha * 255).astype(np.uint8))
        rgba.putalpha(mask.resize(rgba.size, Image.Resampling.LANCZOS))
    rgba.save(out, format='PNG')
    return 'birefnet-lite' if low == 255 else 'preserved-alpha'


def generate(base, source, output, seed, fov_degrees):
    if not 0 <= seed < 2**31 or not 5 <= fov_degrees <= 80:
        raise ValueError('画角は5〜80度、シードは0〜2147483647を指定してください。')
    output.mkdir(parents=True)
    cache = base / 'models'
    manifest = json.loads(MANIFEST.read_text())
    png = output / 'input.png'
    background = cutout(source, png, cache, manifest)
    executable = setup(base)
    models = cache / 'pixal3d'
    for item in manifest['files']:
        print('Checking weight:', item['file'], flush=True)
        fetch(models, manifest['repo'], manifest['revision'], item)
    glb = output / 'model.glb'
    command(executable, '--models', models, '--sv-image', png, '--fov', math.radians(fov_degrees),
            '--seed', seed, '--res', '1024', '--require-gpu', '--threads', '2',
            '--webp', 'off', '--output', glb)
    views = output / 'model.svviews'
    if not glb.is_file() or not (views/'transforms.json').is_file() or not (views/'input.png').is_file():
        raise RuntimeError('Pixal3DのGLBまたは対応するカメラ情報がありません。')
    (output/'generation.json').write_text(json.dumps(dict(
        runtime=COMMIT, ggml=GGML_COMMIT, source_sha256=sha256(source),
        prepared_sha256=sha256(png), model_sha256=sha256(glb),
        weight_revision=manifest['revision'], seed=seed,
        fov_degrees=fov_degrees, resolution=1024, background=background), indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--fov', type=float, default=20.0)
    a = p.parse_args()
    generate(a.base, a.image, a.out, a.seed, a.fov)
