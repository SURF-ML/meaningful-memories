class TranscriptChunk:
    def __init__(self, chunk_text, chunk_index, start_timestamp, end_timestamp):
        self.id = f"id_transcription_{chunk_index}"
        self.timestamp = (start_timestamp, end_timestamp)
        self.text = chunk_text

    def id_equals(self, index):
        return self.id.split("_")[-1] == index
