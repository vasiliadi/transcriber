import os

import google.generativeai as genai
import replicate
from elevenlabs.client import ElevenLabs
from openai import OpenAI

AI_CONFIG = {
    "gemini": {
        "generation_config": {"max_output_tokens": 8192},
        "safety_settings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
        "pro_model": "models/gemini-1.5-pro-latest",
        "flash_model": "models/gemini-1.5-flash-latest",
    },
    "openai": {"tts_model": "tts-1", "voice": "alloy"},
    "elevenlabs": {"tts_model": "eleven_turbo_v2_5"},
}

# Google Gemini config
gemini_api_key = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=gemini_api_key)
pro_model = genai.GenerativeModel(
    AI_CONFIG["gemini"]["pro_model"],
    generation_config=AI_CONFIG["gemini"]["generation_config"],
    safety_settings=AI_CONFIG["gemini"]["safety_settings"],
)
flash_model = genai.GenerativeModel(
    AI_CONFIG["gemini"]["flash_model"],
    generation_config=AI_CONFIG["gemini"]["generation_config"],
    safety_settings=AI_CONFIG["gemini"]["safety_settings"],
)

# Replicate.com config
replicate_api_token = os.environ["REPLICATE_API_TOKEN"]
replicate_client = replicate.Client(
    api_token=replicate_api_token,
    # timeout=httpx.Timeout(None),
)

# HuggingFace.co config
hf_access_token = os.environ["HF_ACCESS_TOKEN"]

# ElevenLabs.io config
elevenlabs_api_key = os.environ["ELEVENLABS_API_KEY"]
elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)

# OpenAI config
openai_api_key = os.environ["OPENAI_API_KEY"]
openai_client = OpenAI(api_key=openai_api_key)

# Proxy config
proxy = os.environ["PROXY"]

# Constants
AUDIO_FILE_NAME = "audio.mp3"
CONVERTED_FILE_NAME = "audio.ogg"
GENERATED_FILE_NAME = "speech.mp3"
WHISPER_DIARIZATION = "thomasmol/whisper-diarization"
INCREDIBLY_FAST_WHISPER = "vaibhavs10/incredibly-fast-whisper"
WHISPER = "openai/whisper"