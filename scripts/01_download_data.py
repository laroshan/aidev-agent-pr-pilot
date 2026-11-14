"""Download the AIDev tables this pilot uses, pinned to one dataset commit.

The pilot uses AIDev v3, the release used by the MSR 2026 Mining Challenge
(data up to 2025-08-01). It is the only release that ships human-authored PRs
(`human_pull_request`) from the same repositories as the agent PRs; v4 and v5
dropped that table.

Usage:
    python scripts/01_download_data.py [--data-dir data/aidev_v3]

Every file is checked against the SHA-256 that Hugging Face reports for the
pinned commit, so a re-run either reproduces the same bytes or fails loudly.
"""
import argparse
import hashlib
import os
import sys
import urllib.request

REPO = "hao-li/AIDev"
# Commit that the `v3` tag points to (checked 2026-11-02 via the HF refs API).
REVISION = "3ca0045773097b138b064550dfd6e72229f40bee"

# file name -> (size in bytes, sha256), from the HF tree API at REVISION.
FILES = {
    "pull_request.parquet": (
        16855612, "08f520b5ef36b6281f82090db09ac14aefc3534ee113886e7bc85131fd8d214c"),
    "human_pull_request.parquet": (
        4387171, "910238f8fe5deb544ae82be343232ff6838f271f3de4b4e4787a515336a91248"),
    "repository.parquet": (
        167251, "5b76717c39be1cada097d680aa0fcecd03611aa52ae05ef7f1d1e0e1e8b34192"),
    "pr_task_type.parquet": (
        2993264, "f32a97a45ac944f4ea473327e62d8f41361502c2b6b3778e76fb64c2b8896476"),
    "human_pr_task_type.parquet": (
        715969, "5527d52bfd9605a25d1ed1ef03bce0e1cc217f6ffed936e2be1b80a04123e658"),
    "pr_reviews.parquet": (
        7517041, "3b7996c6365000e9e7f91bb428ecff78b36290997bee4732e840b0f5cdce70f5"),
    "pr_comments.parquet": (
        25857243, "b8d16135cdd33de13aae32d50523b2b77b508412b245f80f1e3664c9b8b7dacd"),
    "pr_review_comments_v2.parquet": (
        21125785, "a0739f9c808fa1c720037e162efa27baadeedb7180ea94a22dad5062adc71be8"),
    "pr_commits.parquet": (
        8314097, "339228e250d420cd20ffe4b90583d57040263427ea605c1c039631b8ca2bfb4f"),
    "pr_timeline.parquet": (
        34108415, "9f45c52c0a7ffa4395ea6c7ce5beb993b3dfb2425ef3848c6d28e2e96471a6f8"),
    "pr_commit_details.parquet": (
        485214032, "28efcc5b23c657fad8aa3da374fad40d164934e5aeefc5e23ad55ec69a592836"),
}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(name, size, digest, data_dir):
    dest = os.path.join(data_dir, name)
    if os.path.exists(dest) and os.path.getsize(dest) == size and sha256_of(dest) == digest:
        print("ok (cached)  %s" % name)
        return
    url = "https://huggingface.co/datasets/%s/resolve/%s/%s" % (REPO, REVISION, name)
    tmp = dest + ".part"
    print("downloading  %s (%.1f MB)" % (name, size / 1e6), flush=True)
    with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    got = sha256_of(tmp)
    if got != digest:
        os.remove(tmp)
        sys.exit("checksum mismatch for %s: expected %s, got %s" % (name, digest, got))
    os.replace(tmp, dest)
    print("ok           %s" % name)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", default=os.path.join(here, "..", "data", "aidev_v3"))
    args = ap.parse_args()
    os.makedirs(args.data_dir, exist_ok=True)
    for name, (size, digest) in FILES.items():
        download(name, size, digest, args.data_dir)


if __name__ == "__main__":
    main()
