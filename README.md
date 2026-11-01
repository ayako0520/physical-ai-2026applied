# PushT：Diffusion Policy の実行ステップ数（n_action_steps）比較

公開されている学習済み Diffusion Policy を PushT シミュレーションで評価し、
**予測した行動を何ステップ実行してから再計画するか**（`n_action_steps`）が、成功率と実行時間に与える影響を調べました。

- タスク：PushT（T字のブロックを押して目標位置に重ねる。目標との重なり95%以上で成功）
- モデル：[`lerobot/diffusion_pusht`](https://huggingface.co/lerobot/diffusion_pusht)（再学習なし、推論のみ）
- ライブラリ：[LeRobot](https://github.com/huggingface/lerobot) 0.6.1、[gym-pusht](https://github.com/huggingface/gym-pusht)
- 実行環境：Google Colab（T4 GPU、Python 3.13）
- 動画：https://youtu.be/WgepSBy8igU

## 結果

### 本実験（各30エピソード、シード1000）

| `n_action_steps` | 成功数 | 成功率 | 95%信頼区間 | 平均最大報酬 | 実行時間 |
|---|---|---|---|---|---|
| 15 | 17/30 | 56.7% | 39.2–72.6% | 0.953 | 222秒 |
| 12 | 17/30 | 56.7% | 39.2–72.6% | 0.940 | 267秒 |
| 8（既定） | 16/30 | 53.3% | 36.1–69.8% | 0.914 | 381秒 |
| 4 | 7/30 | 23.3% | 11.8–40.9% | 0.918 | 699秒 |
| 2 | 8/30 | 26.7% | 14.2–44.4% | 0.897 | 1341秒 |

### 補足実験（各100エピソード）

| `n_action_steps` | 成功数 | 成功率 | 95%信頼区間 | 実行時間 | 1成功あたりの時間 |
|---|---|---|---|---|---|
| 15 | 47/100 | 47.0% | 37.5–56.7% | 711秒 | 15.1秒 |
| 8 | 61/100 | 61.0% | 51.2–70.0% | 1223秒 | 20.0秒 |

### 主な結果

- `n_action_steps=4` は 8 より成功率が低い（7/30 vs 16/30、両側Fisher正確検定 p=0.033）。
- `n_action_steps=2` も低い傾向だが、有意ではない（8/30 vs 16/30、p=0.064）。
- 15 と 8 は、30エピソードでは差なし（p=1.000）。100エピソードでは 8 が高い傾向（47/100 vs 61/100、p=0.065）だが、有意ではない。
- 値を小さくするほど推論回数が増え、実行時間は長くなった（15 に対して 8 は約1.7倍、4 は約3.2倍）。

集計値は [`results/summary.csv`](results/summary.csv) にあります。

## 実行方法

1. `pusht_n_action_steps_experiment.ipynb` を Google Colab で開く。
2. ランタイムのタイプを「T4 GPU」にする。
3. 上から順に実行する（セル6・7の評価は合計約80分）。

## つまずいた点と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `ImportError: cannot import name 'FqnToConfig'` | Colab標準の `torchao` が古い | `pip install --upgrade torchao` |
| `Namespace gym_pusht not found` | 非同期の並列環境で、ワーカー内に環境が登録されない | `--eval.use_async_envs=false` |
| `policy_preprocessor.json` が見つからない | Hub上のモデルが旧形式 | 前処理だけを変換し、元の重みと組み合わせる（セル3・4） |

セル3の変換スクリプトは、最後に `Couldn't encode 84` のエラーで終了します。前処理・後処理のファイルは、その前に保存されているので問題ありません。

## 制限

- シードは1つのみ。拡散モデルのサンプリングノイズは条件ごとに異なるため、エピソード単位の厳密な対応比較ではありません。
- 本実験と補足実験は初期状態が重なっている可能性があるため、結果を合算していません。
- 動画は、各条件の最初の10エピソード分だけ保存されます（LeRobotの評価の既定動作）。

## ライセンス・出典

- 本リポジトリのコード：Apache License 2.0（[LICENSE](LICENSE)）
- 使用したライブラリとモデルは、いずれも Apache License 2.0 です（LeRobot、gym-pusht、`lerobot/diffusion_pusht`）。
- 参考文献：C. Chi et al., "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion," RSS 2023（arXiv:2303.04137）
