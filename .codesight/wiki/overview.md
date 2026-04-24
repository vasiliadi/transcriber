# transcriber — Overview

> **Navigation aid.** Read actual source files before implementing new features or making changes.

**transcriber** is a single-file Streamlit app (`src/streamlit_app.py`) for transcribing and translating audio.

## Architecture

Single file, no database, no routes. All logic runs inside Streamlit's request/rerun model with `st.session_state` for user settings.

**Entry point:** `streamlit run src/streamlit_app.py`

## Main Flow

```
input (upload / URL / YouTube)
  → download()           # yt-dlp for YouTube, requests for URLs, file buffer for uploads
  → compress_audio()     # ffmpeg → mono ogg/opus 16kbps → audio.ogg
  → transcribe()         # dispatches to one of four Replicate models
  → (optional) correct_transcription()  # Gemini spell/punctuation fix
  → (optional) translate()              # Gemini translation
  → (optional) identify_speakers()      # Gemini speaker name inference
  → display in Streamlit
  → clean_up()           # delete audio.mp3 and audio.ogg
```

## Transcription Models (all via Replicate)

| Constant | Model slug | Best for |
|---|---|---|
| `WHISPER_DIARIZATION` | `thomasmol/whisper-diarization` | dialogs (default) |
| `INCREDIBLY_FAST_WHISPER` | `vaibhavs10/incredibly-fast-whisper` | speed |
| `OPENAI` | `openai/gpt-4o-transcribe` | accuracy |
| `WHISPERX` | `victor-upmeet/whisperx` | dialogs (newer) |

## Output Shape

All `process_*` functions normalise to `{"num_speakers": int, "segments": ...}`:
- `num_speakers == 0` → plain text (no diarization)
- `num_speakers == 1` → list of `{start, end, text}` segments
- `num_speakers > 1` → list of `{start, end, speaker, text}` segments

## External Services

- **Replicate** — runs all transcription models
- **Google Gemini** (`gemini-2.5-flash`) — post-processing, translation, speaker identification
- **HuggingFace** — token passed to diarization models that require it
- **Proxy** — forwarded to yt-dlp and requests for restricted networks

## Required Environment Variables

- `GEMINI_API_KEY`
- `HF_ACCESS_TOKEN`
- `PROXY` (optional at runtime, required declared)
- `REPLICATE_API_TOKEN`

## Gotchas

- Streamlit reruns the entire script on every widget interaction — `st.session_state` initialisation block (line 68) guards against resetting values
- `@st.cache_data` on Gemini calls avoids redundant API round-trips across reruns
- `audio.mp3` / `audio.ogg` are written to the process cwd (`temp/` in Docker via `compose.yaml`) and deleted in `finally` via `clean_up()`
- `PROXY` is read with `os.environ.get` (not `os.environ[]`) so it doesn't hard-fail when unset, but downstream yt-dlp will silently send no proxy

---
_Back to [index.md](./index.md) · Updated 2026-04-23_
