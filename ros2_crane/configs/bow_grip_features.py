# CRANE+ V2「お辞儀して閉じる→戻る→上で開く」用の特徴量定義
# 講座の configs/crane_features.py と同じ形式（関節5つ：アーム4軸＋グリッパー）
features = {
    "observation.state": {
        "dtype": "float32",
        "shape": (5,),
        "names": ["joint1", "joint2", "joint4", "joint3", "gripper"],
    },
    "observation.environment_state": {
        "dtype": "float32",
        "shape": (5,),
        "names": ["joint1", "joint2", "joint4", "joint3", "gripper"],
    },
    "action": {
        "dtype": "float32",
        "shape": (5,),
        "names": ["joint1", "joint2", "joint4", "joint3", "gripper"],
    },
}
# 変換で使う設定
robot_type = "crane_plus"
repo_id = "crane_bow_grip"
root = "/home/ubuntu/dataset/lerobot_dataset/crane_bow_grip"
task_name = "bow_grip"
