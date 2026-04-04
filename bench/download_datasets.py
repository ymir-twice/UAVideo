import os
import os.path as osp
from glob import glob


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def download_dream():
    from huggingface_hub import list_repo_files, snapshot_download

    lmu = os.environ.get("LMUData", "/mnt/data/gk/LMUData")
    target = osp.join(lmu, "datasets", "DREAM-1K")
    _ensure_dir(target)

    files = list_repo_files("omni-research/DREAM-1K", repo_type="dataset", token=os.environ.get("HF_TOKEN"))
    allow = [f for f in files if f in {"video/video.zip", "json/metadata.json", "README.md", ".gitattributes"}]
    if not allow:
        allow = files
    snapshot_download(
        repo_id="omni-research/DREAM-1K",
        repo_type="dataset",
        local_dir=target,
        allow_patterns=allow,
        resume_download=True,
        max_workers=int(os.environ.get("HF_MAX_WORKERS", "16")),
    )
    meta = osp.join(target, "json", "metadata.json")
    z = osp.join(target, "video", "video.zip")
    if not osp.exists(meta):
        raise SystemExit("DREAM-1K download finished but json/metadata.json missing.")
    if not osp.exists(z):
        raise SystemExit("DREAM-1K download finished but video/video.zip missing.")
    return target


def download_moviechat():
    lmu = os.environ.get("LMUData", "/mnt/data/gk/LMUData")
    target = osp.join(lmu, "datasets", "MovieChat-1K-test")
    _ensure_dir(target)

    try:
        from modelscope.hub.snapshot_download import snapshot_download as ms_snapshot_download
    except Exception:
        raise SystemExit("ModelScope SDK not installed. Install with: pip install modelscope")

    repo_id = os.environ.get("MOVIECHAT_MODELSCOPE_REPO", "AI-ModelScope/MovieChat-1K-test")
    ms_snapshot_download(repo_id=repo_id, repo_type="dataset", local_dir=target, allow_patterns=["*.tsv", "**/*.tsv"])
    tsvs = glob(osp.join(target, "**/*.tsv"), recursive=True)
    if not tsvs:
        raise SystemExit("MovieChat-1K-test download finished but no .tsv found.")
    return target


def main():
    dream_dir = download_dream()
    movie_dir = download_moviechat()
    print("OK")
    print(dream_dir)
    print(movie_dir)


if __name__ == "__main__":
    main()
