#!/usr/bin/env bash
# Gazebo の画面のカメラを、ロボットを斜め前から写す位置へ動かし、確認用に撮影する（WSLで実行）
docker exec -u ubuntu pai_ros2 bash -lc '
export DISPLAY=:0
echo "== GUIのサービス"; ign service -l 2>/dev/null | grep -i -E "move_to|camera" | head
# 横（-y側）・やや上から、机の上のロボット（土台の高さ1.015m、中心は約1.15m）を見る
ign service -s /gui/move_to/pose --reqtype ignition.msgs.GUICamera --reptype ignition.msgs.Boolean --timeout 3000 \
  --req "pose: {position: {x: 0.05, y: -0.42, z: 1.25}, orientation: {x: -0.0825, y: 0.0825, z: 0.7023, w: 0.7023}}" 2>&1 | tail -2
sleep 3
import -window 0x3600012 ~/work/video/gazebo_cam.png && echo saved
'
