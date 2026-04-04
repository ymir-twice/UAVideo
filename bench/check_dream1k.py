#!/usr/bin/env python3
"""检查DREAM-1K数据集格式"""
import json
from pathlib import Path

metadata_file = Path("/mnt/data/gk/LMUData/datasets/dream1k/json/metadata.json")

with open(metadata_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"DREAM-1K数据集类型: 视频描述 (Video Description)")
print(f"总样本数: {len(data)}")
print()

if len(data) > 0:
    first_sample = data[0] if isinstance(data, list) else next(iter(data.values()))
    print("第一个样本的字段:")
    for key in first_sample.keys():
        print(f"  - {key}")
    print()

    print("第一个样本内容:")
    print(json.dumps(first_sample, ensure_ascii=False, indent=2)[:500])
