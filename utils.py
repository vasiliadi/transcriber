import streamlit as st
import os
import subprocess
from yt_dlp import YoutubeDL
from bs4 import BeautifulSoup
import requests

from config import AUDIO_FILE_NAME, CONVERTED_FILE_NAME, GENERATED_FILE_NAME, proxy


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


def download(input, mode):
    with st.spinner("Uploading the file to the server..."):
        if mode == "Uploaded file":
            with open(AUDIO_FILE_NAME, "wb") as f:
                f.write(input.getbuffer())
        if mode == "YouTube or link to an audio file":
            if input.startswith("https://www.youtube.com/") or input.startswith(
                "https://youtu.be/"
            ):
                ydl_opts = {
                    "format": "worstaudio",
                    "outtmpl": "audio",
                    "proxy": proxy,
                    "postprocessors": [
                        {  # Extract audio using ffmpeg
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                        }
                    ],
                }
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(input)
            else:
                if input.startswith("https://castro.fm/episode/"):
                    input = BeautifulSoup(
                        requests.get(
                            requests.utils.requote_uri(input), verify=True
                        ).content,
                        "html.parser",
                    ).source.get("src")
                downloaded_file = requests.get(
                    requests.utils.requote_uri(input), verify=True
                )
                with open(AUDIO_FILE_NAME, "wb") as f:
                    f.write(downloaded_file.content)


def clean_up():
    if os.path.isfile(CONVERTED_FILE_NAME):
        os.remove(CONVERTED_FILE_NAME)
    if os.path.isfile(AUDIO_FILE_NAME):
        os.remove(AUDIO_FILE_NAME)
    if os.path.isfile(GENERATED_FILE_NAME):
        os.remove(GENERATED_FILE_NAME)


@st.cache_data(show_spinner=False)
def convert_to_minutes(seconds):
    minutes, seconds = divmod(float(seconds), 60)
    return f"{int(minutes)}:{int(seconds):02d}"
