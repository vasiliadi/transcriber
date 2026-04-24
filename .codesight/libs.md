# Libraries

- `src/streamlit_app.py`

  **Ingestion**
  - `download(url, mode)` — saves uploaded file buffer or fetches audio from YouTube (yt-dlp), castro.fm (BeautifulSoup scrape), or generic URL (requests)

  **Audio**
  - `compress_audio(audio_file_name, converted_file_name)` — ffmpeg: convert any input to mono ogg/opus at 16kbps; calls `st.stop()` on failure

  **Transcription (Replicate)**
  - `get_latest_model_version(model_name)` — returns latest version ID for a Replicate model
  - `get_latest_prediction_output(sleep_time)` — polls Replicate predictions until output is non-None (handles `httpx.ReadTimeout`)
  - `process_whisper_diarization(audio_file_name)` — runs `thomasmol/whisper-diarization`; returns segments with speaker labels
  - `process_incredibly_fast_whisper(audio_file_name, diarization, post_processing)` — runs `vaibhavs10/incredibly-fast-whisper`; normalises output to `{num_speakers, segments}`
  - `process_openai(audio_file_name)` — runs `openai/gpt-4o-transcribe`; returns `{num_speakers: 0, segments: corrected_text}`
  - `process_whisperx(audio_file_name, diarization)` — runs `victor-upmeet/whisperx`; returns `{num_speakers, segments}`
  - `transcribe(model_name)` — dispatcher: routes to one of the four process_* functions above

  **Post-processing (Gemini)**
  - `correct_transcription(transcription, post_processing)` — Gemini: fix spelling/punctuation, split by speaker; `@st.cache_data`
  - `translate(text, target_language, chunks, sleep_time)` — Gemini translation with rate-limit sleep; `@st.cache_data`
  - `identify_speakers(transcription)` — Gemini: infer real names from context and return `{SPEAKER_XX: name}` dict; `@st.cache_data`

  **Speaker helpers**
  - `detected_num_speakers(transcription, model)` — count unique SPEAKER_* values; model-specific segment path; `@st.cache_data`
  - `process_diarization_for_incredibly_fast_whisper(transcription)` — merge consecutive same-speaker segments within 2s gap; `@st.cache_data`

  **Utilities**
  - `convert_to_minutes(seconds)` — float seconds → `"M:SS"` string; `@st.cache_data`
  - `clean_up()` — delete `audio.mp3` and `audio.ogg` from cwd
  - `process_transcription()` — top-level orchestrator: compress → transcribe → branch on `num_speakers` (0/1/multi) → display with optional translation and raw JSON download
