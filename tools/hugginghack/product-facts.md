# HuggingHack product facts

> Verified: 2026-07-23 against official Hugging Face pages and documentation.

## Confirmed platform behavior

- Hugging Face exposes model discovery through `HfApi.list_models`, including search, task, parameter, app, and sort filters.
- `snapshot_download` downloads a complete repository revision and supports a stable `local_dir`, include patterns, exclude patterns, authentication tokens, and concurrent workers.
- A repository downloaded with `local_dir` keeps its original file hierarchy and creates `.cache/huggingface` metadata so later updates can avoid re-downloading unchanged files.
- `model_info(..., files_metadata=True)` returns file size/LFS metadata used for storage estimates and download progress.
- Private and gated models require a user access token. Gated model terms must first be accepted in the user's Hugging Face account.
- Model cards are repository `README.md` files with YAML metadata and Markdown content.
- Model repositories can contain unsafe pickle-based artifacts. HuggingHack downloads files but never imports, unpickles, or executes model code.

## Current UI reference

- The live Models catalog uses compact top navigation, global search, a left filter column, small metadata badges, and sort controls. HuggingHack adapts that hierarchy into a responsive visual-card grid rather than copying the site.
- Model detail pages use a namespace/repository title, likes/follow actions, tags, license metadata, Model card / Files / Community tabs, and local-app guidance.
- Official brand colors published by Hugging Face are `#FFD21E`, `#FF9D00`, and `#6B7280`.

## Sources

- https://huggingface.co/models
- https://huggingface.co/brand
- https://huggingface.co/docs/huggingface_hub/package_reference/hf_api
- https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download
- https://huggingface.co/docs/huggingface_hub/en/guides/download
- https://huggingface.co/docs/hub/en/models-gated
- https://huggingface.co/docs/hub/en/model-cards
- https://huggingface.co/docs/hub/security-pickle
