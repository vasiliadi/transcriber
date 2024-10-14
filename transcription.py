import streamlit as st
import time
import json
from google.api_core import retry
import httpx
from config import (
    replicate_client,
    flash_model,
    hf_access_token,
    CONVERTED_FILE_NAME,
    WHISPER_DIARIZATION,
    WHISPER,
    INCREDIBLY_FAST_WHISPER,
)
from utils import compress_audio, convert_to_minutes
from translate import translate


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


@st.cache_data(show_spinner=False)
@retry.Retry(predicate=retry.if_transient_error)
def correct_transcription(
    transcription, post_processing=st.session_state.post_processing
):
    if post_processing:
        prompt = f"Correct any spelling discrepancies in the transcribed text. Split text by speaker. Only add necessary punctuation such as periods, commas, and capitalization, and use only the context provided: <transcribed_text>{transcription}</transcribed_text>"
        return flash_model.generate_content(prompt).text
    return transcription


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
    return output


def process_whisper_diarization(audio_file_name=CONVERTED_FILE_NAME):
    with open(audio_file_name, "rb") as audio:
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
    with open(audio_file_name, "rb") as audio:
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
        except:
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
        return transcription


def process_whisper(audio_file_name=CONVERTED_FILE_NAME):
    with open(audio_file_name, "rb") as audio:
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

        return transcription


def transcribe(model_name=st.session_state.model_name):
    if model_name == WHISPER_DIARIZATION:
        return process_whisper_diarization()
    if model_name == INCREDIBLY_FAST_WHISPER:
        return process_incredibly_fast_whisper()
    if model_name == WHISPER:
        return process_whisper()


def process_transcription():
    with st.spinner("Compressing file..."):
        compress_audio()
    st.audio(CONVERTED_FILE_NAME)
    with st.spinner("Transcribing..."):
        transcription = transcribe(model_name=st.session_state.model_name)
        if transcription["num_speakers"] == 1:
            for segment in transcription["segments"]:
                text = str(segment["text"]).replace("$", "\$")
                st.markdown(
                    f"**{convert_to_minutes(segment['start'])}:** {translate(text, target_language=st.session_state.language, chunks=True, sleep_time=5)}"
                )
        elif (
            transcription["num_speakers"] == 0
        ):  # for incredibly-fast-whisper (without diarization) and openai/whisper
            st.markdown(translate(transcription["segments"]).replace("$", "\$"), target_language=st.session_state.language)
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
                    f"**{convert_to_minutes(segment['start'])} - {str(segment['speaker']).replace(segment['speaker'], names[segment['speaker']])}:** {translate(text, target_language=st.session_state.language, chunks=True, sleep_time=5)}"
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
