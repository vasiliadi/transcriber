import streamlit as st
import google.generativeai as genai
from google.api_core import retry, exceptions

from config import (
    pro_model,
    AUDIO_FILE_NAME,
    INCREDIBLY_FAST_WHISPER,
    GENERATED_FILE_NAME,
)
from utils import compress_audio
from transcription import process_incredibly_fast_whisper
from translate import translate
from tts import generate_speech


@st.cache_data(show_spinner=False)
@retry.Retry(predicate=retry.if_transient_error)
def summarize_with_transcription(transcription):
    prompt = (
        f"Read carefully transcription and provide a detailed summary: {transcription}"
    )
    response = pro_model.generate_content(prompt)
    return response.text.replace("$", r"\$")


@retry.Retry(predicate=retry.if_transient_error)
def summarize(
    audio_file_name=AUDIO_FILE_NAME,
    prompt=st.session_state.summary_prompt,
    transcription_for_summary=st.session_state.transcription_for_summary,
):
    try:
        audio_file = genai.upload_file(audio_file_name)
        response = pro_model.generate_content(
            [prompt, audio_file], request_options={"timeout": 120}
        )
        genai.delete_file(audio_file.name)
        return response.text.replace("$", r"\$")
    except (exceptions.RetryError, TimeoutError, exceptions.DeadlineExceeded):
        if transcription_for_summary:
            compress_audio()
            transcription = process_incredibly_fast_whisper(
                diarization=False,
                variant=INCREDIBLY_FAST_WHISPER,
                post_processing=False,
            )
            transcription = transcription["segments"]
            return summarize_with_transcription(transcription)
        raise Exception()


def process_summary():
    if not st.session_state.tts:
        st.audio(AUDIO_FILE_NAME)
    with st.spinner("Summarizing..."):
        summary_results = summarize()
        summary_results = translate(summary_results)
        st.markdown(summary_results)
    if st.session_state.tts:
        with st.spinner("Generating speech..."):
            generate_speech(summary_results)
            st.audio(GENERATED_FILE_NAME)
