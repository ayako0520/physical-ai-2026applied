# 発展実験：ロボットアーム CRANE+ V2（ROS 2 + Gazebo + ACT）

PushT の実験と同じ「実行ステップ数（`n_action_steps`）」の比較を、Gazebo 上のロボットアーム CRANE+ V2 で行いました。
デモをプログラムで自動生成し、ACT を CPU で学習して、実行ステップ数 1・4・8・16 を各10回評価しています。

## タスク

お辞儀して下でグリッパーを閉じる → 閉じたまま戻る → 上で開く。

方策は関節角（5つ）しか見ないため、グリッパーの開閉で各段階を区別できる順番にしています。

## 結果（各10回）

| 実行ステップ数 | 成功 | 完了時間（平均） | 動き出しまで | 指令の滑らかさ※ | 推論時間（1ステップ平均） |
|---|---|---|---|---|---|
| 1 | 10/10 | 7.00秒 | 0.63秒 | 0.0012 | 16.5ms |
| 4 | 9/10 | 6.36秒 | 0.49秒 | 0.0025 | 5.0ms |
| 8 | 10/10 | 6.38秒 | 0.20秒 | 0.0023 | 2.5ms |
| 16 | 10/10 | 5.75秒 | 0.14秒 | 0.0020 | 1.7ms |

※ 関節指令の2階差分の平均の大きさ（小さいほど滑らか）。各回の結果は [`results/eval_summary.csv`](results/eval_summary.csv)。

- PushT と違い、実行ステップ数を小さくしても成功率は下がりませんでした。
- 大きいほど完了が早い傾向がありましたが、10回では有意ではありません（N=1 と N=16 で Welch の t 検定 p=0.16）。
- N=1 は指令が最も滑らかな一方、推論を毎回行うため計算量は N=16 の約10倍でした。

## 構成

| ファイル | 役割 |
|---|---|
| `docker/start_container.sh` | 講座の演習用 Docker イメージ（ROS 2 Humble・Gazebo・CRANE+）を起動。成果物は `docker/work/` に保存 |
| `docker/setup_in_container.sh` | 講座のテレオペ用パッケージと学習環境（pixi）を準備 |
| `scripts/demo_generator.py` | デモを自動生成し rosbag に記録（講座のテレオペと同じトピック・20Hz） |
| `scripts/convert_bow_grip.py` | rosbag を LeRobotDataset に変換（前後の静止区間を除く） |
| `configs/train_bow_grip.yaml` | 学習設定（予測を 20Hz の刻みにそろえる、3000ステップ） |
| `scripts/train_act.py` | ACT の学習 |
| `scripts/eval_policy.py` | 実行ステップ数ごとに Gazebo で評価し、成功・時間・滑らかさを記録 |
| `docker/set_camera.sh`、`docker/record_run.sh` | 動画用のカメラ設定と録画 |

## 実行手順

前提：Docker が使える Linux（WSL2 可）。講座のイメージは約25GB、学習環境は約9GBを使います。GPU は不要です。

```bash
bash docker/start_container.sh          # デスクトップは http://localhost:6080/
bash docker/setup_in_container.sh
# 以降はコンテナ内（ユーザー ubuntu）で実行。スクリプトは ~/work/scripts/ にコピーしておく
ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py &   # DISPLAY=:0
python3 ~/work/scripts/demo_generator.py --episodes 30
cd ~/pai_training
pixi run python ~/work/scripts/convert_bow_grip.py
WANDB_MODE=disabled pixi run python ~/work/scripts/train_act.py --config ~/work/configs/train_bow_grip.yaml
pixi run python ~/work/scripts/eval_policy.py --model ~/work/checkpoints/crane_bow_grip_act_trim --steps 1 4 8 16 --trials 10
```

WSL2 では、Windows 側から接続しているプロセスがなくなると WSL が止まり、コンテナも終了します。作業中は `wsl -d Ubuntu -- sleep infinity` などを別に起動しておいてください。

## 講座の設定から変えた点

1. 予測16ステップの時間間隔を、推論の周期（20Hz）にそろえた（講座は 0.1 秒刻み）。
2. デモの前後の静止区間を除き、短いエピソードの水増しをやめた（静止と動き出しを区別できず、方策が動かなくなったため）。
3. 学習量を 200 から 3000 ステップへ増やした。

## 出典・ライセンス

- 講座の演習用リポジトリ [`pai_training`](https://github.com/matsuolab/pai_training)・[`physicalai_teleop`](https://github.com/matsuolab/physicalai_teleop)（東京大学 松尾・岩澤研究室）。`scripts/train_act.py` は `pai_training` の `train.py`（ファイルに Apache License 2.0 と記載）を元に変更しました。`scripts/convert_bow_grip.py` は同リポジトリの変換クラスを実行時に読み込んで使います。
- [CRANE+ V2 ROS 2 パッケージ](https://github.com/rt-net/crane_plus)（RT Corporation）：Apache License 2.0
- ACT：T. Z. Zhao et al., "Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware," RSS 2023
