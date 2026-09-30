# Project Context

Single-file Streamlit app for audio transcription and translation. All logic lives in `src/streamlit_app.py` (~600 lines) — read it in full before implementing rather than grepping for fragments. No database, no routes, no ORM, no tests: verify changes with the type-checker and linter below.

## Commands

| Task | Command |
| --- | --- |
| Run the app | `pixi run start` |
| Type-check | `uvx pyrefly@latest check` |
| Lint | `uvx ruff@latest check` |
| Format | `uvx ruff@latest format` |

Run the app through `pixi`, never bare `python` or `streamlit`. Run the checkers exactly as written: not a system-wide `ruff`/`pyrefly`, and not without `@latest`.

## Flow

input (upload / URL / YouTube via yt-dlp) → `download()` → `compress_audio()` (ffmpeg → mono Opus/ogg, 16 kbps) → `transcribe()` → `process_transcription()` renders it → `clean_up()` (in a `finally`)

`transcribe()` dispatches to one of four Replicate models, each with its own `process_*` function:

| Constant | Model | Best for |
| --- | --- | --- |
| `WHISPER_DIARIZATION` | `thomasmol/whisper-diarization` | dialogs (default) |
| `INCREDIBLY_FAST_WHISPER` | `vaibhavs10/incredibly-fast-whisper` | speed |
| `OPENAI` | `openai/gpt-4o-transcribe` | accuracy |
| `WHISPERX` | `victor-upmeet/whisperx` | dialogs (newer) |

Gemini (`GEMINI_MODEL`) handles the post-processing, at two points:

- `correct_transcription()` runs inside `process_incredibly_fast_whisper()` and `process_openai()` only.
- `translate()` (a no-op when no language is selected) and `identify_speakers()` (only when `num_speakers > 1`) run inside `process_transcription()`, during rendering.

`process_transcription()` expects `{"num_speakers": int, "segments": ...}` and branches on `num_speakers`:

- `0` → `segments` is plain text, no diarization
- `1` → segments, each read for `start` and `text`
- `>1` → segments, each read for `start`, `text` and `speaker`

Every `process_*` builds that dict except `process_whisper_diarization()`, which returns the Replicate output unchanged (typed `-> Any`) and relies on the model already having this shape. Build the dict explicitly when adding a model — `transcribe()`'s `-> dict[str, Any] | None` does not enforce it.

## Gotchas

- Python 3.14 only. `get_latest_prediction_output()` has an unparenthesized `except TypeError, httpx.ReadTimeout:` — valid under [PEP 758](https://peps.python.org/pep-0758/); do not add parentheses. Check syntax with `.pixi/envs/default/bin/python`, never a system `python3`.
- Streamlit reruns the whole script on every widget interaction. Add new user settings to the `st.session_state` init block, and keep `@st.cache_data` on Gemini calls.
- `download()` and `compress_audio()` write `audio.mp3` / `audio.ogg` to the process cwd (`/app` in Docker).
- After changing `pixi.lock`, regenerate the conda/system package table in `THIRD_PARTY_NOTICES.md` with `pixi list -e docker --platform linux-64 --fields name,version,license`.

## Environment variables

Required variables are read with `os.environ[...]` and fail at startup when missing; `PROXY` uses `os.environ.get`, so an unset value silently means no proxy.

| Variable | Required | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | yes | Google Gemini client |
| `REPLICATE_API_TOKEN` | yes | Replicate client |
| `HF_ACCESS_TOKEN` | yes | HuggingFace token passed to diarization models |
| `PROXY` | no | proxy for yt-dlp and curl_cffi |
