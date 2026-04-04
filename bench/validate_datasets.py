import os
import os.path as osp
from glob import glob


def validate_moviechat(root: str):
    ann = osp.join(root, "annotations")
    gt = osp.join(root, "gt", "gt")
    vid = osp.join(root, "videos")
    ann_files = sorted(glob(osp.join(ann, "*.json")))
    gt_files = sorted(glob(osp.join(gt, "*.json")))
    vid_files = sorted(glob(osp.join(vid, "*.mp4")))
    ann_ids = {osp.splitext(osp.basename(p))[0] for p in ann_files}
    gt_ids = {osp.splitext(osp.basename(p))[0] for p in gt_files}
    vid_ids = {osp.splitext(osp.basename(p))[0] for p in vid_files}
    miss_gt = sorted(ann_ids - gt_ids)
    miss_vid = sorted(ann_ids - vid_ids)
    return {
        "annotations": len(ann_files),
        "gt": len(gt_files),
        "videos": len(vid_files),
        "missing_gt": len(miss_gt),
        "missing_videos": len(miss_vid),
    }


def validate_dream(root: str):
    tsvs = glob(osp.join(root, "**/*.tsv"), recursive=True)
    mp4s = glob(osp.join(root, "**/*.mp4"), recursive=True)
    zips = glob(osp.join(root, "**/*.zip"), recursive=True)
    return {"tsv": len(tsvs), "mp4": len(mp4s), "zip": len(zips)}


def main():
    lmu = os.environ.get("LMUData", "/mnt/data/gk/LMUData")
    movie = osp.join(lmu, "datasets", "MovieChat-1K-test")
    dream = osp.join(lmu, "datasets", "DREAM-1K")
    if osp.isdir(movie):
        print("MovieChat-1K-test", validate_moviechat(movie))
    else:
        print("MovieChat-1K-test missing")
    if osp.isdir(dream):
        print("DREAM-1K", validate_dream(dream))
    else:
        print("DREAM-1K missing")


if __name__ == "__main__":
    main()

