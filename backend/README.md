# winchat-api

The Python AI core for WinChat v2 (FastAPI). See the repo root `README.md` for how to run
the full stack, and `docs/PLAN.md` for architecture.

```bash
uv sync                                   # install
cp .env.example .env                      # then fill in keys
uv run uvicorn winchat_api.main:app --reload
uv run pytest
```
