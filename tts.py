import streamlit as st
import os
import time
from elevenlabs import save
from semantic_text_splitter import TextSplitter
from pydub import AudioSegment

from config import openai_client, elevenlabs_client, AI_CONFIG, GENERATED_FILE_NAME


def generate_opoenai_tts_audio(text, output_file_name, sleep_time=0):
    generated_audio = openai_client.audio.speech.create(
        model=AI_CONFIG["openai"]["tts_model"],
        voice=AI_CONFIG["openai"]["voice"],
        input=text,
    )
    generated_audio.write_to_file(output_file_name)
    time.sleep(sleep_time)


def generate_elevenlabs_tts_audio(text, output_file_name):
    generated_audio = elevenlabs_client.generate(
        text=text,
        model=AI_CONFIG["elevenlabs"]["tts_model"],
    )
    save(generated_audio, output_file_name)


def generate_speech(text):
    if st.session_state.tts_model == "ElevenLabs":
        generate_elevenlabs_tts_audio(text, GENERATED_FILE_NAME)
    if st.session_state.tts_model == "OpenAI":
        if len(text) > 4096:
            splitter = TextSplitter(4096)
            chunks = splitter.chunks(text)
            for i in range(len(chunks)):
                temp_file_name = f"part_{i}.mp3"
                generate_opoenai_tts_audio(
                    chunks[i], temp_file_name, sleep_time=2
                )  # https://platform.openai.com/docs/guides/rate-limits/usage-tiers
                locals()[f"sound{i}"] = AudioSegment.from_file(temp_file_name)
                if i == 0:
                    sounds = locals()[f"sound{i}"]
                if i > 0:
                    sounds += locals()[f"sound{i}"]
                if os.path.isfile(temp_file_name):
                    os.remove(temp_file_name)
            sounds.export(GENERATED_FILE_NAME, format="mp3")
        else:
            generate_opoenai_tts_audio(text, GENERATED_FILE_NAME)
