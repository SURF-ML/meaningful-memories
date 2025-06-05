import html
import os

import librosa
import soundfile as sf
from pydub import AudioSegment

import json


def get_cache_kwargs():
    cache_dir = "/projects/2/managed_datasets/hf_cache_dir"  ## TODO: import from config
    return dict(cache_dir=cache_dir, local_files_only=True)


def color_entities_html(text: str, label: str = "", link: str = ""):
    colors = {
        "Location": "background-color: lightcoral; color: black;",
        "Person": "background-color: lightgreen; color: black;",
        "Food": "background-color: peachpuff; color: black;",
        "Date": "background-color: lightblue; color: black;",
    }
    style = colors.get(label, "background-color: white; color: black;")
    if link:
        return f'<a href="{link}" <span style="{style} padding: 5px; border-radius: 3px;">{html.escape(text)}</span></a>'
    else:
        return f'<span style="{style} padding: 5px; border-radius: 3px;">{text}</span>'


def extract_audio_from_video(input_path, output_path):
    audio, sr = librosa.load(str(input_path))
    sf.write(os.path.join(output_path), audio, sr)


def create_small_sample(input_path, out_dir, start=10000, end=300000):
    new_audio = AudioSegment.from_wav(input_path)
    new_audio = new_audio[start:end]
    new_audio.export(os.path.join(out_dir, "interview_sample.wav"), format="wav")

def read_json(input_path):
    interviews = []
    with open(input_path) as f:
        data = json.load(f)
    for interview in data:
        interviews.append({"original_uri": interview["@id"], "headline": interview["headline"], "text": [{"text": interview["description"]}, {"text": interview["articleBody"]}]})
    return interviews