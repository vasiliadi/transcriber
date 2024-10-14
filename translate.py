import streamlit as st
import time
from google.api_core import retry

from config import flash_model


@st.cache_data(show_spinner=False)
@retry.Retry(predicate=retry.if_transient_error)
def translate(
    text, target_language, chunks=False, sleep_time=30
):
    if target_language is None:
        return text
    prompt = f"Translate input text to {target_language}. Return only translated text: <input_text>{text}</input_text>"
    try:
        translation = flash_model.generate_content(prompt)
        if chunks:
            time.sleep(
                sleep_time
            )  # 2 queries per minute for Gemini-1.5-pro and 15 for Gemini-1.5-flash https://ai.google.dev/gemini-api/docs/models/gemini#model-variations
        return translation.text
    except ValueError:
        st.error(
            "The translator thinks the content is unsafe and can't return the translation 🙈",
            icon="🚨",
        )
        st.stop()
