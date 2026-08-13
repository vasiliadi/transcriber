# Project Context

Single-file Streamlit app for audio transcription and translation. All logic lives in `src/streamlit_app.py`. No database, no routes, no ORM, no tests.

## Commands

| Task | Command |
| --- | --- |
| Run the app | `pixi run start` |
| Type-check | `uvx pyrefly@latest check` |
| Lint | `uvx ruff@latest check` |
| Format | `uvx ruff@latest format` |

Run the app through `pixi`, never bare `python` or `streamlit`.

Run the checkers through `uvx …@latest`, which fetches the newest release on each invocation — nothing to install, and no stale local copy. Do not substitute a system-wide `ruff` or `pyrefly`, and do not drop the `@latest` suffix; both can leave you on an older version than intended.

## Stack

Streamlit (UI) · Replicate (transcription) · Google Gemini (correction, translation, speaker ID) · yt-dlp (YouTube) · curl_cffi (HTTP) · ffmpeg (compression)

## Flow

input (upload / URL / YouTube) → `download()` → `compress_audio()` (ffmpeg → mono ogg 16 kbps) → `transcribe()` → optional `correct_transcription()` / `translate()` / `identify_speakers()` → display → `clean_up()`

`transcribe()` dispatches to one of four Replicate models, each with its own `process_*` function:

| Constant | Model | Best for |
| --- | --- | --- |
| `WHISPER_DIARIZATION` | `thomasmol/whisper-diarization` | dialogs (default) |
| `INCREDIBLY_FAST_WHISPER` | `vaibhavs10/incredibly-fast-whisper` | speed |
| `OPENAI` | `openai/gpt-4o-transcribe` | accuracy |
| `WHISPERX` | `victor-upmeet/whisperx` | dialogs (newer) |

`process_transcription()` expects `{"num_speakers": int, "segments": ...}` and branches on `num_speakers`:

- `0` → plain text, no diarization
- `1` → segments, each read for `start` and `text`
- `>1` → segments, each read for `start`, `text` and `speaker`

`process_openai`, `process_whisperx` and `process_incredibly_fast_whisper` build that dict themselves. `process_whisper_diarization` does not — it is typed `-> Any` and returns the Replicate output unchanged, relying on the upstream model to already have this shape. Build the dict explicitly when adding a model: `transcribe()`'s `-> dict[str, Any] | None` does not enforce it.

## Gotchas

- The project targets Python 3.14 (`requires-python`, ruff `target-version`, pyrefly `python-version`), so it uses 3.14-only syntax. `get_latest_prediction_output()` has an unparenthesized `except TypeError, httpx.ReadTimeout:` — valid under [PEP 758](https://peps.python.org/pep-0758/). It is not a mistake; do not "fix" it by adding parentheses. An older interpreter will call it a `SyntaxError`, so check syntax with `.pixi/envs/default/bin/python`, never a system `python3`.
- Streamlit reruns the whole script on every widget interaction. Add new user settings to the `st.session_state` init block, and keep `@st.cache_data` on Gemini calls.
- `download()` and `compress_audio()` write `audio.mp3` / `audio.ogg` to the process cwd (`/app` in Docker); `clean_up()` deletes them in a `finally`.
- `PROXY` is read with `os.environ.get`, so an unset value silently sends no proxy instead of failing.
- After changing `pixi.lock`, regenerate the conda/system package table in `THIRD_PARTY_NOTICES.md` with `pixi list -e docker --platform linux-64 --fields name,version,license`.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | yes | Google Gemini client |
| `REPLICATE_API_TOKEN` | yes | Replicate client |
| `HF_ACCESS_TOKEN` | yes | HuggingFace token passed to diarization models |
| `PROXY` | no | proxy for yt-dlp and curl_cffi |

Read `src/streamlit_app.py` in full before implementing. It is a single file, short enough to read in one pass — do that rather than grepping for fragments.
