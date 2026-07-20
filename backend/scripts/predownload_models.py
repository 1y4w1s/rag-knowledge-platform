"""Pre-download embedding models for CI cache. Run with continue-on-error: true."""
from huggingface_hub import snapshot_download
import os

cache = os.path.expanduser("~/.cache/huggingface/hub")
models = ["BAAI/bge-small-zh-v1.5", "BAAI/bge-small-en-v1.5"]

for model in models:
    dest = os.path.join(cache, "models--" + model.replace("/", "--"))
    os.makedirs(dest, exist_ok=True)
    snapshot_download(model, local_dir=dest, local_dir_use_symlinks=False)
    print(f"Cached: {model}")
