"""Colab orchestration. Source files stay in the mounted Drive project folder."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
import zipfile

REQUIRED = [
    'reference/setup_l4.py', 'reference/generate_mesh.py', 'reference/rig_mesh.py',
    'reference/viewer.html', 'tools/setup_transfer.py', 'tools/prepare_transfer.py',
    'integration/motionstudio-adapter.js', 'motions/taka-motion.json',
    'MOTIONS_LICENSE.md',
]

def check_project(root):
    root = Path(root).expanduser().resolve()
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError('PROJECT_DIRにコード一式を配置してください: ' + ', '.join(missing))
    reference = json.loads((root / 'motions/taka-motion.json').read_text())
    if reference.get('geometry_included') is not False:
        raise ValueError('メッシュを含まないTaka動作参照が必要です')
    return root


def create_job(root, work_dir='/content/motionstudio10/jobs'):
    job = Path(work_dir) / uuid.uuid4().hex[:12]
    job.mkdir(parents=True)
    sources = list((root / 'reference').glob('*.py')) + list((root / 'tools').glob('*.py'))
    sources += [root / 'motions/taka-motion.json', root / 'reference/viewer.html',
                root / 'integration/motionstudio-adapter.js']
    record = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sources}
    (job / 'source-record.json').write_text(json.dumps(record, indent=2))
    return job


def run_logged(command, log_path):
    command = list(map(str, command))
    log_path = Path(log_path)
    print('実行:', Path(command[1]).name if len(command) > 1 else command[0], flush=True)
    done = threading.Event()
    started = time.monotonic()
    def progress():
        while not done.wait(30):
            print('処理継続中:', round(time.monotonic() - started), '秒 /', log_path.name, flush=True)
    threading.Thread(target=progress, daemon=True).start()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True, env=env)
    try:
        with log_path.open('w') as log:
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
        if process.wait():
            raise RuntimeError('工程が停止しました。ログ: ' + str(log_path)
                               + '。別キャラや簡易動作では代用していません。')
    finally:
        done.set()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)


def read_input(path):
    if str(path).strip():
        source = Path(path).expanduser()
        return source.name, source.read_bytes()
    from google.colab import files
    uploaded = files.upload()
    if len(uploaded) != 1:
        raise ValueError('入力ファイルを1つ選んでください')
    return next(iter(uploaded.items()))


def prepare_image(path, job):
    import io
    from PIL import Image, ImageOps
    name, data = read_input(path)
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGBA')
    destination = job / 'input.png'
    image.save(destination)
    (job / 'input-record.json').write_text(json.dumps(dict(
        filename=Path(name).name, original_sha256=hashlib.sha256(data).hexdigest(),
        prepared_sha256=hashlib.sha256(destination.read_bytes()).hexdigest()),
        ensure_ascii=False, indent=2))
    return destination


def prepare_rig(path, job):
    import io
    name, data = read_input(path)
    if name.lower().endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            candidates = [n for n in archive.namelist() if Path(n).name == 'rigged.glb']
            if not candidates:
                candidates = [n for n in archive.namelist() if Path(n).name == 'character.glb']
            if len(candidates) != 1:
                raise ValueError('対象のリグ付きGLBを1つに絞れません')
            data = archive.read(candidates[0])
    if data[:4] != b'glTF':
        raise ValueError('GLB形式ではありません')
    destination = job / 'rigged.glb'
    destination.write_bytes(data)
    print('入力SHA-256:', hashlib.sha256(data).hexdigest())
    return destination


def prepare_web(root, transfer, job):
    result = json.loads((transfer / 'result.json').read_text())
    character = transfer / 'character'
    if hashlib.sha256((character / 'character.glb').read_bytes()).hexdigest() != result['model_sha256']:
        raise ValueError('今回のモデルと表示対象が一致しません')
    web = job / 'web'
    web.mkdir(exist_ok=True)
    for name in ['character.glb', 'character.json', 'validation-report.json']:
        shutil.copy2(character / name, web / name)
    shutil.copy2(root / 'reference/viewer.html', web / 'index.html')
    shutil.copy2(root / 'integration/motionstudio-adapter.js', web / 'motionstudio-adapter.js')
    print('状態:', result['status'])
    print('Taka動作SHA-256:', result['motion_sha256'])
    return web


def serve_web(web):
    from functools import partial
    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
    server = ThreadingHTTPServer(('0.0.0.0', 0),
        partial(SimpleHTTPRequestHandler, directory=str(web)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def save_result(root, transfer, job):
    character = transfer / 'character'
    destination = root / 'outputs' / job.name
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / 'character-taka-result.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        paths = list(character.glob('*.json')) + [character / 'character.glb', root / 'MOTIONS_LICENSE.md']
        paths += list(job.glob('*.log')) + list(job.glob('*-record.json'))
        for path in paths:
            if path.is_file():
                archive.write(path, path.name)
    print('Driveへ保存しました:', archive_path)
    return archive_path
