# Project Context

This is a single-file Streamlit app (`src/streamlit_app.py`, 607 lines) for audio transcription and translation.

**Run:** `streamlit run src/streamlit_app.py`

**Stack:** Python, Streamlit, Replicate (transcription models), Google Gemini (post-processing/translation/speaker ID), yt-dlp (YouTube download), ffmpeg (audio compression)

**Transcription models (via Replicate):**
- `thomasmol/whisper-diarization` — best for dialogs (default)
- `vaibhavs10/incredibly-fast-whisper` — best for speed
- `openai/gpt-4o-transcribe` — best accuracy
- `victor-upmeet/whisperx` — new best for dialogs

**Key flow:** input (upload/URL/YouTube) → `download()` → `compress_audio()` (ffmpeg → mono ogg 16kbps) → `transcribe()` → optional `correct_transcription()` / `translate()` / `identify_speakers()` → display

**Scratch files:** `audio.mp3` and `audio.ogg` written to cwd, deleted in `clean_up()` after each run.

**No database, no routes, no ORM.**

Required environment variables (no defaults):
- `GEMINI_API_KEY` — Google Gemini client
- `HF_ACCESS_TOKEN` — HuggingFace token passed to diarization models
- `PROXY` — optional proxy for yt-dlp/requests (read via `os.environ.get`)
- `REPLICATE_API_TOKEN` — Replicate client

Read `.codesight/libs.md` for a full function index. Read actual source files before implementing.
