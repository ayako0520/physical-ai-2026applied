#!/usr/bin/env bash
# 第5回講義資料の手順に沿って、テレオペ用パッケージと学習環境を準備する（WSLで実行）
# ログは work/setup.log に出力する
docker exec -u ubuntu pai_ros2 bash -lc '
set -e
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash

echo "== 1. テレオペ用パッケージ（physicalai_teleop）"
mkdir -p ~/pai_ws/src
cd ~/pai_ws/src
[ -d physicalai_teleop ] || git clone -q https://github.com/matsuolab/physicalai_teleop.git
cd ~/pai_ws
rosdep install --from-paths src --ignore-src -r -y >/dev/null 2>&1 || echo "rosdep: 一部失敗（続行）"
colcon build --symlink-install --packages-select physicalai_teleop 2>&1 | tail -3

echo "== 2. 学習環境（pai_training + pixi）"
cd ~
[ -d pai_training ] || git clone -q --recurse-submodules https://github.com/matsuolab/pai_training.git
command -v pixi >/dev/null || [ -x ~/.pixi/bin/pixi ] || (curl -fsSL https://pixi.sh/install.sh | bash >/dev/null 2>&1)
export PATH="$HOME/.pixi/bin:$PATH"
cd ~/pai_training
pixi install 2>&1 | tail -5
echo "== 完了"
df -h / | tail -1
' > "$(dirname "$0")/work/setup.log" 2>&1
echo "exit=$?" >> "$(dirname "$0")/work/setup.log"
tail -15 "$(dirname "$0")/work/setup.log"
