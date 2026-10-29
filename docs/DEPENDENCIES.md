# Dependencies

Pinned versions come from `backend/uv.lock`. Checked 2026-10-27.

| Name | Version | Role | License | Official reference |
|---|---|---|---|---|
| Python | 3.13.3 | runtime | PSF | https://www.python.org |
| FastAPI | 0.162.0 | HTTP API | MIT | https://fastapi.tiangolo.com |
| Uvicorn | 0.54.0 | ASGI server | BSD-3-Clause | https://www.uvicorn.org |
| Pydantic | 2.14.1 | contracts/validation | MIT | https://docs.pydantic.dev |
| pydantic-settings | 2.16.1 | config | MIT | https://docs.pydantic.dev |
| openai (SDK) | 3.39.0 | client for Meta Model API (OpenAI-compatible) and Baseten | Apache-2.0 | https://dev.meta.ai/docs/models |
| httpx | 0.28.1 | HTTP client | BSD-3-Clause | https://www.python-httpx.org |
| meta-sam-parser | 0.1.0 | parse SAM 3.1 streams, decode masks, build prompts | **SAM License** (custom; redistribution must include the agreement; acknowledge SAM in publications; no ITAR/weapons uses) | https://dev.meta.ai/docs/sam/client-libraries |
| opencv-python-headless | 4.14.0.94 (pinned `<5`) | homography, geometry | Apache-2.0 | https://docs.opencv.org/4.x/ |
| numpy | 2.5.4 | numerics | BSD-3-Clause (+ bundled MIT/Zlib/0BSD/CC0) | https://numpy.org |
| SQLAlchemy | 2.1.6 | evidence store (SQLite/Postgres) | MIT | https://docs.sqlalchemy.org |
| SciPy | 1.18.1 | Hungarian assignment (`linear_sum_assignment`) | BSD-3-Clause | https://scipy.org |
| python-multipart | see uv.lock | multipart uploads in FastAPI | Apache-2.0 | https://github.com/Kludex/python-multipart |
| psycopg[binary] | 3.3.6 (optional extra `postgres`) | Postgres driver | LGPL-3.0 | https://www.psycopg.org |
| pytest | 9.1.1 | tests (dev) | MIT | https://pytest.org |
| ruff | 0.17.3 | lint (dev) | MIT | https://docs.astral.sh/ruff |
| FFmpeg / ffprobe | 8.1 (gyan.dev essentials build, system) | media probe/derivatives | LGPL/GPL (build-dependent) | https://ffmpeg.org |

## Hosted models

| Model | Provider | Mode | Verified |
|---|---|---|---|
| `muse-spark-1.3` | Meta Model API | Standard (not `-contributor`) | listed in docs 2026-10-27; smoke test pending |
| `sam-3.1` | Meta Model API | — | listed in docs 2026-10-27; smoke test pending |
| Muse Spark Open | Baseten | — | model ID + base URL to confirm from dashboard |
