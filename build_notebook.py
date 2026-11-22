"""Build thin Colab entry points that execute the source tree on mounted Drive."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parent

MOUNT = '''from google.colab import drive, output
from pathlib import Path
import sys

drive.mount('/content/drive')
PROJECT_DIR = '/content/drive/MyDrive/Colab Notebooks/GameCreation/MotionStudio/10_ImageToCharacter' #@param {type:'string'}
ROOT = Path(PROJECT_DIR).expanduser()
if not (ROOT / 'tools/colab_runtime.py').is_file():
    raise FileNotFoundError('GitHubのコード一式があるフォルダーをPROJECT_DIRに指定してください。')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'tools'))
import importlib, colab_runtime
importlib.reload(colab_runtime)
from colab_runtime import (
    check_project, create_job, run_logged,
    prepare_image, prepare_rig, prepare_web, serve_web, save_result,
)
ROOT = check_project(ROOT)
JOB = create_job(ROOT)
print('コードの読み込み先:', ROOT)
print('今回の作業先:', JOB)
'''
VIEW = '''WEB = prepare_web(ROOT, TRANSFER, JOB)
if 'AVATAR_SERVER' in globals():
    AVATAR_SERVER.shutdown()
    AVATAR_SERVER.server_close()
AVATAR_SERVER = serve_web(WEB)
output.serve_kernel_port_as_iframe(
    AVATAR_SERVER.server_address[1], height=850, cache_in_notebook=False,
)
'''

def build(existing):
    cells = []
    def md(text):
        cells.append(dict(cell_type='markdown', metadata={}, source=text.splitlines(True)))
    def code(text):
        cells.append(dict(cell_type='code', metadata={}, source=text.splitlines(True),
                          outputs=[], execution_count=None))
    md('# ' + ('生成済みキャラへTakaの動作を移す' if existing else '画像から3Dキャラを作り、Takaの動作で操作する') + '''

GitHubのコード一式をGoogle Driveへ配置し、このNotebookから読み込んで実行します。
Notebook内にソースコードや動作データを埋め込まず、教材ZIPのアップロードも行いません。
Takaの調整済み5動作を使用します。たかにゃんの画像やモデルは含みません。

''' + ('生成済みリグへの移植はCPUで実行できます。' if existing else '画像からの生成はColabのL4 GPUを選択してください。生成API料金は不要ですがColabの計算資源は別です。'))
    md('''## 1. Google Driveからコードを読み込む

事前に、GitHubのコード一式（tools、reference、motions、integrationなど）をDriveのプロジェクトフォルダーへ配置してください。
PROJECT_DIRは、そのフォルダーを指定します。共有ドライブ内のパスも指定できます。
''')
    code(MOUNT)
    md('## 2. 実行環境を準備する\n\n環境と重みはColabの一時領域へ置き、Drive上のソースは変更しません。')
    environment = 'transfer-engine' if existing else 'l4-engine'
    script = 'tools/setup_transfer.py' if existing else 'reference/setup_l4.py'
    code(f'''ENGINE = Path('/content/motionstudio10/{environment}')
run_logged([sys.executable, ROOT / '{script}', '--base', ENGINE], JOB / 'setup.log')
PYTHON = ENGINE / 'venv/bin/python'
''')
    if existing:
        md('''## 3. 生成済みのリグを選ぶ

Drive上のGLBまたは結果ZIPのパスを指定します。空欄ならファイル選択画面を開きます。
''')
        code("RIG_PATH = '' #@param {type:'string'}\nRIGGED = prepare_rig(RIG_PATH, JOB)\n")
    else:
        md('''## 3. 入力画像を選ぶ

Drive上の画像パスを指定します。空欄ならファイル選択画面を開きます。
全身、正面、両腕が胴体から離れた二足キャラクターのA/Tポーズを推奨します。
''')
        code("IMAGE_PATH = '' #@param {type:'string'}\nIMAGE = prepare_image(IMAGE_PATH, JOB)\nfrom IPython.display import display, Image\ndisplay(Image(filename=str(IMAGE)))\n")
        md('## 4. メッシュとリグを生成する')
        code('''FRONT_YAW = -90.0 #@param {type:'number'}
MESH = JOB / 'mesh.glb'
RIGGED = JOB / 'rigged.glb'
run_logged([PYTHON, ROOT / 'reference/generate_mesh.py', '--engine', ENGINE,
            '--image', IMAGE, '--out', MESH, '--front-yaw', FRONT_YAW], JOB / 'mesh.log')
run_logged([PYTHON, ROOT / 'reference/rig_mesh.py', '--engine', ENGINE,
            '--mesh', MESH, '--out', RIGGED, '--seed', 1011], JOB / 'rig.log')
''')
    md('## Takaの調整済み動作を移す\n\n全体振幅は1.0を保ち、足首の初期向きと関節周辺の変形、接地を補正します。失敗を簡易動作や別キャラで代用しません。')
    code('''TRANSFER = JOB / 'transfer'
run_logged([PYTHON, ROOT / 'tools/prepare_transfer.py',
            '--source', RIGGED, '--out', TRANSFER], JOB / 'transfer.log')
''')
    md('## 動作を確認する\n\n歩行、走行、ジャンプを正面、横、背面から確認します。検査警告がある場合は見た目も確認してください。')
    code(VIEW)
    md('## 結果をGoogle Driveへ保存する\n\nPROJECT_DIR/outputs/実行ID/へGLB、診断JSON、ログを含む結果ZIPを保存します。')
    code('ARCHIVE = save_result(ROOT, TRANSFER, JOB)\n')
    md('## PCへもダウンロードする（任意）')
    code('from google.colab import files\nfiles.download(ARCHIVE)\n')
    for i, cell in enumerate(cells):
        cell['id'] = f'cell-{i:02}'
    notebook = dict(cells=cells, metadata={
        'colab': {'gpuType': 'L4'} if not existing else {},
        'kernelspec': {'name': 'python3', 'display_name': 'Python 3'},
        'language_info': {'name': 'python'},
        **({'accelerator': 'GPU'} if not existing else {}),
    }, nbformat=4, nbformat_minor=5)
    name = '02_Existing_Rig_to_Taka_Motion.ipynb' if existing else '01_Image_to_Taka_Motion_L4.ipynb'
    (ROOT / name).write_text(json.dumps(notebook, ensure_ascii=False, indent=2))

def build_pixal3d():
    import textwrap
    cells = []

    def cell(kind, content):
        item = dict(cell_type=kind, id=f'cell-{len(cells):02}', metadata={},
                    source=textwrap.dedent(content).strip().splitlines(True))
        if kind == 'code':
            item.update(outputs=[], execution_count=None)
        cells.append(item)

    cell('markdown', '''
    # 03 画像からPixal3Dで3D化して色を補正する

    ColabのL4 GPUを選びます。入力はPNGまたはJPEGの画像1枚です。
    背景があればBiRefNet-liteで切り抜き、Pixal3Dで静的な3Dモデルを生成します。
    保存されたカメラ情報を使って元画像の色を投影し、画像で裏づけられない明るい線を補正します。
    最終出力の `model.refined.glb` を04でリグ付けできます。
    GitHubのソース一式を事前にGoogle Driveへ配置してください。
    ''')
    cell('code', '''
    from google.colab import drive
    from pathlib import Path
    import sys

    drive.mount('/content/drive')
    PROJECT_DIR = '/content/drive/MyDrive/Colab Notebooks/GameCreation/MotionStudio/10_ImageToCharacter' #@param {type:'string'}
    ROOT = Path(PROJECT_DIR).expanduser().resolve()
    if not (ROOT / 'tools/pixal3d_generate.py').is_file():
        raise FileNotFoundError('最新版のソース一式があるDriveフォルダーを指定してください。')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / 'tools'))
    from colab_runtime import read_input, run_logged
    ''')
    cell('markdown', '''
    ## 画像と生成条件を指定する

    Drive上のパスを指定します。空欄ならファイル選択画面を開きます。
    初回はCUDA版のビルドと約8GBの重みの取得があり、その後にGPU生成とCPU補正が続きます。
    同じランタイム内では確認済みのビルドと重みを再利用します。
    ''')
    cell('code', '''
    from uuid import uuid4

    IMAGE_PATH = '' #@param {type:'string'}
    SEED = 42 #@param {type:'integer'}
    FOV_DEGREES = 20.0 #@param {type:'number'}

    ENGINE = Path('/content/image-to-playable-pixal3d')
    JOB = ENGINE / 'runs' / uuid4().hex[:12]
    JOB.mkdir(parents=True)
    _, payload = read_input(IMAGE_PATH)
    SOURCE = JOB / 'source-image'
    SOURCE.write_bytes(payload)
    ''')
    cell('code', '''
    import shutil
    import subprocess


    uv_path = shutil.which('uv')
    if uv_path is None:
        bootstrap = ENGINE / 'uv-bootstrap'
        run_logged([sys.executable, '-m', 'pip', 'install', '--target', bootstrap,
                    'uv==0.9.5'], JOB / 'uv-bootstrap.log')
        uv_path = str(bootstrap / 'bin/uv')

    VENV = ENGINE / 'venv-uv'
    PYTHON = VENV / 'bin/python'
    if not PYTHON.is_file():
        run_logged([uv_path, 'venv', '--python', sys.executable, VENV],
                   JOB / 'venv.log')

    run_logged([uv_path, 'pip', 'install', '--python', PYTHON,
                'numpy==2.2.6', 'scipy==1.16.2', 'pillow==11.3.0',
                'opencv-python-headless==4.12.0.88', 'onnxruntime==1.30.0'],
               JOB / 'dependencies.log')
    run_logged([PYTHON, '-c', 'import numpy, scipy, PIL, cv2, onnxruntime'],
               JOB / 'imports.log')
    ''')
    cell('code', '''
    GENERATED = JOB / 'generated'
    run_logged([PYTHON, ROOT / 'tools/pixal3d_generate.py', '--base', ENGINE,
                '--image', SOURCE, '--out', GENERATED, '--seed', SEED,
                '--fov', FOV_DEGREES], JOB / 'generation.log')
    ''')
    cell('code', '''
    import os

    RESULT = JOB / 'refined'
    subprocess.run([str(PYTHON), '-m', 'pixal3d_refine',
                    '--model', str(GENERATED / 'model.glb'),
                    '--views', str(GENERATED / 'model.svviews'),
                    '--output', str(RESULT)], check=True, env={
        **os.environ, 'PYTHONPATH': str(ROOT / 'tools'), 'PYTHONDONTWRITEBYTECODE': '1',
        'OPENBLAS_NUM_THREADS': '2', 'OMP_NUM_THREADS': '2',
    })
    ''')
    cell('code', '''
    from IPython.display import Image, display

    for name in ('00_projection.jpg', '01_colour.jpg'):
        display(Image(filename=str(RESULT / name)))
    ''')
    cell('code', '''
    import shutil

    destination = ROOT / 'outputs' / ('pixal3d-' + JOB.name)
    shutil.copytree(RESULT, destination)
    for name in ('model.glb', 'input.png', 'generation.json'):
        shutil.copy2(GENERATED / name, destination / name)
    shutil.copytree(GENERATED / 'model.svviews', destination / 'model.svviews')
    for path in JOB.glob('*.log'):
        shutil.copy2(path, destination / path.name)
    print('04に渡すファイル:', destination / 'model.refined.glb')
    ''')
    notebook = dict(cells=cells, metadata={'colab': {'gpuType':'L4'}, 'accelerator':'GPU',
        'kernelspec': {'name': 'python3', 'display_name': 'Python 3'},
        'language_info': {'name': 'python'}}, nbformat=4, nbformat_minor=5)
    (ROOT / '03_Pixal3D_Mesh_Refinement.ipynb').write_text(
        json.dumps(notebook, ensure_ascii=False, indent=2) + '\n')





def build_tokenrig_single():
    import textwrap
    cells = []

    def cell(kind, source):
        item = dict(cell_type=kind, id=f'cell-{len(cells):02}', metadata={},
                    source=textwrap.dedent(source).strip().splitlines(True))
        if kind == 'code':
            item.update(outputs=[], execution_count=None)
        cells.append(item)

    cell('markdown', '''
    # 04 指定したGLBにTokenRigで骨を入れ、Takaの動作を移す

    ColabのL4 GPUを選びます。入力はリグ付け前の静的GLB 1本です。
    01と同じ設定のTokenRigで骨を入れ、02と同じTakaの5動作を移します。
    ''')
    cell('code', MOUNT + '''
required_04 = ('tools/rig_to_taka.py', 'tools/orient_pixal_input.py',
               'tools/pixal3d_refine/photo_paint.py')
missing_04 = [name for name in required_04 if not (ROOT / name).is_file()]
if missing_04:
    raise FileNotFoundError('04のソースが不足しています。最新版ソースZIPをDriveに展開してください: '
                            + ', '.join(missing_04))
''')
    cell('code', '''
    ENGINE = Path('/content/motionstudio10/tokenrig-engine')
    run_logged([sys.executable, ROOT / 'reference/setup_l4.py', '--base', ENGINE,
                '--rig-only'], JOB / 'setup.log')
    ''')
    cell('markdown', '''
    ## GLBを1本指定する

    Drive上のパスを `GLB_PATH` に設定します。
    03の `model.refined.glb` なら `FROM_PIXAL3D_03` をオンにします。
    他のツールで作った正面が+ZのGLBはオフにします。
    向きや変形は、出力されたビューアで確認してください。
    ''')
    cell('code', '''
    from rig_to_taka import run_case

    GLB_PATH = '' #@param {type:'string'}
    FROM_PIXAL3D_03 = True #@param {type:'boolean'}
    if not GLB_PATH.strip():
        raise ValueError('処理する静的GLBを1本指定してください。')
    JOB = create_job(ROOT)
    TRANSFER = run_case(ROOT, ENGINE, Path(GLB_PATH).expanduser(), JOB, FROM_PIXAL3D_03)
    ARCHIVE = save_result(ROOT, TRANSFER, JOB)
    ''')
    cell('code', VIEW)
    notebook = dict(cells=cells, metadata={'colab': {'gpuType':'L4'}, 'accelerator':'GPU',
        'kernelspec': {'name':'python3','display_name':'Python 3'},
        'language_info': {'name':'python'}}, nbformat=4, nbformat_minor=5)
    (ROOT / '04_GLB_to_Taka_Motion.ipynb').write_text(
        json.dumps(notebook, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__':
    build(False)
    build(True)
    build_pixal3d()
    build_tokenrig_single()
    print('Built Drive-backed notebooks')
