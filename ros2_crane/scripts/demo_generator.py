#!/usr/bin/env python3
"""CRANE+ V2 のデモ（お辞儀して閉じる→戻る→上で開く）を自動生成し、rosbag に記録する。

講座のキーボード操作（teleop_keyboard）と同じトピック・関節順・20Hz で指令を送るので、
講座の変換スクリプト（rosbag2lerobot.py）でそのまま LeRobotDataset に変換できる。

使い方（コンテナ内）:
    python3 demo_generator.py --episodes 30 --out ~/dataset/rosbags/bow_grip
"""
import argparse
import math
import os
import random
import signal
import subprocess
import time

import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

# 講座のテレオペと同じ関節順・値
ARM_JOINT_NAMES = ['crane_plus_joint1', 'crane_plus_joint2', 'crane_plus_joint4', 'crane_plus_joint3']
GRIPPER_JOINT_NAME = 'crane_plus_joint_hand'
GRIPPER_OPEN = -0.5236
GRIPPER_CLOSE = 0.1745
RATE = 20.0  # Hz
TOPICS = ['/joint_states', '/crane_plus_arm_controller/joint_trajectory', '/crane_plus_gripper_controller/joint_trajectory']


def smooth(t):
    """0→1 を滑らかにつなぐ（コサイン補間）"""
    t = min(max(t, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def make_plan(rng):
    """1エピソード分の動作計画：(継続時間, joint2の始点→終点, グリッパーの始点→終点) の列"""
    depth = rng.uniform(0.75, 0.85)       # お辞儀の深さ [rad]
    k = lambda base: base * rng.uniform(0.9, 1.1)  # 各段階の時間を ±10% ゆらす
    return [
        (k(0.5), (0.0, 0.0), (GRIPPER_OPEN, GRIPPER_OPEN)),      # 直立で待つ
        (k(1.5), (0.0, depth), (GRIPPER_OPEN, GRIPPER_OPEN)),    # ① お辞儀
        (k(0.8), (depth, depth), (GRIPPER_OPEN, GRIPPER_CLOSE)), # ② 下で閉じる
        (k(0.3), (depth, depth), (GRIPPER_CLOSE, GRIPPER_CLOSE)),
        (k(1.5), (depth, 0.0), (GRIPPER_CLOSE, GRIPPER_CLOSE)),  # ③ 閉じたまま戻る
        (k(0.8), (0.0, 0.0), (GRIPPER_CLOSE, GRIPPER_OPEN)),     # ④ 上で開く
        (k(0.5), (0.0, 0.0), (GRIPPER_OPEN, GRIPPER_OPEN)),      # 直立で待つ
    ]


class DemoPublisher(Node):
    def __init__(self):
        super().__init__('crane_plus_demo_generator')
        self.arm_pub = self.create_publisher(JointTrajectory, '/crane_plus_arm_controller/joint_trajectory', 10)
        self.gripper_pub = self.create_publisher(JointTrajectory, '/crane_plus_gripper_controller/joint_trajectory', 10)

    def send(self, j2, grip):
        # テレオペと同じく、目標位置を 0.1 秒後に到達する1点の軌道として送る
        jt = JointTrajectory()
        jt.joint_names = ARM_JOINT_NAMES
        pt = JointTrajectoryPoint()
        pt.positions = [0.0, float(j2), 0.0, 0.0]
        pt.time_from_start.nanosec = int(0.1 * 1e9)
        jt.points.append(pt)
        self.arm_pub.publish(jt)
        jg = JointTrajectory()
        jg.joint_names = [GRIPPER_JOINT_NAME]
        pg = JointTrajectoryPoint()
        pg.positions = [float(grip)]
        pg.time_from_start.nanosec = int(0.1 * 1e9)
        jg.points.append(pg)
        self.gripper_pub.publish(jg)

    def hold(self, j2, grip, seconds):
        for _ in range(int(seconds * RATE)):
            self.send(j2, grip)
            time.sleep(1.0 / RATE)

    def run_plan(self, plan):
        for dur, (a0, a1), (g0, g1) in plan:
            n = max(1, int(dur * RATE))
            for i in range(n):
                s = smooth((i + 1) / n)
                self.send(a0 + (a1 - a0) * s, g0 + (g1 - g0) * s)
                time.sleep(1.0 / RATE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--episodes', type=int, default=30)
    ap.add_argument('--out', default=os.path.expanduser('~/dataset/rosbags/bow_grip'))
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    rclpy.init()
    node = DemoPublisher()
    try:
        for ep in range(args.episodes):
            plan = make_plan(rng)
            node.hold(0.0, GRIPPER_OPEN, 2.5)  # 初期姿勢へ戻す（記録しない）
            bag = os.path.join(args.out, f'ep{ep}')
            rec = subprocess.Popen(['ros2', 'bag', 'record', '-o', bag] + TOPICS,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            node.hold(0.0, GRIPPER_OPEN, 2.0)  # 記録の立ち上がり待ち（直立のまま指令を送る）
            node.run_plan(plan)
            rec.send_signal(signal.SIGINT)
            rec.wait(timeout=20)
            print(f'ep{ep} 記録完了（お辞儀の深さ {plan[1][1][1]:.3f} rad）', flush=True)
    finally:
        node.hold(0.0, GRIPPER_OPEN, 1.0)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
