import torch
import whisperx
from transformers import pipeline

from meaningful_memories.config import config
from meaningful_memories.transcript import Transcript
from meaningful_memories.utils import get_cache_kwargs


class WhisperTranscriber:
    def __init__(self):
        self.model_name = config.transcript.whisper.model_name
        self.model = None
        if not self.model:
            self.load_model()

    def load_model(self):
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        cache_dir = (
            get_cache_kwargs() if config.transcript.whisper.use_shared_cache else {}
        )
        self.model = pipeline(
            "automatic-speech-recognition",
            model=self.model_name,
            chunk_length_s=30,
            device=device,
            model_kwargs=cache_dir,
        )

    def transcribe(self, interview, small_sample=False):
        if small_sample:
            input_audio = interview.sample_path
        else:
            input_audio = interview.audio_path
        interview.transcript = Transcript(
            self.model(input_audio, batch_size=8, return_timestamps=True)["chunks"]
        )


class WhisperXTranscriber:
    def __init__(self):
        self.model_name = config.transcript.whisperx.model_name
        self.model = None
        self.device = "cuda"
        if not self.model:
            self.load_model()
        self.batch_size = 4

    def load_model(self):
        self.model = whisperx.load_model(self.model_name, self.device, language="nl")

    def transcribe(self, interview):
        audio = whisperx.load_audio(interview.audio_path)
        result = self.model.transcribe(audio, batch_size=self.batch_size)

        # 2. Align whisper output
        model_a, metadata = whisperx.load_align_model(
            language_code="nl", device=self.device
        )
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            self.device,
            return_char_alignments=False,
        )

        # print(result["segments"])  # after alignment

        diarize_model = whisperx.DiarizationPipeline(device=self.device)

        # add min/max number of speakers if known
        diarize_segments = diarize_model(audio)
        # diarize_model(audio, min_speakers=min_speakers, max_speakers=max_speakers)

        result = whisperx.assign_word_speakers(diarize_segments, result)
        interview.transcript = Transcript(result["segments"], whisperx=True)
