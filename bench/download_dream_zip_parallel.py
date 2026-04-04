import math
import os
import os.path as osp
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def _download_range(url: str, out_path: str, headers: dict, start: int, end: int, retries: int = 5) -> int:
    expected = end - start + 1
    done = osp.getsize(out_path) if osp.exists(out_path) else 0
    if done >= expected:
        return done

    for attempt in range(retries):
        h = dict(headers)
        cur_start = start + done
        h["Range"] = f"bytes={cur_start}-{end}"
        try:
            with requests.get(url, headers=h, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(out_path, "ab") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                if done >= expected:
                    return done
        except Exception:
            pass
    raise RuntimeError(f"incomplete part: {out_path} got={done} expected={expected}")


def main():
    lmu = os.environ.get("LMUData", "/mnt/data/gk/LMUData")
    token = os.environ.get("HF_TOKEN", "")
    url = "https://huggingface.co/datasets/omni-research/DREAM-1K/resolve/main/video/video.zip"
    out_dir = osp.join(lmu, "datasets", "DREAM-1K", "video")
    os.makedirs(out_dir, exist_ok=True)
    out_file = osp.join(out_dir, "video.full.zip")

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    h0 = dict(headers)
    h0["Range"] = "bytes=0-0"
    r0 = requests.get(url, headers=h0, timeout=60, allow_redirects=True)
    r0.raise_for_status()
    cr = r0.headers.get("Content-Range") or ""
    if "/" not in cr:
        raise SystemExit("missing Content-Range")
    total = int(cr.split("/")[-1])
    if total <= 0:
        raise SystemExit("invalid total size")

    parts = int(os.environ.get("HF_PARALLEL_PARTS", "8"))
    parts = max(1, min(parts, 32))
    part_size = math.ceil(total / parts)

    tmp_files = []
    tasks = []
    expected_sizes = []
    with ThreadPoolExecutor(max_workers=parts) as ex:
        for i in range(parts):
            start = i * part_size
            end = min(total - 1, (i + 1) * part_size - 1)
            if start > end:
                continue
            tmp = out_file + f".part{i:02d}"
            tmp_files.append(tmp)
            expected_sizes.append(end - start + 1)
            tasks.append(ex.submit(_download_range, url, tmp, headers, start, end))

        sizes = []
        for fut in as_completed(tasks):
            sizes.append(fut.result())
            print(f"part_done={len(sizes)}/{len(tasks)}")

    with open(out_file + ".tmp", "wb") as out:
        for tmp in tmp_files:
            with open(tmp, "rb") as f:
                out.write(f.read())
    os.replace(out_file + ".tmp", out_file)
    if osp.getsize(out_file) != total:
        raise RuntimeError(f"size mismatch: got={osp.getsize(out_file)} expected={total}")
    for tmp in tmp_files:
        try:
            os.remove(tmp)
        except Exception:
            pass
    print("OK")
    print(out_file)
    print(f"bytes={total}")


if __name__ == "__main__":
    main()
