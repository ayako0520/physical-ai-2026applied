#!/usr/bin/env python3
"""記録した rosbag を LeRobotDataset に変換する。

講座の rosbag2lerobot.py の読み込み（_get_messages）と時刻合わせ（_sample_and_hold）をそのまま使い、
次の2点を変更した:
  1. 各エピソードの前後の「直立・開いたまま静止している区間」を取り除く
     （関節角だけを見る方策では、静止と動き出しを区別できず、「動かない」ことを学んでしまうため）
  2. 短いエピソードを最長に合わせて最後のフレームで水増しする処理をやめる（同じ理由）

使い方（コンテナ内、~/pai_training で）:
    pixi run python ~/work/scripts/convert_bow_grip.py --out ~/dataset/lerobot_dataset/crane_bow_grip_trim
"""
import argparse
import importlib.util
import os
import sys

import numpy as np
import torch

PAI = os.path.expanduser('~/pai_training')
spec = importlib.util.spec_from_file_location('rosbag2lerobot', os.path.join(PAI, 'scripts', 'rosbag2lerobot.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

OPEN = -0.5236
MARGIN = 2  # 動き出しの前・開き終わりの後に残すフレーム数


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bags', default=os.path.expanduser('~/dataset/rosbags/bow_grip'))
    ap.add_argument('--out', default=os.path.expanduser('~/dataset/lerobot_dataset/crane_bow_grip_trim'))
    ap.add_argument('--features', default=os.path.expanduser('~/work/configs/bow_grip_features.py'))
    ap.add_argument('--fps', type=int, default=20)
    args = ap.parse_args()
    if os.path.exists(args.out):
        sys.exit(f'出力先が既にあります（上書きしません）: {args.out}')

    conv = mod.RosbagToLeRobot(args.bags, args.out, args.features, target_freq=args.fps)
    lengths = []
    for ep_dir in conv.episode_dirs:
        m = conv._get_messages(ep_dir)
        js, arm, grip = m['/joint_states'], m['/crane_plus_arm_controller/joint_trajectory'], m['/crane_plus_gripper_controller/joint_trajectory']
        j_t = np.array([t for _, t in js]); j_p = np.array([msg.position for msg, _ in js])
        a_t = np.array([t for _, t in arm]); a_p = np.array([msg.points[0].positions for msg, _ in arm])
        g_t = np.array([t for _, t in grip]); g_p = np.array([msg.points[0].positions[0] for msg, _ in grip])
        start, end = max(j_t[0], a_t[0], g_t[0]), min(j_t[-1], a_t[-1], g_t[-1])
        n = int((end - start) * args.fps / 1e9)
        tt = np.linspace(start, end, n)
        state = conv._sample_and_hold(j_t, j_p, tt)
        action = np.hstack([conv._sample_and_hold(a_t, a_p, tt), conv._sample_and_hold(g_t, g_p, tt).reshape(-1, 1)])

        # 動き出し：joint2 の指令が 0 から離れた最初のフレーム
        moving = np.where(np.abs(action[:, 1]) > 0.005)[0]
        s = max(0, moving[0] - MARGIN)
        # 開き終わり：グリッパーを閉じた後、指令が「開」に戻った最初のフレーム
        closed = np.where(action[:, 4] > 0.0)[0]
        reopened = np.where((np.arange(n) > closed[-1]) & (action[:, 4] <= OPEN + 0.01))[0]
        e = min(n, (reopened[0] if len(reopened) else n - 1) + MARGIN + 1)
        for i in range(s, e):
            conv.dataset.add_frame({
                'observation.state': torch.tensor(state[i], dtype=torch.float32),
                'observation.environment_state': torch.tensor(state[i], dtype=torch.float32),
                'action': torch.tensor(action[i], dtype=torch.float32),
                'task': conv.task_name,
            })
        conv.dataset.save_episode()
        lengths.append(e - s)
        print(f'{ep_dir.name}: 全{n}フレーム → {s}〜{e} の {e - s} フレームを使用', flush=True)
    print(f'完了: {len(lengths)} エピソード、平均 {np.mean(lengths):.0f} フレーム → {args.out}')


if __name__ == '__main__':
    main()
