import os
import os.path as osp
import time

import requests
from dotenv import dotenv_values


def main():
    cfg_path = "/mnt/data/gk/pretrained_models/doubao-1.8"
    if not osp.exists(cfg_path):
        raise SystemExit("doubao config not found")
    cfg = dotenv_values(cfg_path)
    base_url = (cfg.get("DOUBAO_BASE_URL") or "").rstrip("/")
    api_key = cfg.get("DOUBAO_API_KEY") or ""
    model = cfg.get("DOUBAO_MODEL") or ""
    if not base_url or not api_key or not model:
        raise SystemExit("doubao config missing DOUBAO_BASE_URL/DOUBAO_API_KEY/DOUBAO_MODEL")

    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    t0 = time.time()
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    out = data["choices"][0]["message"]["content"].strip()
    dt = time.time() - t0
    print("ok")
    print(f"latency_s={dt:.2f}")
    print(f"reply={out[:80]}")


if __name__ == "__main__":
    main()

