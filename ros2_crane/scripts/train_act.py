#!/usr/bin/env python3
"""ACT を学習する。講座の scripts/train.py（Apache-2.0, Tatsuya Kamijo / HuggingFace）を元に、
設定ファイルを引数で指定できるようにし、wandb を使わずにログをファイルへ残すよう変更した。

使い方（コンテナ内、~/pai_training で）:
    pixi run python ~/work/scripts/train_act.py --config ~/work/configs/train_bow_grip.yaml
"""
import argparse
import importlib.util
import json
import time
from pathlib import Path

import torch
import yaml
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset, LeRobotDatasetMetadata
from lerobot.common.datasets.utils import dataset_to_policy_features
from lerobot.common.policies.act.configuration_act import ACTConfig
from lerobot.common.policies.act.modeling_act import ACTPolicy
from lerobot.configs.types import FeatureType


def load_features(path):
    spec = importlib.util.spec_from_file_location('features', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.features


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--steps', type=int, default=None, help='学習ステップ数を上書き（速度確認用）')
    args = ap.parse_args()
    cfg = yaml.safe_load(open(Path(args.config).expanduser()))
    steps = args.steps or cfg['training_steps']
    out = Path(cfg['output_directory'])
    out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(0)

    meta = LeRobotDatasetMetadata(cfg['repo_id'], root=cfg['dataset_root'])
    features = dataset_to_policy_features(load_features(cfg['config_path']))
    out_ft = {k: f for k, f in features.items() if f.type is FeatureType.ACTION}
    in_ft = {k: f for k, f in features.items() if k not in out_ft}
    policy = ACTPolicy(ACTConfig(input_features=in_ft, output_features=out_ft,
                                 chunk_size=cfg['chunk_size'], n_action_steps=cfg['n_action_steps']),
                       dataset_stats=meta.stats)
    policy.train().to(cfg['device'])

    dataset = LeRobotDataset(cfg['repo_id'], root=cfg['dataset_root'], delta_timestamps=cfg['delta_timestamps'])
    loader = torch.utils.data.DataLoader(dataset, num_workers=cfg['num_workers'], batch_size=cfg['batch_size'],
                                         shuffle=True, drop_last=True)
    opt = torch.optim.Adam(policy.parameters(), lr=cfg['learning_rate'])

    log, step, t0 = [], 0, time.time()
    while step < steps:
        for batch in loader:
            batch = {k: (v.to(cfg['device']) if isinstance(v, torch.Tensor) else v) for k, v in batch.items()}
            # 講座と同じく、観測の時間方向の次元を取り除く
            batch['observation.state'] = batch['observation.state'][:, -1, :]
            batch['observation.environment_state'] = batch['observation.environment_state'][:, -1, :]
            loss, _ = policy.forward(batch)
            loss.backward()
            opt.step()
            opt.zero_grad()
            if step % cfg['log_freq'] == 0:
                print(f'step {step} loss {loss.item():.4f} ({time.time() - t0:.0f}s)', flush=True)
                log.append({'step': step, 'loss': loss.item(), 'sec': time.time() - t0})
            step += 1
            if step >= steps:
                break

    policy.save_pretrained(out)
    json.dump(log, open(out / 'train_log.json', 'w'), indent=1)
    print(f'保存: {out}（{time.time() - t0:.0f}秒）')


if __name__ == '__main__':
    main()
