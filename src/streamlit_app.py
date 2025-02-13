import json
import os
import subprocess
import time
from pathlib import Path
from textwrap import dedent

import httpx
import replicate
import requests
import streamlit as st
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from yt_dlp import YoutubeDL

# Google Gemini config
gemini_api_key = os.environ["GEMINI_API_KEY"]
gemini_client = genai.Client(api_key=gemini_api_key)
GEMINI_MODEL = "models/gemini-1.5-flash-latest"
SAFETY_SETTINGS = [
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT",
        threshold="BLOCK_NONE",
    ),
]


# Replicate.com config
replicate_api_token = os.environ["REPLICATE_API_TOKEN"]
replicate_client = replicate.Client(
    api_token=replicate_api_token,
)

# HuggingFace.co config
hf_access_token = os.environ["HF_ACCESS_TOKEN"]

# Proxy config
proxy = os.environ["PROXY"]

# Constants
AUDIO_FILE_NAME = "audio.mp3"
CONVERTED_FILE_NAME = "audio.ogg"
WHISPER_DIARIZATION = "thomasmol/whisper-diarization"
INCREDIBLY_FAST_WHISPER = "vaibhavs10/incredibly-fast-whisper"
WHISPER = "openai/whisper"

# Headers for requests https://www.whatismybrowser.com/guides/the-latest-user-agent/chrome
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
}

# Initialization
if "mode" not in st.session_state:
    st.session_state.mode = "YouTube or link to an audio file"
    st.session_state.language = None
    st.session_state.model_name = WHISPER_DIARIZATION
    st.session_state.model_name_variant = INCREDIBLY_FAST_WHISPER
    st.session_state.post_processing = True
    st.session_state.diarization = True
    st.session_state.speaker_identification = True
    st.session_state.raw_json = False


# Functions
def download(url, mode=st.session_state.mode):
    with st.spinner("Uploading the file to the server..."):
        if mode == "Uploaded file":
            with Path(AUDIO_FILE_NAME).open("wb") as f:
                f.write(url.getbuffer())
        if mode == "YouTube or link to an audio file":
            if url.startswith(("https://www.youtube.com/", "https://youtu.be/")):
                ydl_opts = {
                    "format": "worstaudio",
                    "outtmpl": "audio",
                    "proxy": proxy,
                    "postprocessors": [
                        {  # Extract audio using ffmpeg
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                        },
                    ],
                }
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(url)
            else:
                if url.startswith("https://castro.fm/episode/"):
                    url = BeautifulSoup(
                        requests.get(
                            requests.utils.requote_uri(url),
                            headers=headers,
                            verify=True,
                            timeout=120,
                        ).content,
                        "html.parser",
                    ).source.get("src")
                downloaded_file = requests.get(
                    requests.utils.requote_uri(url),
                    verify=True,
                    timeout=120,
                )
                with Path(AUDIO_FILE_NAME).open("wb") as f:
                    f.write(downloaded_file.content)


def compress_audio(
    audio_file_name=AUDIO_FILE_NAME,
    converted_file_name=CONVERTED_FILE_NAME,
):
    try:
        subprocess.run(
            [
                "ffmpeg",  # /usr/bin/ffmpeg
                "-y",
                "-i",
                audio_file_name,
                "-vn",
                "-ac",
                "1",
                "-c:a",
                "libopus",
                "-b:a",
                "16k",
                converted_file_name,
            ],
            check=True,
            capture_output=False,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        st.error("Check uploaded file 👀", icon="🚨")
        st.write(e.stderr)
        st.stop()


@st.cache_data(show_spinner=False)
def correct_transcription(
    transcription,
    post_processing=st.session_state.post_processing,
):
    if post_processing:
        prompt = f"Correct any spelling discrepancies in the transcribed text. Split text by speaker. Only add necessary punctuation such as periods, commas, and capitalization, and use only the context provided: <transcribed_text>{transcription}</transcribed_text>"
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=None,
                safety_settings=SAFETY_SETTINGS,
                response_mime_type="text/plain",
                max_output_tokens=8192,
            ),
        )
        return response.text
    return transcription


def get_latest_model_version(model_name):
    return replicate_client.models.get(model_name).versions.list()[0].id


def get_latest_prediction_output(sleep_time=10):
    transcription = None
    while transcription is None:
        try:
            transcription = replicate_client.predictions.list().results[0].output
        except (TypeError, httpx.ReadTimeout):
            time.sleep(sleep_time)
    return transcription


@st.cache_data(show_spinner=False)
def detected_num_speakers(transcription):  # for incredibly-fast-whisper only
    speakers = [i["speaker"] for i in transcription[0:-1]]
    return len(set(speakers))


@st.cache_data(show_spinner=False)
def process_diarization_for_incredibly_fast_whisper(
    transcription,
):  # for incredibly-fast-whisper only
    output = []
    current_group = {
        "start": str(transcription[0]["timestamp"][0]),
        "end": str(transcription[0]["timestamp"][1]),
        "speaker": transcription[0]["speaker"],
        "text": transcription[0]["text"],
    }

    for i in range(1, len(transcription[0:-1])):
        time_gap = (
            transcription[i]["timestamp"][0] - transcription[i - 1]["timestamp"][1]
        )
        if (
            transcription[i]["speaker"] == transcription[i - 1]["speaker"]
            and time_gap <= 2  # noqa: PLR2004
        ):
            current_group["end"] = str(transcription[i]["timestamp"][1])
            current_group["text"] += " " + transcription[i]["text"]
        else:
            output.append(current_group)

            current_group = {
                "start": str(transcription[i]["timestamp"][0]),
                "end": str(transcription[i]["timestamp"][1]),
                "speaker": transcription[i]["speaker"],
                "text": transcription[i]["text"],
            }

    output.append(current_group)
    return output


def process_whisper_diarization(audio_file_name=CONVERTED_FILE_NAME):
    with Path(audio_file_name).open("rb") as audio:
        try:
            transcription = replicate_client.run(
                f"{WHISPER_DIARIZATION}:{get_latest_model_version(WHISPER_DIARIZATION)}",
                input={"file": audio, "transcript_output_format": "segments_only"},
            )
        except httpx.ReadTimeout:
            transcription = get_latest_prediction_output()
        return transcription


def process_incredibly_fast_whisper(
    audio_file_name=CONVERTED_FILE_NAME,
    diarization=st.session_state.diarization,
    variant=st.session_state.model_name_variant,
    post_processing=st.session_state.post_processing,
):
    with Path(audio_file_name).open("rb") as audio:
        try:
            transcription = replicate_client.run(
                f"{variant}:{get_latest_model_version(variant)}",
                input={
                    "audio": audio,
                    "hf_token": hf_access_token,
                    "diarise_audio": diarization,
                },
                use_file_output=False,
            )
        except httpx.ReadTimeout:
            transcription = get_latest_prediction_output()
        except:  # noqa: E722
            st.error("Model error 😫 Try to switch the model 👍", icon="🚨")
            st.stop()

        transcription = {
            "num_speakers": detected_num_speakers(transcription) if diarization else 0,
            "segments": (
                process_diarization_for_incredibly_fast_whisper(transcription)
                if diarization
                else correct_transcription(
                    transcription["text"],
                    post_processing=post_processing,
                )
            ),
        }
        return transcription  # noqa: RET504


def process_whisper(audio_file_name=CONVERTED_FILE_NAME):
    with Path(audio_file_name).open("rb") as audio:
        try:
            transcription = replicate_client.run(
                f"{WHISPER}:{get_latest_model_version(WHISPER)}",
                input={"audio": audio},
            )
        except httpx.ReadTimeout:
            transcription = get_latest_prediction_output()

        transcription = {
            "num_speakers": 0,
            "segments": correct_transcription(transcription["transcription"]),
        }

        return transcription  # noqa: RET504


def transcribe(model_name=st.session_state.model_name):
    if model_name == WHISPER_DIARIZATION:
        return process_whisper_diarization()
    if model_name == INCREDIBLY_FAST_WHISPER:
        return process_incredibly_fast_whisper()
    if model_name == WHISPER:
        return process_whisper()
    return None


@st.cache_data(show_spinner=False)
def translate(
    text,
    target_language=st.session_state.language,
    chunks=False,
    sleep_time=30,
):
    if target_language is None:
        return text
    prompt = f"Translate input text to {target_language}. Return only translated text: <input_text>{text}</input_text>"
    try:
        translation = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=dedent("""
                    You are a language model specializing in accurate, context-sensitive translations.
                    Translate each text with precise meaning and maintain the original tone and style.
                    Adapt idioms, cultural references, and metaphors for naturalness in the target language,
                    while providing brief explanations directly in the text, if necessary.
                    Avoid literal translations unless they are essential.
                    When terms have multiple meanings, use the context to select the best fit.
                    Do not translate proper nouns or technical terms unless widely recognized equivalents exist.
                    Ensure consistent terminology, especially for technical or specialized language.
                    Use polite, respectful language, adjusting formality as appropriate for the text type (e.g., legal, business, casual).
                    I want you to only reply the translation, do not write notes or explanations.
                    """).strip(),
                safety_settings=SAFETY_SETTINGS,
                response_mime_type="text/plain",
                max_output_tokens=8192,
            ),
        )
        if chunks:
            time.sleep(
                sleep_time,
            )  # 2 queries per minute for Gemini-1.5-pro and 15 for Gemini-1.5-flash https://ai.google.dev/gemini-api/docs/models/gemini#model-variations
        return translation.text
    except ValueError:
        st.error(
            "The translator thinks the content is unsafe and can't return the translation 🙈",
            icon="🚨",
        )
        st.stop()


@st.cache_data(show_spinner=False)
def identify_speakers(transcription):
    prompt = (
        f'Identify speakers names and replace "SPEAKER_" with identified name in this json <transcribed_json>{transcription}</transcribed_json>. '
        """If you didnt identify names return the same name as was provided <example_return_without_identification>{"SPEAKER_00":"SPEAKER_00"}</example_return_without_identification>
        Return using this JSON schema, include only unique records:

        original_speaker as key: str
        detected_speaker as value: str
        Return: dict[str, str]
        """
    )
    names = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=None,
            safety_settings=SAFETY_SETTINGS,
            response_mime_type="application/json",
            max_output_tokens=8192,
        ),
    )
    return json.loads(names.text)


@st.cache_data(show_spinner=False)
def convert_to_minutes(seconds):
    minutes, seconds = divmod(float(seconds), 60)
    return f"{int(minutes)}:{int(seconds):02d}"


def clean_up():
    if Path(CONVERTED_FILE_NAME).is_file():
        Path(CONVERTED_FILE_NAME).unlink()
    if Path(AUDIO_FILE_NAME).is_file():
        Path(AUDIO_FILE_NAME).unlink()


def process_transcription():
    with st.spinner("Compressing file..."):
        compress_audio()
    st.audio(CONVERTED_FILE_NAME)
    with st.spinner("Transcribing..."):
        transcription = transcribe(model_name=st.session_state.model_name)
        if transcription["num_speakers"] == 1:
            for segment in transcription["segments"]:
                text = str(segment["text"]).replace("$", r"\$")
                st.markdown(
                    f"**{convert_to_minutes(segment['start'])}:** {translate(text, chunks=True, sleep_time=5)}",
                )
        elif (
            transcription["num_speakers"] == 0
        ):  # for incredibly-fast-whisper (without diarization) and openai/whisper
            st.markdown(translate(transcription["segments"]).replace("$", r"\$"))
        else:
            if st.session_state.speaker_identification:
                names = identify_speakers(transcription)
            else:
                names = {}
                for speaker in transcription["segments"]:
                    names[speaker["speaker"]] = speaker["speaker"]
            for segment in transcription["segments"]:
                text = str(segment["text"]).replace("$", r"\$")
                st.markdown(
                    f"**{convert_to_minutes(segment['start'])} - {str(segment['speaker']).replace(segment['speaker'], names[segment['speaker']])}:** {translate(text, chunks=True, sleep_time=5)}",
                )
        if st.session_state.raw_json:
            last_prediction_id = replicate_client.predictions.list().results[0].id
            data = json.dumps(
                replicate_client.predictions.get(last_prediction_id).output,
            )
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

if st.session_state.mode == "Uploaded file":
    data_input = st.file_uploader(
        "Choose a file:",
        # https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/audio-understanding#audio-requirements
        type=["wav", "mp3", "aiff", "aac", "ogg", "flac", "m4a"],
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
            options=[WHISPER_DIARIZATION, INCREDIBLY_FAST_WHISPER, WHISPER],
            captions=["best for dialogs", "best for speed", "best in accuracy"],
            index=0,  # change if default value (st.session_state.model_name) has changed
            key="model_name",
            horizontal=False,
        )
    with col2_model_settings:
        if st.session_state.model_name == WHISPER_DIARIZATION:
            st.checkbox(
                "Enable speaker identification",
                value=True,
                disabled=False,
                key="speaker_identification",
            )
        if st.session_state.model_name == INCREDIBLY_FAST_WHISPER:
            st.radio(
                label="Model version",
                captions=["best for speed", "best for fast diarization"],
                options=[
                    "vaibhavs10/incredibly-fast-whisper",
                    "nicknaskida/incredibly-fast-whisper",
                ],
                index=0,
                key="model_name_variant",
            )
            st.divider()

            def change_state():
                if not st.session_state.diarization:
                    st.session_state.speaker_identification = False
                if st.session_state.diarization:
                    st.session_state.post_processing = False

            st.checkbox(
                "Enable diarization",
                value=True,
                disabled=False,
                key="diarization",
                on_change=change_state(),
            )
            st.checkbox(
                "Enable speaker identification",
                value=True,
                disabled=not st.session_state.diarization,
                key="speaker_identification",
            )
            st.checkbox(
                "Enable post-processing",
                value=False,
                disabled=st.session_state.diarization,
                key="post_processing",
            )
        if st.session_state.model_name == WHISPER:
            st.checkbox(
                "Enable post-processing",
                value=True,
                key="post_processing",
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
