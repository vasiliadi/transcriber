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

`transcribe()` dispatches to one of four Replicate models, each with its own `process_*` function. There is no Replicate SDK: `run_prediction()` calls the [HTTP API](https://replicate.com/docs/reference/http) with `curl_cffi` — `upload_file()` posts the audio to `/files`, then it creates a prediction (pinned to the model's `latest_version`, or via `/models/{name}/predictions` with `official=True` for official models such as `OPENAI`) and polls it until it finishes.

Gemini (`GEMINI_MODEL`) handles the post-processing, at two points:

- `correct_transcription()` runs inside `process_incredibly_fast_whisper()` and `process_openai()` only.
- `translate()` (a no-op when no language is selected) and `identify_speakers()` (only when `num_speakers > 1`) run inside `process_transcription()`, during rendering.

`process_transcription()` expects `{"num_speakers": int, "segments": ...}` and branches on `num_speakers`:

- `0` → `segments` is plain text, no diarization
- `1` → segments, each read for `start` and `text`
- `>1` → segments, each read for `start`, `text` and `speaker`

Every `process_*` builds that dict except `process_whisper_diarization()`, which returns the Replicate output unchanged (typed `-> Any`) and relies on the model already having this shape. Build the dict explicitly when adding a model, and register it in `TRANSCRIBERS` — `transcribe()`'s `-> dict[str, Any]` does not enforce the shape.

## Gotchas

- Python 3.14 only. Check syntax with `.pixi/envs/default/bin/python`, never a system `python3`.
- The Raw JSON download reads `st.session_state.raw_output`, which `run_prediction()` sets to the last prediction's output.
- Streamlit reruns the whole script on every widget interaction. Add new user settings to `DEFAULTS` (re-assigned every run, because Streamlit deletes the key of a widget that was not rendered), and keep `@st.cache_data` on Gemini calls.
- `download()` and `compress_audio()` write `audio.mp3` / `audio.ogg` to the process cwd (`/app` in Docker).
- After changing `pixi.lock`, regenerate the conda/system package table in `THIRD_PARTY_NOTICES.md` with `pixi list -e docker --platform linux-64 --fields name,version,license`.

## Environment variables

`GEMINI_API_KEY`, `REPLICATE_API_TOKEN` and `HF_ACCESS_TOKEN` are required: read with `os.environ[...]`, they fail at startup when missing. `PROXY` (YouTube downloads via yt-dlp in `download()` only; castro.fm, direct audio links and Replicate API calls go direct) uses `os.environ.get`, so an unset value silently means no proxy.
