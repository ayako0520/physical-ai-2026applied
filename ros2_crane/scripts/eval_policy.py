#!/usr/bin/env python3
"""学習した ACT を Gazebo の CRANE+ V2 で動かし、実行ステップ数（n_action_steps）ごとに評価する。
講座の scripts/infer.py（Apache-2.0）の推論部分を元に、評価のループと判定を追加した。

判定（関節の実際の位置で順に確認する）:
  ① 開いたまま joint2 >= 0.6 まで下がる → ② その姿勢でグリッパーが閉じる（>= 0.0）
  → ③ 閉じたまま joint2 <= 0.15 まで戻る → ④ グリッパーが開く（<= -0.3）
  10 秒以内に ①〜④ をすべて満たせば成功。

使い方（コンテナ内、~/pai_training で、ROS 2 を source した状態）:
    pixi run python ~/work/scripts/eval_policy.py --model ~/work/checkpoints/crane_bow_grip_act \
        --steps 1 4 8 16 --trials 10
"""
import argparse
import csv
import json
import os
import random
import time

import numpy as np
import rclpy
import torch
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from lerobot.common.policies.act.modeling_act import ACTPolicy

ARM = ['crane_plus_joint1', 'crane_plus_joint2', 'crane_plus_joint4', 'crane_plus_joint3']
HAND = 'crane_plus_joint_hand'
OPEN, CLOSE = -0.5236, 0.1745
RATE = 20.0
EP_SEC = 10.0


class Robot(Node):
    def __init__(self):
        super().__init__('crane_plus_act_eval')
        self.arm_pub = self.create_publisher(JointTrajectory, '/crane_plus_arm_controller/joint_trajectory', 10)
        self.grip_pub = self.create_publisher(JointTrajectory, '/crane_plus_gripper_controller/joint_trajectory', 10)
        self.create_subscription(JointState, '/joint_states', self.on_state, 10)
        self.state = None

    def on_state(self, msg):
        d = dict(zip(msg.name, msg.position))
        self.state = np.array([d.get(j, 0.0) for j in ARM] + [d.get(HAND, 0.0)], dtype=np.float32)

    def send(self, a):
        for pub, names, pos in ((self.arm_pub, ARM, a[:4]), (self.grip_pub, [HAND], a[4:5])):
            jt = JointTrajectory()
            jt.joint_names = names
            pt = JointTrajectoryPoint()
            pt.positions = [float(x) for x in pos]
            pt.time_from_start.nanosec = int(0.1 * 1e9)
            jt.points.append(pt)
            pub.publish(jt)

    def wait(self, sec, action=None):
        end = time.time() + sec
        while time.time() < end:
            if action is not None:
                self.send(action)
            rclpy.spin_once(self, timeout_sec=1.0 / RATE)


def judge(states):
    """関節の位置の時系列から ①〜④ の達成時刻を求める"""
    phase, t_done = 0, None
    for i, s in enumerate(states):
        j2, g = s[1], s[4]
        if phase == 0 and j2 >= 0.6 and g <= -0.3:
            phase = 1
        elif phase == 1 and j2 >= 0.5 and g >= 0.0:
            phase = 2
        elif phase == 2 and j2 <= 0.15 and g >= 0.0:
            phase = 3
        elif phase == 3 and j2 <= 0.15 and g <= -0.3:
            phase, t_done = 4, i / RATE
            break
    return phase, t_done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--steps', type=int, nargs='+', default=[1, 4, 8, 16])
    ap.add_argument('--trials', type=int, default=10)
    ap.add_argument('--out', default=os.path.expanduser('~/work/eval'))
    ap.add_argument('--seed', type=int, default=1000)
    ap.add_argument('--mark', default=None, help='方策で動かし始めた瞬間に作るファイル（録画の開始合図）')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)

    policy = ACTPolicy.from_pretrained(os.path.expanduser(args.model)).eval()
    rclpy.init()
    robot = Robot()
    robot.wait(1.0)
    summary = []
    for n in args.steps:
        policy.config.n_action_steps = n
        for trial in range(args.trials):
            # 初期姿勢：直立・開いた状態に、毎回少しだけずれを加える（同じ条件の繰り返しを避ける）
            start = np.array([0.0, rng.uniform(-0.05, 0.05), 0.0, 0.0, OPEN + rng.uniform(-0.05, 0.05)], dtype=np.float32)
            robot.wait(3.0, start)
            policy.reset()  # 行動キューを空にし、実行ステップ数の設定を反映する
            if args.mark:
                open(os.path.expanduser(args.mark), 'w').close()
            states, actions, infer_ms = [], [], []
            t_next = time.time()
            for k in range(int(EP_SEC * RATE)):
                rclpy.spin_once(robot, timeout_sec=0.0)
                obs = torch.tensor(robot.state).unsqueeze(0)
                t0 = time.time()
                with torch.no_grad():
                    a = policy.select_action({'observation.state': obs, 'observation.environment_state': obs})
                infer_ms.append((time.time() - t0) * 1000)
                a = a.squeeze(0).numpy()
                robot.send(a)
                states.append(robot.state.copy())
                actions.append(a.copy())
                t_next += 1.0 / RATE
                while time.time() < t_next:
                    rclpy.spin_once(robot, timeout_sec=max(0.0, t_next - time.time()))
            states, actions = np.array(states), np.array(actions)
            phase, t_done = judge(states)
            # 滑らかさ：指令の2階差分（加速度に相当）の平均の大きさと、1ステップの最大の跳び
            jerk = float(np.abs(np.diff(actions[:, :4], n=2, axis=0)).mean())
            jump = float(np.abs(np.diff(actions[:, :4], axis=0)).max())
            row = {'n_action_steps': n, 'trial': trial, 'success': phase == 4, 'phase_reached': phase,
                   'time_to_complete': t_done, 'cmd_jerk': jerk, 'cmd_max_jump': jump,
                   'infer_calls': int(sum(1 for x in infer_ms if x > 1.0)), 'infer_ms_mean': float(np.mean(infer_ms))}
            summary.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            with open(os.path.join(args.out, f'traj_nas{n}_t{trial}.csv'), 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['t', 'j1', 'j2', 'j4', 'j3', 'grip', 'a1', 'a2', 'a4', 'a3', 'a_grip'])
                for i, (s, a) in enumerate(zip(states, actions)):
                    w.writerow([i / RATE] + [f'{x:.5f}' for x in s] + [f'{x:.5f}' for x in a])
    with open(os.path.join(args.out, 'summary.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    robot.wait(2.0, np.array([0, 0, 0, 0, OPEN], dtype=np.float32))
    robot.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
