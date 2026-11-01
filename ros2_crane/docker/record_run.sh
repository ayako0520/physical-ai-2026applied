#!/usr/bin/env bash
# 学習した方策で1回動かしながら、Gazebo の3D表示部分を連続撮影して動画にする（WSLで実行）
# 事前に set_camera.sh でカメラを横からの視点にしておく
# 使い方: bash record_run.sh <n_action_steps>
N=${1:-1}
docker exec -u ubuntu pai_ros2 bash -lc "
source /opt/ros/humble/setup.bash; source ~/airobot_ws/install/setup.bash
export PATH=\"\$HOME/.pixi/bin:\$PATH\" DISPLAY=:0
FF=~/pai_training/.pixi/envs/default/bin/ffmpeg
OUT=~/work/video/nas$N; rm -rf \$OUT; mkdir -p \$OUT/frames
# Gazebo のウィンドウを探す
WIN=\$(xwininfo -root -tree | grep '(\"ign-gazebo-gui\"' | head -1 | awk '{print \$1}')
echo \"window=\$WIN\"
cd ~/pai_training
pixi run python ~/work/scripts/eval_policy.py --model ~/work/checkpoints/crane_bow_grip_act_trim --steps $N --trials 1 --seed 7 --out \$OUT/eval --mark \$OUT/start.mark > \$OUT/eval.log 2>&1 &
# 評価プログラムが動かし始めた合図（start.mark）を待ってから撮影を始める
until [ -f \$OUT/start.mark ]; do sleep 0.05; done
T0=\$(date +%s.%N); i=0
while [ \$(echo \"\$(date +%s.%N) - \$T0 < 10.5\" | bc) -eq 1 ]; do
  import -window \$WIN \$OUT/frames/\$(printf %05d \$i).png 2>/dev/null; i=\$((i+1))
done
T1=\$(date +%s.%N); wait
FPS=\$(echo \"scale=2; \$i / (\$T1 - \$T0)\" | bc)
echo \"frames=\$i fps=\$FPS\"
\$FF -hide_banner -loglevel error -y -framerate \$FPS -i \$OUT/frames/%05d.png -vf 'crop=582:680:0:100,scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30' -pix_fmt yuv420p \$OUT/run_nas$N.mp4
tail -1 \$OUT/eval.log
ls -la \$OUT/run_nas$N.mp4
"
