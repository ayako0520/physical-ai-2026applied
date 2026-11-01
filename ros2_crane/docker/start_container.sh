#!/usr/bin/env bash
# 講座の ROS 2 デスクトップ環境（Docker）を起動する。WSL の Ubuntu で実行する
# ブラウザで http://localhost:6080/ を開くとデスクトップが表示される
set -eu

NAME=pai_ros2
IMAGE=airobotbook/ros2-desktop-ai-robot-book-humble
# 成果物は Windows 側のこのフォルダの work/ に保存する（環境を消しても残る）
WORK="$(cd "$(dirname "$0")" && pwd)/work"
mkdir -p "$WORK"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  docker start "$NAME" >/dev/null
  echo "既存のコンテナ $NAME を起動しました"
else
  # ポートとオプションは第5回講義資料のコンテナ起動例に合わせる
  docker run -d \
    --name "$NAME" \
    -e RESOLUTION=1920x1080 \
    -p 15900:5900 \
    -p 13389:3389 \
    -p 9090:9090 \
    -p 9876:9876 \
    -p 6080:80 \
    --shm-size=512m \
    --privileged \
    -v "$WORK":/home/ubuntu/work \
    "$IMAGE" >/dev/null
  echo "コンテナ $NAME を作成して起動しました"
fi
echo "デスクトップ: http://localhost:6080/"
