# transcriber — Wiki

_Updated 2026-04-23 — re-run `npx codesight --wiki` if the codebase has changed, then update manually._

> **How to use safely:** These articles tell you WHERE things live and WHAT exists. They do not show full implementation logic. Always read the actual source files before implementing new features or making changes.

## Articles

- [Overview](./overview.md) — architecture, flow, models, gotchas

## Quick Stats

- Single source file: `src/streamlit_app.py` (607 lines)
- Functions: **17**
- External services: Replicate, Google Gemini, HuggingFace, yt-dlp
- Env vars: **4** required, **0** with defaults
- Routes: **0** | Models/ORM: **0** | Database: **0**

## How to Use

- **New session:** read `index.md` (this file), then `overview.md` for architecture
- **Function reference:** read `.codesight/libs.md` for all 17 functions with descriptions
- **Config/env vars:** read `.codesight/CODESIGHT.md`
- **Before implementing anything:** read `src/streamlit_app.py` directly

---
_Last compiled: 2026-04-23 · [codesight](https://github.com/Houseofmvps/codesight)_
