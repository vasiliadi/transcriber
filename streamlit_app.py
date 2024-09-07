import streamlit as st
import os
import subprocess
import time
import json
import google.generativeai as genai
from google.api_core import retry
import replicate
import requests
from yt_dlp import YoutubeDL
from bs4 import BeautifulSoup
from elevenlabs.client import ElevenLabs

# Google Gemini config
gemini_api_key = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=gemini_api_key)
generation_config = {"max_output_tokens": 8192}
gemini_safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]
pro_model = genai.GenerativeModel(
    "models/gemini-1.5-pro",
    generation_config=generation_config,
    safety_settings=gemini_safety_settings,
)
flash_model = genai.GenerativeModel(
    "models/gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=gemini_safety_settings,
)

# Replicate.com config
replicate_api_token = os.environ["REPLICATE_API_TOKEN"]
replicate_client = replicate.Client(api_token=replicate_api_token)

# HuggingFace.co config
try:
    hf_access_token = os.environ["HF_ACCESS_TOKEN"]
except KeyError:
    pass

# ElevenLabs.io config
try:
    elevenlabs_api_key = os.environ["ELEVENLABS_API_KEY"]
except KeyError:
    pass

# File names
AUDIO_FILE_NAME = "audio.mp3"
CONVERTED_FILE_NAME = "audio.ogg"

# Initialization
if "mode" not in st.session_state:
    st.session_state.mode = "YouTube or link to an audio file"
    st.session_state.language = None
    st.session_state.model_name = "incredibly-fast-whisper"
    st.session_state.summary_prompt = (
        "Listen carefully to the following audio file. Provide a detailed summary."
    )
    st.session_state.post_processing = True
    st.session_state.diarization = True
    st.session_state.speaker_identification = True
    st.session_state.raw_json = False
    st.session_state.tts = False


# Functions
def download(mode=st.session_state.mode):
    match mode:
        case "Uploaded file":
            with open(AUDIO_FILE_NAME, "wb") as f:
                f.write(uploaded_file.getbuffer())

        case "YouTube or link to an audio file":
            if url.startswith("https://www.youtube.com/") or url.startswith(
                "https://youtu.be/"
            ):
                ydl_opts = {
                    "format": "worstaudio",
                    "outtmpl": "audio",
                    "postprocessors": [
                        {  # Extract audio using ffmpeg
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                        }
                    ],
                }
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(url)
            else:
                downloaded_file = requests.get(requests.utils.requote_uri(url))
                with open(AUDIO_FILE_NAME, "wb") as f:
                    f.write(downloaded_file.content)


def compress_audio(
    audio_file_name=AUDIO_FILE_NAME, converted_file_name=CONVERTED_FILE_NAME
):
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                audio_file_name,
                "-vn",
                "-ac",
                "1",
                "-c:a",
                "libopus",
                "-b:a",
                "16k",  # 12k works well too
                converted_file_name,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        st.error("Check uploaded file 👀", icon="🚨")
        st.write(e.stderr)
        st.stop()


@retry.Retry(predicate=retry.if_transient_error)
def summarize(audio_file_name=AUDIO_FILE_NAME, prompt=st.session_state.summary_prompt):
    audio_file = genai.upload_file(audio_file_name)
    response = pro_model.generate_content([prompt, audio_file])
    genai.delete_file(audio_file.name)
    summary = response.text.replace("$", "\$")
    return summary


@retry.Retry(predicate=retry.if_transient_error)
def correct_transcription(transcription):
    if st.session_state.post_processing:
        prompt = f"Correct any spelling discrepancies in the transcribed text. Split text by speaker. Only add necessary punctuation such as periods, commas, and capitalization, and use only the context provided: <transcribed_text>{transcription}</transcribed_text>"
        corrected_transcription = flash_model.generate_content(prompt).text
    else:
        corrected_transcription = transcription
    return corrected_transcription


def transcribe(model_name=st.session_state.model_name):
    match model_name:
        case "whisper-diarization":
            latest_model_version = (
                replicate_client.models.get("thomasmol/whisper-diarization")
                .versions.list()[0]
                .id
            )
            with open(CONVERTED_FILE_NAME, "rb") as audio:
                transcription = replicate_client.run(
                    f"thomasmol/whisper-diarization:{latest_model_version}",
                    input={"file": audio, "transcript_output_format": "segments_only"},
                )
                return transcription

        case "incredibly-fast-whisper":
            latest_model_version = (
                replicate_client.models.get("vaibhavs10/incredibly-fast-whisper")
                .versions.list()[0]
                .id
            )

            with open(CONVERTED_FILE_NAME, "rb") as audio:
                if st.session_state.diarization:
                    try:
                        if hf_access_token is None:
                            pass
                    except NameError:
                        st.error(
                            "HF_ACCESS_TOKEN is not provided. Disable diarization or provide HF_ACCESS_TOKEN. Or switch the model",
                            icon="🚨",
                        )
                        st.stop()
                    try:
                        transcription = replicate.run(
                            f"vaibhavs10/incredibly-fast-whisper:{latest_model_version}",
                            input={
                                "audio": audio,
                                "hf_token": hf_access_token,
                                "diarise_audio": True,
                            },
                        )
                    except:
                        st.error("Model error 😫 Try to switch the model 👍", icon="🚨")
                        st.stop()

                    def detected_num_speakers(transcription):
                        speakers = [i["speaker"] for i in transcription[0:-1]]
                        return len(set(speakers))

                    output = []
                    current_group = {
                        "start": str(transcription[0]["timestamp"][0]),
                        "end": str(transcription[0]["timestamp"][1]),
                        "speaker": transcription[0]["speaker"],
                        "text": transcription[0]["text"],
                    }

                    for i in range(1, len(transcription[0:-1])):
                        time_gap = (
                            transcription[i]["timestamp"][0]
                            - transcription[i - 1]["timestamp"][1]
                        )
                        if (
                            transcription[i]["speaker"]
                            == transcription[i - 1]["speaker"]
                            and time_gap <= 2
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

                    transcription = {
                        "num_speakers": detected_num_speakers(transcription),
                        "segments": output,
                    }

                if not st.session_state.diarization:
                    transcription = replicate.run(
                        f"vaibhavs10/incredibly-fast-whisper:{latest_model_version}",
                        input={
                            "audio": audio,
                        },
                    )
                    transcription = {
                        "num_speakers": 0,
                        "segments": correct_transcription(transcription["text"]),
                    }

                return transcription

        case "whisper":
            latest_model_version = (
                replicate_client.models.get("openai/whisper").versions.list()[0].id
            )
            with open(CONVERTED_FILE_NAME, "rb") as audio:
                transcription = replicate_client.run(
                    f"openai/whisper:{latest_model_version}",
                    input={"audio": audio},
                )

                transcription = {
                    "num_speakers": 0,
                    "segments": correct_transcription(transcription["transcription"]),
                }

                return transcription

        case _:
            st.error("Model not found 🫴")
            st.stop()


@retry.Retry(predicate=retry.if_transient_error)
def translate(
    text, target_language=st.session_state.language, chunks=False, sleep_time=30
):
    prompt = f"Translate input text to {target_language}. Return only translated text: <input_text>{text}</input_text>"
    if target_language != None:
        try:
            if chunks:
                translation = flash_model.generate_content(prompt)
                time.sleep(
                    sleep_time
                )  # 2 queries per minute for Gemini-1.5-pro and 15 for Gemini-1.5-flash https://ai.google.dev/gemini-api/docs/models/gemini#model-variations
                return translation.text
            else:
                translation = flash_model.generate_content(prompt)
                return translation.text
        except ValueError:
            st.error(
                "The translator thinks the content is unsafe and can't return the translation 🙈",
                icon="🚨",
            )
            st.stop()
    else:
        return text


@retry.Retry(predicate=retry.if_transient_error)
def identify_speakers(transcription):
    prompt = (
        f'Identify speakers names and replace "SPEAKER_" with identified name in this json <transcribed_json>{transcription}</transcribed_json>. '
        + """If you didnt identify names return the same name as was provided <example_return_without_identification>{"SPEAKER_00":"SPEAKER_00"}</example_return_without_identification>
        Return using this JSON schema, include only unique records:
        
        original_speaker as key: str
        detected_speaker as value: str
        Return: dict[str, str]
        """
    )
    names = flash_model.generate_content(
        prompt,
        generation_config={
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        },
    )
    return json.loads(names.text)


def convert_to_minutes(seconds):
    minutes, seconds = divmod(float(seconds), 60)
    return f"{int(minutes)}:{int(seconds):02d}"


def clean_up():
    if os.path.isfile(CONVERTED_FILE_NAME):
        os.remove(CONVERTED_FILE_NAME)
    if os.path.isfile(AUDIO_FILE_NAME):
        os.remove(AUDIO_FILE_NAME)


def generate_speech(text):
    try:
        if elevenlabs_api_key is None:
            pass
    except NameError:
        st.error(
            "ELEVENLABS_API_KEY is not provided. Disable Text to Speech Player or provide ELEVENLABS_API_KEY",
            icon="🚨",
        )
        st.stop()
    elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
    generated_audio = elevenlabs_client.generate(
        text=text,
        model="eleven_turbo_v2_5",
    )
    return b"".join(generated_audio)


def get_printable_results():
    with st.spinner("Uploading the file to the server..."):
        download()
    if summary:
        if not st.session_state.tts:
            st.audio(AUDIO_FILE_NAME)
        with st.spinner("Summarizing..."):
            summary_results = summarize()
            summary_results = translate(summary_results)
            st.markdown(summary_results)
        if st.session_state.tts:
            with st.spinner("Generating speech..."):
                speech = generate_speech(summary_results)
                st.audio(speech)
    else:
        with st.spinner("Compressing file..."):
            compress_audio()
        st.audio(CONVERTED_FILE_NAME)
        with st.spinner("Transcribing..."):
            transcription = transcribe(model_name=st.session_state.model_name)
            if transcription["num_speakers"] == 1:
                for segment in transcription["segments"]:
                    text = str(segment["text"]).replace("$", "\$")
                    st.markdown(
                        f"**{convert_to_minutes(segment['start'])}:** {translate(text, chunks=True, sleep_time=5)}"
                    )
            elif (
                transcription["num_speakers"] == 0
            ):  # for incredibly-fast-whisper (without diarization) and openai/whisper
                st.markdown(translate(transcription["segments"]))
            else:
                if st.session_state.speaker_identification:
                    names = identify_speakers(transcription)
                else:
                    names = {}
                    for speaker in transcription["segments"]:
                        names[speaker["speaker"]] = speaker["speaker"]
                for segment in transcription["segments"]:
                    text = str(segment["text"]).replace("$", "\$")
                    st.markdown(
                        f"**{convert_to_minutes(segment['start'])} - {str(segment['speaker']).replace(segment['speaker'], names[segment['speaker']])}:** {translate(text, chunks=True, sleep_time=5)}"
                    )
            if st.session_state.raw_json:
                last_prediction_id = replicate_client.predictions.list().results[0].id
                data = json.dumps(
                    replicate_client.predictions.get(last_prediction_id).output
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
    uploaded_file = st.file_uploader(
        "Choose a file:",
        type=["wav", "mp3", "aiff", "aac", "ogg", "flac"],
    )
if st.session_state.mode == "YouTube or link to an audio file":
    url = st.text_input(
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

summary = st.checkbox("Generate summary (without transcription)")

advanced = st.toggle("Advanced settings")

if advanced:
    st.text("Model settings")
    col1_model_selection, col2_model_settings = st.columns(2)
    with col1_model_selection:
        st.radio(
            label="Select option",
            label_visibility="collapsed",
            options=["whisper-diarization", "incredibly-fast-whisper", "whisper"],
            captions=["best for dialogs", "best for speed", "best in accuracy"],
            index=1,  # change if default value (st.session_state.model_name) has changed
            key="model_name",
            horizontal=False,
            disabled=summary,
        )
    with col2_model_settings:
        if st.session_state.model_name == "whisper-diarization":
            st.checkbox(
                "Enable speaker identification",
                value=True,
                disabled=False,
                key="speaker_identification",
            )
        if st.session_state.model_name == "incredibly-fast-whisper":

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
        if st.session_state.model_name == "whisper":
            st.checkbox(
                "Enable post-processing",
                value=True,
                # disabled=summary,
                key="post_processing",
            )

    st.checkbox("Enable Raw JSON download", key="raw_json", disabled=summary)
    st.divider()

    st.text("Summarization settings")
    summarization_style = st.radio(
        label="Select prompt",
        label_visibility="collapsed",
        options=["Detailed", "Short", "Action points", "Explain like I am 5"],
        index=0,  # change if default value (st.session_state.summary_prompt) has changed
        disabled=not summary,
    )
    if summarization_style == "Detailed":
        st.session_state.summary_prompt = (
            "Listen carefully to the following audio file. Provide a detailed summary."
        )
    if summarization_style == "Short":
        st.session_state.summary_prompt = (
            "Listen carefully to the following audio file. Provide a short summary."
        )
    if summarization_style == "Action points":
        st.session_state.summary_prompt = "Listen carefully to the following audio file. Provide a bullet-point summary"
    if summarization_style == "Explain like I am 5":
        st.session_state.summary_prompt = "Listen carefully to the following audio file. Explain like I am 5 years old."
    st.checkbox("Enable Text to Speech Player", disabled=not summary, key="tts")
    st.divider()

go = st.button("Go")

# Data processing
if go:
    try:
        if st.session_state.mode == "Uploaded file":
            if uploaded_file is not None:
                get_printable_results()
            else:
                st.error("Upload an audio file.", icon="🚨")
        elif st.session_state.mode == "YouTube or link to an audio file":
            if len(url.strip()) != 0:
                if url.startswith("https://castro.fm/episode/"):
                    soup = BeautifulSoup(
                        requests.get(requests.utils.requote_uri(url)).content,
                        "html.parser",
                    )
                    url = soup.source.get("src")
                get_printable_results()
            else:
                st.error("Enter an audio file link.", icon="🚨")
    except Exception as e:
        st.error("Repeat attempt! An error has occurred.", icon="🚨")
        st.write(e)
    finally:
        clean_up()
