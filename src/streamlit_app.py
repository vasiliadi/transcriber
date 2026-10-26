import json
import os
import subprocess
import time
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import urlparse

import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import CurlMime, requests
from curl_cffi.requests.exceptions import RequestException
from curl_cffi.requests.utils import requote_uri
from google import genai
from google.genai import types
from pydantic import BaseModel
from yt_dlp import YoutubeDL

if TYPE_CHECKING:
    from streamlit.runtime.uploaded_file_manager import UploadedFile

# Google Gemini config
gemini_api_key = os.environ["GEMINI_API_KEY"]
gemini_client = genai.Client(api_key=gemini_api_key)
GEMINI_MODEL = "gemini-3.8-flash"
THINKING_CONFIG = types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)


# Replicate.com config
replicate_api_token = os.environ["REPLICATE_API_TOKEN"]
REPLICATE_API_URL = "https://api.replicate.com/v1"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

# HuggingFace.co config
hf_access_token = os.environ["HF_ACCESS_TOKEN"]

# Proxy for YouTube (yt-dlp) downloads only
proxy = os.environ.get("PROXY")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}

# Constants
AUDIO_FILE_NAME = "audio.mp3"
CONVERTED_FILE_NAME = "audio.ogg"
WHISPER_DIARIZATION = "thomasmol/whisper-diarization"
INCREDIBLY_FAST_WHISPER = "vaibhavs10/incredibly-fast-whisper"
OPENAI = "openai/gpt-4o-transcribe"
WHISPERX = "victor-upmeet/whisperx"


class SpeakerMapping(BaseModel):
    original_speaker: str
    detected_speaker: str


# Initialization
DEFAULTS = {
    "mode": "YouTube or link to an audio file",
    "language": None,
    "model_name": WHISPER_DIARIZATION,
    "post_processing": True,
    "diarization": True,
    "speaker_identification": True,
    "raw_json": False,
    "raw_output": None,
}
# Streamlit deletes the key of a widget not rendered in a run; re-assigning every
# key each run keeps the user's choice and seeds missing defaults.
for key, value in DEFAULTS.items():
    st.session_state[key] = st.session_state.get(key, value)


# Functions
def fetch(url: str, stream: bool = False) -> requests.Response:
    response = requests.get(
        requote_uri(url),
        impersonate="chrome",
        verify=True,
        timeout=120,
        stream=stream,
    )
    try:
        response.raise_for_status()
    except RequestException:
        response.close()
        raise
    return response


def download(url: Any) -> None:
    with st.spinner("Uploading the file to the server..."):
        if st.session_state.mode == "Uploaded file":
            with Path(AUDIO_FILE_NAME).open("wb") as f:
                f.write(url.getbuffer())
        elif st.session_state.mode == "YouTube or link to an audio file":
            if urlparse(url).hostname in YOUTUBE_HOSTS:
                ydl_opts = {
                    "format": "worstaudio",
                    "outtmpl": "audio",
                    "proxy": proxy,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                        },
                    ],
                }
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(url)
            else:
                if url.startswith("https://castro.fm/episode/"):
                    source = BeautifulSoup(fetch(url).content, "html.parser").source
                    src = source.get("src") if source is not None else None
                    if not isinstance(src, str) or not src.strip():
                        st.error(
                            "Could not extract audio URL from castro.fm page",
                            icon="🚨",
                        )
                        st.stop()
                    url = src
                # stream to disk; with stream=True the timeout limits stalls, not the whole transfer
                downloaded_file = fetch(url, stream=True)
                try:
                    with Path(AUDIO_FILE_NAME).open("wb") as f:
                        f.writelines(downloaded_file.iter_content())
                finally:
                    downloaded_file.close()


def compress_audio() -> None:
    try:
        subprocess.run(
            [
                "ffmpeg",  # /usr/bin/ffmpeg
                "-y",
                "-i",
                AUDIO_FILE_NAME,
                "-vn",
                "-ac",
                "1",
                "-c:a",
                "libopus",
                "-b:a",
                "16k",
                CONVERTED_FILE_NAME,
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        st.error("Check uploaded file 👀", icon="🚨")
        st.stop()


@st.cache_data(show_spinner=False)
def correct_transcription(
    transcription: str,
    post_processing: bool = st.session_state.post_processing,
) -> str:
    if post_processing:
        prompt = f"Correct any spelling discrepancies in the transcribed text. Split text by speaker. Only add necessary punctuation such as periods, commas, and capitalization, and use only the context provided: <transcribed_text>{transcription}</transcribed_text>"
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="text/plain",
                thinking_config=THINKING_CONFIG,
            ),
        )
        if response.text is not None:
            return response.text
    return transcription


def replicate_request(
    method: Literal["GET", "POST"],
    path: str,
    **kwargs: Any,
) -> Any:
    # Only GET is retried: a retried POST could create (and bill) a duplicate prediction
    attempts = 5 if method == "GET" else 1
    for attempt in range(1, attempts + 1):
        delay = 2 ** (attempt - 1)
        try:
            response = requests.request(
                method,
                f"{REPLICATE_API_URL}/{path}",
                headers={"Authorization": f"Bearer {replicate_api_token}"},
                verify=True,
                timeout=120,
                **kwargs,
            )
        except RequestException:  # connection errors and timeouts
            if attempt == attempts:
                raise
        else:
            if response.status_code not in RETRYABLE_STATUSES or attempt == attempts:
                response.raise_for_status()
                return response.json()
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None and retry_after.isdigit():
                delay = int(retry_after)
        time.sleep(delay)
    return None  # unreachable: the last attempt returns or raises


def upload_file(audio_file_name: str) -> str:
    multipart = CurlMime()
    multipart.addpart(
        name="content",
        content_type="audio/ogg",
        filename=Path(audio_file_name).name,
        local_path=audio_file_name,
    )
    try:
        return replicate_request("POST", "files", multipart=multipart)["urls"]["get"]
    finally:
        multipart.close()


def get_latest_model_version(model_name: str) -> str:
    return replicate_request("GET", f"models/{model_name}")["latest_version"]["id"]


def run_prediction(
    model_name: str,
    model_input: dict[str, Any],
    official: bool = False,
) -> Any:
    if official:  # official models run without a version id
        prediction = replicate_request(
            "POST",
            f"models/{model_name}/predictions",
            json={"input": model_input},
        )
    else:
        prediction = replicate_request(
            "POST",
            "predictions",
            json={
                "version": get_latest_model_version(model_name),
                "input": model_input,
            },
        )
    while prediction["status"] in {"starting", "processing"}:
        time.sleep(10)
        prediction = replicate_request("GET", f"predictions/{prediction['id']}")
    if prediction["status"] != "succeeded":
        msg = f"Prediction {prediction['status']}: {prediction.get('error')}"
        raise RuntimeError(msg)
    st.session_state.raw_output = prediction["output"]
    return prediction["output"]


def count_speakers(segments: list[dict[str, Any]]) -> int:
    # never 0, which would render the segments as plain text
    return max(1, len({s["speaker"] for s in segments}))


def process_diarization_for_incredibly_fast_whisper(
    transcription: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # merge consecutive chunks of the same speaker separated by at most 2 seconds
    output: list[dict[str, Any]] = []
    prev_end: float | None = None
    for chunk in transcription:
        start, end = chunk["timestamp"]  # end can be None on the last chunk
        if (
            output
            and chunk["speaker"] == output[-1]["speaker"]
            and prev_end is not None
            and start - prev_end <= 2  # noqa: PLR2004
        ):
            output[-1]["end"] = str(end)
            output[-1]["text"] += " " + chunk["text"]
        else:
            output.append(
                {
                    "start": str(start),
                    "end": str(end),
                    "speaker": chunk["speaker"],
                    "text": chunk["text"],
                },
            )
        prev_end = end
    return output


def process_whisper_diarization() -> Any:
    return run_prediction(
        WHISPER_DIARIZATION,
        {
            "file": upload_file(CONVERTED_FILE_NAME),
            "transcript_output_format": "segments_only",
        },
    )


def process_incredibly_fast_whisper(
    diarization: bool = st.session_state.diarization,
    post_processing: bool = st.session_state.post_processing,
) -> dict[str, Any]:
    transcription: Any = run_prediction(
        INCREDIBLY_FAST_WHISPER,
        {
            "audio": upload_file(CONVERTED_FILE_NAME),
            "hf_token": hf_access_token,
            "diarise_audio": diarization,
        },
    )
    # Diarized output is a list of segments plus the full transcript as the last item;
    # a dict means no diarization (disabled, or pyannote failed to load)
    if isinstance(transcription, dict):
        return {
            "num_speakers": 0,
            "segments": correct_transcription(
                transcription["text"],
                post_processing=post_processing,
            ),
        }
    segments = transcription[:-1]
    return {
        "num_speakers": count_speakers(segments),
        "segments": process_diarization_for_incredibly_fast_whisper(segments),
    }


def process_openai() -> dict[str, Any]:
    transcription = run_prediction(
        OPENAI,
        {"audio_file": upload_file(CONVERTED_FILE_NAME)},
        official=True,
    )
    return {
        "num_speakers": 0,
        "segments": correct_transcription("".join(transcription)),
    }


def process_whisperx(
    diarization: bool = st.session_state.diarization,
) -> dict[str, Any]:
    segments = run_prediction(
        WHISPERX,
        {
            "audio_file": upload_file(CONVERTED_FILE_NAME),
            "diarization": diarization,
            "huggingface_access_token": hf_access_token,
        },
    )["segments"]
    return {
        "num_speakers": count_speakers(segments) if diarization else 1,
        "segments": segments,
    }


TRANSCRIBERS = {
    WHISPER_DIARIZATION: process_whisper_diarization,
    INCREDIBLY_FAST_WHISPER: process_incredibly_fast_whisper,
    OPENAI: process_openai,
    WHISPERX: process_whisperx,
}


def transcribe() -> dict[str, Any]:
    return TRANSCRIBERS[st.session_state.model_name]()


@st.cache_data(show_spinner=False)
def translate(
    text: str,
    target_language: str | None = st.session_state.language,
    chunks: bool = False,
) -> str:
    if target_language is None:
        return text
    prompt = f"Translate input text to {target_language}. Return only translated text: <input_text>{text}</input_text>"
    translation = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=dedent("""
                You are a language model specializing in accurate, context-sensitive translations.
                Translate each text with precise meaning and maintain the original tone and style.
                Adapt idioms, cultural references, and metaphors for naturalness in the target language.
                Avoid literal translations unless they are essential.
                When terms have multiple meanings, use the context to select the best fit.
                Do not translate proper nouns or technical terms unless widely recognized equivalents exist.
                Ensure consistent terminology, especially for technical or specialized language.
                Use polite, respectful language, adjusting formality as appropriate for the text type (e.g., legal, business, casual).
                I want you to only reply the translation, do not write notes or explanations.
                """).strip(),
            response_mime_type="text/plain",
            thinking_config=THINKING_CONFIG,
        ),
    )
    if chunks:
        # Gemini Flash rate limit https://ai.google.dev/gemini-api/docs/rate-limits
        time.sleep(5)
    if translation.text is not None:
        return translation.text
    return text


@st.cache_data(show_spinner=False)
def identify_speakers(transcription: dict[str, Any]) -> dict[str, str]:
    prompt = (
        f'Identify speaker names from context and map each "SPEAKER_XX" label to the identified name in this json <transcribed_json>{transcription}</transcribed_json>. '
        'If a speaker cannot be identified, return their original label as the detected name (e.g. original_speaker="SPEAKER_00", detected_speaker="SPEAKER_00"). '
        "Return one entry per unique speaker."
    )
    names = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[SpeakerMapping],
            thinking_config=THINKING_CONFIG,
        ),
    )
    parsed = cast("list[SpeakerMapping] | None", names.parsed)
    if not parsed:
        st.error("Can't identify speakers 🙈", icon="🚨")
        st.stop()
    return {m.original_speaker: m.detected_speaker for m in parsed}


def convert_to_minutes(seconds: float | str) -> str:
    minutes, seconds = divmod(float(seconds), 60)
    return f"{int(minutes)}:{int(seconds):02d}"


def clean_up() -> None:
    if Path(CONVERTED_FILE_NAME).is_file():
        Path(CONVERTED_FILE_NAME).unlink()
    if Path(AUDIO_FILE_NAME).is_file():
        Path(AUDIO_FILE_NAME).unlink()


def process_transcription() -> None:
    with st.spinner("Compressing file..."):
        compress_audio()
    st.audio(CONVERTED_FILE_NAME)
    with st.spinner("Transcribing..."):
        transcription = transcribe()
        if transcription["num_speakers"] == 1:
            for segment in transcription["segments"]:
                text = str(segment["text"]).replace("$", r"\$")
                st.markdown(
                    f"**{convert_to_minutes(segment['start'])}:** {translate(text, chunks=True)}",
                )
        elif transcription["num_speakers"] == 0:  # plain text
            st.markdown(translate(transcription["segments"]).replace("$", r"\$"))
        else:
            names = (
                identify_speakers(transcription)
                if st.session_state.speaker_identification
                else {}
            )
            for segment in transcription["segments"]:
                text = str(segment["text"]).replace("$", r"\$")
                st.markdown(
                    f"**{convert_to_minutes(segment['start'])} - {names.get(segment['speaker'], segment['speaker'])}:** {translate(text, chunks=True)}",
                )
        if st.session_state.raw_json:
            data = json.dumps(st.session_state.raw_output)
            st.download_button(
                label="Download JSON",
                data=data,
                file_name="data.json",
                mime="application/json",
            )


# Frontend
st.set_page_config(page_title="Transcriber")
st.title("Transcribe & Translate Audio Files")

st.radio(
    label="Choose what to transcribe:",
    options=["Uploaded file", "YouTube or link to an audio file"],
    key="mode",
)

data_input: UploadedFile | str | None = None
if st.session_state.mode == "Uploaded file":
    data_input = st.file_uploader(
        "Choose a file:",
        # https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/audio-understanding#audio-requirements
        type=["wav", "mp3", "aiff", "aac", "ogg", "flac", "m4a", "mp4", "mov"],
    )
if st.session_state.mode == "YouTube or link to an audio file":
    data_input = st.text_input(
        label="Enter a YouTube URL or audio link:",
        placeholder="https://traffic.megaphone.fm/GLD4878952581.mp3",
    )

target_language = st.selectbox(
    label="If you choose to translate, content will be returned translated.",
    options=["English", "Ukrainian", "Spanish", "French", "German", "Russian"],
    index=None,
    placeholder="Select the target language if you need translation, or skip it if you don't",
    label_visibility="collapsed",
    key="language",
)

advanced = st.toggle("Advanced settings")

if advanced:
    st.text("Model settings")
    col1_model_selection, col2_model_settings = st.columns(2)
    with col1_model_selection:
        st.radio(
            label="Select option",
            label_visibility="collapsed",
            options=[WHISPER_DIARIZATION, INCREDIBLY_FAST_WHISPER, OPENAI, WHISPERX],
            captions=[
                "best for dialogs",
                "best for speed",
                "best in accuracy",
                "new best for dialogs",
            ],
            key="model_name",
            horizontal=False,
        )
    with col2_model_settings:
        if st.session_state.model_name in {INCREDIBLY_FAST_WHISPER, WHISPERX}:
            if st.session_state.diarization:
                st.session_state.post_processing = False
            else:
                st.session_state.speaker_identification = False
        if st.session_state.model_name == WHISPER_DIARIZATION:
            st.checkbox(
                "Enable speaker identification",
                key="speaker_identification",
            )
        if st.session_state.model_name == INCREDIBLY_FAST_WHISPER:
            st.checkbox("Enable diarization", key="diarization")
            st.checkbox(
                "Enable speaker identification",
                disabled=not st.session_state.diarization,
                key="speaker_identification",
            )
            st.checkbox(
                "Enable post-processing",
                disabled=st.session_state.diarization,
                key="post_processing",
            )
        if st.session_state.model_name == OPENAI:
            st.checkbox("Enable post-processing", key="post_processing")
        if st.session_state.model_name == WHISPERX:
            st.checkbox("Enable diarization", key="diarization")
            st.checkbox(
                "Enable speaker identification",
                disabled=not st.session_state.diarization,
                key="speaker_identification",
            )

    st.checkbox("Enable Raw JSON download", key="raw_json")
    st.divider()

    if st.button("Clear Cache", type="primary"):
        st.cache_data.clear()
        st.success("Cache cleared.")
    st.divider()

go = st.button("Go")

# Data processing
if go:
    try:
        if st.session_state.mode == "Uploaded file" and data_input is None:
            st.error("Upload an audio file.", icon="🚨")
        elif (
            st.session_state.mode == "YouTube or link to an audio file"
            and isinstance(data_input, str)
            and not data_input.strip()
        ):
            st.error("Enter an audio file link.", icon="🚨")
        else:
            download(url=data_input)
            process_transcription()
    except Exception as e:
        st.error("Repeat attempt! An error has occurred.", icon="🚨")
        st.write(e)
    finally:
        clean_up()
