import os
import os.path as osp
import sys
import time

import requests


def download(url: str, out_path: str, token: str):
    os.makedirs(osp.dirname(out_path), exist_ok=True)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    tmp = out_path + ".part"
    done = osp.exists(tmp) and osp.getsize(tmp) or 0
    if done:
        headers["Range"] = f"bytes={done}-"

    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        mode = "ab" if done else "wb"
        t0 = time.time()
        last = time.time()
        with open(tmp, mode) as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                now = time.time()
                if now - last >= 5:
                    last = now
                    if total:
                        pct = done / total * 100
                        sys.stdout.write(f"downloaded={done} total={total} pct={pct:.2f}\n")
                        sys.stdout.flush()
                    else:
                        sys.stdout.write(f"downloaded={done}\n")
                        sys.stdout.flush()
        os.replace(tmp, out_path)
        sys.stdout.write(f"done in {time.time()-t0:.1f}s\n")
        sys.stdout.flush()


def main():
    lmu = os.environ.get("LMUData", "/mnt/data/gk/LMUData")
    token = os.environ.get("HF_TOKEN", "")
    out_path = osp.join(lmu, "datasets", "DREAM-1K", "video", "video.zip")
    url = "https://huggingface.co/datasets/omni-research/DREAM-1K/resolve/main/video/video.zip"
    download(url, out_path, token)


if __name__ == "__main__":
    main()
