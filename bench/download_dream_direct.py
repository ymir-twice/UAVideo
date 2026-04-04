import os
import os.path as osp

from huggingface_hub import hf_hub_download


def main():
    lmu = os.environ.get("LMUData", "/mnt/data/gk/LMUData")
    target = osp.join(lmu, "datasets", "DREAM-1K")
    os.makedirs(osp.join(target, "video"), exist_ok=True)
    os.makedirs(osp.join(target, "json"), exist_ok=True)

    meta = hf_hub_download(
        repo_id="omni-research/DREAM-1K",
        repo_type="dataset",
        filename="json/metadata.json",
        local_dir=target,
    )
    z = hf_hub_download(
        repo_id="omni-research/DREAM-1K",
        repo_type="dataset",
        filename="video/video.zip",
        local_dir=target,
    )
    print("OK")
    print(meta)
    print(z)


if __name__ == "__main__":
    main()

