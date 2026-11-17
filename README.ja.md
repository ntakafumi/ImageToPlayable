# 画像から3Dキャラクターを作り、Takaの動作で操作する

[English](README.md)

1枚の二足歩行キャラクター画像から3Dメッシュとリグを作り、既存のTakaの調整済み動作を移して、ブラウザーで操作するGoogle Colab教材です。
TRELLIS、SkinTokens / TokenRig、Three.jsを利用します。

## 収録する動作

待機、歩行、軽い走り、走行、ジャンプの5動作を収録しています。
Takaのゲームで実行した各フレームの骨の方向と胴体の姿勢、速度情報、ジャンプ軌道を `motions/taka-motion.json` に保存しています。
Takaのメッシュやテクスチャは含みません。
簡易的なサイン波の歩行に置き換えず、各キャラの骨格へ移植します。
全体振幅は1.0を保ち、足首の初期向き、関節周辺のウェイトと局所変形、床との接地を補正します。
体型が異なるため、足先の位置までTakaと完全に一致するわけではありません。

## 最初に開くNotebook

| Notebook | 用途 | 環境 |
| --- | --- | --- |
| `01_Image_to_Taka_Motion_L4.ipynb` | 画像から生成、リギング、Taka動作の移植、操作まで | Colab L4 GPU |
| `02_Existing_Rig_to_Taka_Motion.ipynb` | 保存済みのリグ付きGLBへTaka動作を移す | Colab CPUで実行可能 |

## Google Driveへの配置

GitHubのコード一式を、Google Driveの次のフォルダーへ配置します。
ダウンロードZIPを使う場合は、事前に解凍してフォルダーを置いてください。
Colabで教材ZIPをアップロードしたり、Notebookからソースを生成したりする必要はありません。

```text
マイドライブ/Colab Notebooks/GameCreation/MotionStudio/10_ImageToCharacter/
├── 01_Image_to_Taka_Motion_L4.ipynb
├── 02_Existing_Rig_to_Taka_Motion.ipynb
├── reference/
├── tools/
├── motions/taka-motion.json
├── integration/
├── MOTIONS_LICENSE.md
└── README.ja.md
```

Notebookだけを別の場所で開くこともできますが、参照するコード一式はDriveへ配置してください。

## 実行手順

1. Drive内のNotebookをGoogle Colabで開きます。
2. 01の場合はGPUのL4を選びます。02はGPU不要です。
3. 最初のセルでDriveをマウントし、`PROJECT_DIR` にコード一式のあるフォルダーを指定します。
4. セルを順番に実行し、専用環境を準備します。
5. `IMAGE_PATH` または `RIG_PATH` にDrive上の入力ファイルを指定します。空欄ならファイル選択画面が開きます。
6. 動作移植と表示のセルを実行し、各方向から確認します。
7. 保存セルでDriveの `outputs/実行ID/` へ結果ZIPを保存します。PCへのダウンロードは任意です。

標準の `PROJECT_DIR` は次の場所です。共有ドライブなど別の配置先も指定できます。

```python
PROJECT_DIR = '/content/drive/MyDrive/Colab Notebooks/GameCreation/MotionStudio/10_ImageToCharacter'
```

ソースと動作参照はDriveから直接読み込みます。
環境、モデル重み、途中結果、表示用ファイルはColabの一時領域へ置き、Drive上のソースは書き換えません。
モデル重みは公式配布元から取得し、有料の生成APIは使いません。Colabの計算資源は別途料金がかかる場合があります。

## 操作

| 入力 | 動作 |
| --- | --- |
| WASD | 歩いて移動 |
| Shift＋WASD | 走って移動 |
| Space | ジャンプ |
| マウスドラッグ／ホイール | 視点の回転／ズーム |
| 各動作ボタン | その場で再生 |
| 正面／横／背面 | カメラの切り替え |
| 一時停止とスライダー | 特定の姿勢を確認 |
| 録画 | 歩行→走行→ジャンプのWebMまたはMP4を保存（ブラウザー依存） |

ジャンプの上下移動はGLBに記録済みで、ビューアーでは二重に加算しません。
変形検査の警告は診断JSONに残します。
移植に失敗した場合に、保存済みの別キャラや簡易動作で代用する処理はありません。

## 入力画像と限界

全身、正面、両腕が胴体から離れたA/Tポーズを推奨します。
利用と変換の権限がある画像を入力してください。
見えない背面や厚みは推定されます。
推定骨格、短い手足、複雑な服装によっては、関節の潰れ、足滑り、めり込みが残る場合があります。
方向一致の検査に通っても、見た目の品質や衝突がないことを保証するものではありません。

## ソース構成

- `reference/`：L4環境、TRELLIS生成、TokenRig、操作画面
- `tools/colab_runtime.py`：Notebookから呼び出す入力、実行、表示、保存処理
- `tools/`：骨格の対応、Taka動作の移植、足首と局所変形の補正、検査
- `motions/taka-motion.json`：メッシュを含まないTakaの動作参照データ
- `build_notebook.py`：Notebookの生成
- `check_release.py`：構文と配布物の検査

## ライセンス

独自の教材コードは [MIT License](LICENSE)、収録動作データは [MOTIONS_LICENSE.md](MOTIONS_LICENSE.md)に従います。
依存ライブラリとモデル重みはそれぞれの条件に従います。配布元は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。
記事に登場する、たかにゃんとTakaの画像、モデル、テクスチャ、ゲーム背景は同梱していません。

## 関連記事

Takaは制作者の3Dゲームのキャラクターで、骨格とスキニング、基本動作を用意しています。
生成された動作をTakaへ移す例は[「文章で人間を踊らせるKimodoをColabで試す」](https://zenn.dev/nakanishitf/articles/86ee54b68edee8)で紹介しています。

## 確認した環境

Colab L4上で、画像からのメッシュ生成、リギング、5動作の移植、動作付きGLB出力まで実行しました。
保存済みリグからの再開経路と、ブラウザーでの5動作の読み込み、視点切り替え、一時停止による姿勢確認も確認しています。
動作データは以前の10N実験で使用した参照と同一です。
検証した例でも関節変形の警告は残っています。詳しくは [VALIDATION.md](VALIDATION.md) を参照してください。
