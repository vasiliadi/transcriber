import streamlit as st

from config import (
    WHISPER_DIARIZATION,
    INCREDIBLY_FAST_WHISPER,
    WHISPER,
)
from utils import download, clean_up
from transcription import process_transcription
from summary import process_summary


# Initialization
if "mode" not in st.session_state:
    st.session_state.mode = "YouTube or link to an audio file"
    st.session_state.language = None
    st.session_state.model_name = INCREDIBLY_FAST_WHISPER
    st.session_state.model_name_variant = INCREDIBLY_FAST_WHISPER
    st.session_state.summary_prompt = (
        "Listen carefully to the following audio file. Provide a detailed summary."
    )
    st.session_state.post_processing = True
    st.session_state.diarization = True
    st.session_state.speaker_identification = True
    st.session_state.raw_json = False
    st.session_state.tts = False
    st.session_state.tts_model = "ElevenLabs"
    st.session_state.transcription_for_summary = True


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
        type=["wav", "mp3", "aiff", "aac", "ogg", "flac"],
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

summary = st.checkbox("Generate summary", value=True)

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
            index=1,  # change if default value (st.session_state.model_name) has changed
            key="model_name",
            horizontal=False,
            disabled=summary,
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
    st.checkbox(
        "Use transcription for summary (in case of failure without)",
        disabled=not summary,
        key="transcription_for_summary",
        value=True,
    )
    text_to_speech = st.checkbox(
        "Enable Text to Speech Player", disabled=not summary, key="tts"
    )
    st.radio(
        label="Text-To-Speech engine",
        options=["ElevenLabs", "OpenAI"],
        index=0,
        key="tts_model",
        disabled=not text_to_speech,
    )
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
            download(input=data_input, mode=st.session_state.mode)
            if summary:
                process_summary()
            else:
                process_transcription()
    except Exception as e:
        st.error("Repeat attempt! An error has occurred.", icon="🚨")
        st.write(e)
    finally:
        clean_up()
