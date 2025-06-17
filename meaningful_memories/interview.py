import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from meaningful_memories.annotation_utils import generate_web_annotations
from meaningful_memories.transcript import Transcript
from meaningful_memories.utils import (color_entities_html,
                                       extract_audio_from_video)


class Interview:
    def __init__(
        self,
        input_dir: Optional[str] = None,
        skip_convert: bool = False,
        original_uri: str = "",
        interview_label: str = "",
    ):
        self.input_dir = Path(input_dir) if input_dir else None
        self.original_uri = original_uri
        self.audio_path = None
        self.video_path = None
        self.interview_label = interview_label
        if not len(self.original_uri):
            self.original_uri = self.interview_label
        if not input_dir:
            logging.info(
                "Initializing interview object without path. Won't be able to run input conversion."
            )
        else:
            self.load_audio_path()
            if not skip_convert:
                self.load_video_path()
                logging.info(f"Converting {self.video_path} to audio (WAV).")
                extract_audio_from_video(self.video_path, self.audio_path)
            self.interview_label = os.path.basename(self.input_dir)
        self.transcript = None
        self.entities = []
        self.chunk_topics = []
        self.topics = []
        self.chunk_locations = []
        self.small_sample_path = os.path.join(self.input_dir, "interview_sample.wav")

    def load_video_path(self):
        ## TODO: default to interview.mp4 if multiple mp4 files in directory
        if list(self.input_dir.glob("*.mp4")):
            self.video_path = list(self.input_dir.glob("*.mp4"))[0]
        elif list(self.input_dir.glob("*.mkv")):
            self.video_path = list(self.input_dir.glob("*.mkv"))[0]

    def load_audio_path(self):
        if list(self.input_dir.glob("*.wav")):
            self.audio_path = str(list(self.input_dir.glob("*.wav"))[0])
        else:
            self.audio_path = os.path.join(self.input_dir, "interview.wav")

    def combine_chunks(self):
        chunk_offsets = {}
        transcript_all = ""
        offset = 0
        for chunk in self.transcript.chunks:
            chunk_offsets[chunk.id] = offset
            separator = "\n"
            transcript_all += chunk.text + separator
            offset += len(chunk.text + separator)

        for entity in self.entities:
            local_start = entity["start"]
            local_end = entity["end"]
            chunk_id = entity["chunk_id"]
            chunk_offset = chunk_offsets[chunk_id]

            entity["global_start"] = local_start + chunk_offset
            entity["global_end"] = local_end + chunk_offset

        self.transcript.transcript_all = transcript_all

        line_offsets = []
        full_text = ""
        running_offset = 0
        for line in self.transcript.get_lines():
            text = line["text"]
            start_offset = running_offset
            end_offset = start_offset + len(text)
            line_offsets.append(
                {
                    "start": start_offset,
                    "end": end_offset,
                    "timestamp": line["timestamp"],
                    "text": text,
                }
            )
            running_offset = end_offset
            full_text += text

        for entity in self.entities:
            g_start = entity["global_start"]
            for i, line in enumerate(line_offsets):
                if line["start"] <= g_start < line["end"]:
                    entity["line_index"] = i
                    entity["line_timestamp"] = line["timestamp"]
                    entity["line_text"] = line["text"]
                    break
            else:
                entity["line_index"] = None
                entity["line_timestamp"] = None
                entity["line_text"] = None

    def visualize(self):
        all_chunks_marked = ""

        for chunk in self.transcript.chunks:
            text = chunk.text
            chunk_entities = [
                ent for ent in self.entities if chunk.id == ent["chunk_id"]
            ]

            entity_replacements = []

            for ent in chunk_entities:
                if ent["score"] > 0.8:
                    link = ent.get("adamlink", "")
                    if not link:
                        link = ent.get("gtaa_subject", "")
                    start, end = ent["start"], ent["end"]
                    entity_text = text[start:end]  # Extract the exact entity text
                    replacement = color_entities_html(entity_text, ent["label"], link)
                    entity_replacements.append((start, end, replacement))

            entity_replacements.sort(reverse=True, key=lambda x: x[0])

            for start, end, replacement in entity_replacements:
                text = text[:start] + replacement + text[end:]

            # Preserve line breaks after sentence-ending punctuation
            text = re.sub(r"(?<=[a-zA-Z0-9])([.!?])(\s|$)", r"\1<br>\2", text)

            all_chunks_marked += text
        topics = "".join(["<li>" + topic[0] + "</li>" for topic in self.topics])
        topic_information = f"<br><br> Topics: <ul>{topics}</ul>"
        all_chunks_marked += topic_information
        with open(
            os.path.join(self.input_dir, "interview_transcript_tagged.html"), "w"
        ) as f:
            f.write(
                f"<!DOCTYPE html>\n<html>\n<head><meta charset='UTF-8' name='viewport' content='width=device-width, initial-scale=1'>>\n</head>\n<body>\n{all_chunks_marked}\n</body>\n</html>"
            )

    def write_to_file(self, args):
        entity_results = []

        for i, ent in enumerate(self.entities):
            region_id = str(uuid.uuid4())
            entity_results.append(
                {
                    "id": region_id,
                    "from_name": "label",
                    "to_name": "text",
                    "type": "labels",
                    "value": {
                        "start": ent["global_start"],
                        "end": ent["global_end"],
                        "text": ent["text"],
                        "labels": [ent["label"]],
                        "timestamps": ent["timestamps"],
                        "wikidata": ent.get("wikidata", ""),
                        "adamlink": ent.get("adamlink", ""),
                        "preflabel": ent.get("preflabel", ""),
                    },
                }
            )
            for datalink in ["wikidata", "adamlink", "preflabel"]:
                if datalink in ent and ent[datalink]:
                    entity_results.append(
                        {
                            "id": region_id,
                            "from_name": datalink,
                            "to_name": "text",
                            "type": "textarea",
                            "value": {"text": [ent[datalink]]},
                        }
                    )
        output_data = {
            "metadata": {"label": self.interview_label},
            "entities": self.entities,
            "topics_chunk": self.chunk_topics,
            "topics_aggregate": self.topics,
            "locations_chunk": [
                {
                    "chunk_id": loc["chunk_id"],
                    "locations": [
                        llm_loc.dict() for llm_loc in loc["locations"].locations
                    ],
                }
                for loc in self.chunk_locations
            ],
            "transcript_chunks": [
                {"id": chunk.id, "timestamp": chunk.timestamp, "text": chunk.text}
                for chunk in self.transcript.chunks
            ],
            "transcript_raw": self.transcript.transcription_raw,
            "data": {
                "text": self.transcript.transcript_all
            },  # labelstudio friendly format
            "predictions": [{"result": entity_results}],
        }
        with open(
            os.path.join(self.input_dir, f"{self.interview_label}.json"), "w"
        ) as f:
            json.dump(output_data, f)

        w3_annotations = generate_web_annotations(
            output_data, self.interview_label, text_only=args.text_only
        )
        with open(
            os.path.join(self.input_dir, "annotations.jsonld"), "w", encoding="utf-8"
        ) as f:
            json.dump(w3_annotations, f, ensure_ascii=False, indent=2)

    def load_from_file(self):
        with open(os.path.join(self.input_dir, "interview.json"), "r") as f:
            interview_data = json.load(f)
        self.entities = interview_data["entities"]
        self.transcript = Transcript(interview_data["transcript_raw"])
        self.topics = interview_data["topics_aggregate"]
        # self.transcript.chunks = [TranscriptChunk(x["id"], x["text"], x["timestamp"][0], x["timestamp"][1]) for x in interview_data["transcript_chunmks"]]
