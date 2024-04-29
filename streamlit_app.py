import streamlit as st
import os
import subprocess
import time
import json
import google.generativeai as genai
import replicate
import requests
from pytube import YouTube

# Google Gemini config
gemini_api_key = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=gemini_api_key)
generation_config = {
    #   "temperature": 1,
    #   "top_p": 0.95,
    #   "top_k": 0,
    "max_output_tokens": 8192,
}
gemini_safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]
model = genai.GenerativeModel(
    "models/gemini-1.5-pro-latest",
    generation_config=generation_config,
    safety_settings=gemini_safety_settings,
)

# Replicate.com config
replicate_api_token = os.environ["REPLICATE_API_TOKEN"]
replicate_client = replicate.Client(api_token=replicate_api_token)

# File names
audio_file_name = "audio.mp3"
converted_file_name = "audio.ogg"

# Initialization
if "mode" not in st.session_state:
    st.session_state.mode = "Uploaded file"
    st.session_state.language = None
    st.session_state.model_name = "Balanced"


# Functions
def download(mode=st.session_state.mode):
    match mode:
        case "Uploaded file":
            with open(audio_file_name, "wb") as f:
                f.write(uploaded_file.getbuffer())
        case "YouTube link":
            YouTube(yt_url).streams.filter(only_audio=True).order_by(
                "abr"
            ).asc().first().download(filename=audio_file_name)
        case "Audio file link":
            downloaded_file = requests.get(audio_link)
            with open(audio_file_name, "wb") as f:
                f.write(downloaded_file.content)


def compress_audio(audio_file_name=audio_file_name):
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
                "16k", # 12k works well too
                converted_file_name,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        st.error("Check uploaded file.", icon="🚨")
        st.write(e.stderr)
        st.stop()


def summarize(audio_file_name=audio_file_name):
    prompt = "Listen carefully to the following audio file. Provide a detailed summary."
    audio_file = genai.upload_file(audio_file_name)
    response = model.generate_content([prompt, audio_file])
    genai.delete_file(audio_file.name)
    return response.text


def transcribe(model_name=st.session_state.model_name):
    match model_name:
        case "Balanced":
            with open(converted_file_name, "rb") as audio:
                transcription = replicate_client.run(
                    "thomasmol/whisper-diarization:3ff22700b10e9c888e72235131e10c0a8427cd79e750bc42e4c035be2121796b",
                    input={"file": audio, "transcript_output_format": "segments_only"},
                )
                return transcription
        case _:
            st.error("Model not found")
            st.stop()


def translate(
    text, target_language=st.session_state.language, chunks=False, sleep_time=30
):
    prompt = f"Translate input text to {target_language}. Return only translated text: <input_text>{text}</input_text>"
    try:
        if chunks:
            translation = model.generate_content(prompt)
            time.sleep(
                sleep_time
            )  # 2 queries per minute https://ai.google.dev/gemini-api/docs/models/gemini#model-variations
            return translation.text
        else:
            translation = model.generate_content(prompt)
            return translation.text
    except ValueError:
        st.error(
            "The translator thinks the content is unsafe and can't return the translation 🙈",
            icon="🚨",
        )
        st.stop()


def identify_speakers(transcription):
    prompt = (
        'Identify speakers names and replace "speaker" with identified name. For exmple <example_json>{"avg_logprob": -0.1729651133334914, "end": "238.19", "speaker": "SPEAKER_00", "start": "15.34", "text": "About six years ago."}</example_json>, return only json as example <example_return>{"SPEAKER_00":"Dave"}</example_return>. If you didnt identify names return the same name as was provided <example_return_without_identification>{"SPEAKER_00":"SPEAKER_00"}</example_return_without_identification>'
        + f"Do it with this json <transcribed_json>{transcription}</transcribed_json>"
    )
    names = model.generate_content(prompt)
    names_json = json.loads(names.text.split("```json")[1].split("```")[0])
    return names_json


def convert_to_minutes(seconds):
    minutes, seconds = divmod(float(seconds), 60)
    return f"{int(minutes)}:{int(seconds):02d}"


def clean_up():
    if os.path.isfile(converted_file_name):
        os.remove(converted_file_name)
    if os.path.isfile(audio_file_name):
        os.remove(audio_file_name)


def get_printable_results():
    with st.spinner("Uploading the file to the server..."):
        download()
    if summary:
        st.audio(audio_file_name)
        with st.spinner("Summarizing..."):
            summary_results = summarize()
            if target_language != None:
                translation_results = translate(summary_results)
                st.markdown(translation_results)
            else:
                st.markdown(summary_results)
    else:
        with st.spinner("Compressing file..."):
            compress_audio()
        st.audio(converted_file_name)
        with st.spinner("Transcribing..."):
            transcription = transcribe()
            if transcription["num_speakers"] == 1:
                if target_language != None:
                    for segment in transcription["segments"]:
                        text = str(segment['text']).replace("$", "\$")
                        st.markdown(
                            f"**{convert_to_minutes(segment['start'])}:** {translate(text, chunks=True, sleep_time=30)}"
                        )
                else:
                    for segment in transcription["segments"]:
                        text = str(segment['text']).replace("$", "\$")
                        st.markdown(
                            f"**{convert_to_minutes(segment['start'])}:** {text}"
                        )
            else:
                names = identify_speakers(transcription)
                if target_language != None:
                    for segment in transcription["segments"]:
                        text = str(segment['text']).replace("$", "\$")
                        st.markdown(
                            f"**{convert_to_minutes(segment['start'])} - {str(segment['speaker']).replace(segment['speaker'], names[segment['speaker']])}:** {translate(text, chunks=True, sleep_time=30)}"
                        )
                else:
                    for segment in transcription["segments"]:
                        text = str(segment['text']).replace("$", "\$")
                        st.markdown(
                            f"**{convert_to_minutes(segment['start'])} - {str(segment['speaker']).replace(segment['speaker'], names[segment['speaker']])}:** {text}"
                        )
    clean_up()


# Frontend
st.title("Transcribe & Translate Audio Files")

st.radio(
    label="Choose what to transcribe:",
    options=["Uploaded file", "YouTube link", "Audio file link"],
    key="mode",
)

if st.session_state.mode == "Uploaded file":
    uploaded_file = st.file_uploader(
        "Choose a file:",
        type=["wav", "mp3", "aiff", "aac", "ogg", "flac"],
    )
elif st.session_state.mode == "YouTube link":
    yt_url = st.text_input(
        label="Enter YouTube URL:",
        placeholder="https://www.youtube.com/watch?v=z7-fPFtgRE4",
    )
elif st.session_state.mode == "Audio file link":
    audio_link = st.text_input(
        label="Enter the link to the file:",
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

go = st.button("Go")

# Data processing
if go:
    if st.session_state.mode == "Uploaded file":
        if uploaded_file is not None:
            get_printable_results()
        else:
            st.error("Upload an audio file.", icon="🚨")

    elif st.session_state.mode == "YouTube link":
        if len(yt_url.strip()) != 0:
            get_printable_results()
        else:
            st.error("Enter a YouTube link.", icon="🚨")

    elif st.session_state.mode == "Audio file link":
        if len(audio_link.strip()) != 0:
            get_printable_results()
        else:
            st.error("Enter an audio file link.", icon="🚨")
