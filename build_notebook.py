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

if __name__ == '__main__':
    build(False)
    build(True)
    print('Built Drive-backed notebooks')
