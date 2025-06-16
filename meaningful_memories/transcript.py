import string

from meaningful_memories.config import config
from meaningful_memories.transcript_chunk import TranscriptChunk


class Transcript:
    def __init__(self, transcription, whisperx=False):
        self.transcription_raw = transcription
        self.whisperx = whisperx
        self.transcript_all = ""
        # self.transcription_lines = self.get_lines()
        self.chunks = []
        self.max_length = config.transcript.whisper.max_chunk_size
        if self.whisperx:
            self.create_chunks_from_words()
        else:
            self.create_chunks()
        self.chunks_dict = {chunk.id: chunk for chunk in self.chunks}

    def get_chunk_by_id(self, chunk_id):
        return self.chunks_dict.get(chunk_id)

    def get_lines(self):
        lines = []
        for part in self.transcription_raw:
            part_lines = part["text"].split(".")
            for part_line in part_lines:
                if not part_line.endswith(tuple(string.punctuation)):
                    part_line += "."
                if not "timestamp" in part:
                    part["timestamp"] = (
                        0,
                        0,
                    )  # setting to default value in case of text
                lines.append({"text": part_line, "timestamp": part["timestamp"]})
        return lines

    def create_chunks(self):
        chunk_text = ""
        start_timestamp = 0
        end_timestamp = 0
        chunk_id = 0
        for line in self.transcription_raw:
            if len(chunk_text.split() + line["text"].split()) < self.max_length:
                chunk_text += line["text"].strip() + " "
                if "timestamp" in line:
                    if line["timestamp"][0] and line["timestamp"][0] < start_timestamp:
                        start_timestamp = line["timestamp"][0]
                    if line["timestamp"][1] and line["timestamp"][1] > end_timestamp:
                        end_timestamp = line["timestamp"][1]
            else:
                self.chunks.append(
                    TranscriptChunk(
                        chunk_text, chunk_id, start_timestamp, end_timestamp
                    )
                )
                chunk_text = line["text"]
                chunk_id += 1
                start_timestamp = line["timestamp"][0] if "timestamp" in line else 0
                end_timestamp = line["timestamp"][1] if "timestamp" in line else 0
        self.chunks.append(
            TranscriptChunk(chunk_text, chunk_id, start_timestamp, end_timestamp)
        )

    def create_chunks_from_words(self, keep_same_speaker=False):
        current_chunk = []
        current_start = None
        current_end = None
        current_speaker = None
        chunk_id = 0
        for segment in self.transcription_raw:
            start = float(segment["start"])
            end = float(segment["end"])
            speaker = segment.get("speaker", "unknown")

            if not current_chunk:
                current_chunk = [segment]
                current_start = start
                current_end = end
                current_speaker = speaker
                continue

            next_duration = end - current_start
            speaker_matches = speaker == current_speaker

            if next_duration > self.max_length or (
                keep_same_speaker and not speaker_matches
            ):
                combined_text = " ".join(seg["text"] for seg in current_chunk)
                self.chunks.append(
                    TranscriptChunk(combined_text, chunk_id, current_start, current_end)
                )
                chunk_id += 1

                current_chunk = [segment]
                current_start = start
                current_end = end
                current_speaker = speaker
            else:
                current_chunk.append(segment)
                current_end = end

        if current_chunk:
            combined_text = " ".join(seg["text"] for seg in current_chunk)
            self.chunks.append(
                TranscriptChunk(combined_text, chunk_id, current_start, current_end)
            )

    def get_transcript_at_time(self, time_start, time_end):
        """
        We want to be able to get the corresponding transcript when we
        ask for specific time. Time can be more general, e.g.
        get_transcript_at_time("01:00", "02:00") should give
        the result for the closest parts of the transcript.
        """
        return

    def get_timestamps(self, chunk_id):
        """transcript has mapping of timestamps <-> text
        We convert the transcript to text.
        We want to have the mapping from text index to timestamp.
        Currently, we return the timestamp of the chunk only
        since we don't have more finegrained timestamps.
        """
        return self.get_chunk_by_id(chunk_id).timestamp
