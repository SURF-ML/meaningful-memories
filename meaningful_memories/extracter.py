import logging
from collections import Counter
from typing import List

from gliner import GLiNER
from ollama import ChatResponse, chat
from pydantic import BaseModel

from meaningful_memories.config import config
from meaningful_memories.interview import Interview
from meaningful_memories.linker import LocationLinker, SubjectLinker


class Extracter:
    def __init__(self):
        self.model_name: str = ""

    def load_model(self):
        raise NotImplementedError

    def extract(self):
        raise NotImplementedError


class EntityExtracter(Extracter):
    def __init__(self):
        self.model_name: str = config.entities.model_name
        self.model = None
        if not self.model:
            self.load_model()
        self.labels: List[str] = ["Person", "Date", "Location", "Food", "Occupation"]
        self.model_threshold: float = 0.5
        self.post_threshold: float = 0.8
        self.location_linker = LocationLinker()
        self.subject_linker = SubjectLinker()

    def load_model(self):
        self.model = GLiNER.from_pretrained(self.model_name)

    def extract(self, interview: Interview):
        for chunk in interview.transcript.chunks:
            chunk_entities = self.model.predict_entities(
                chunk.text, self.labels, threshold=self.model_threshold
            )
            for ent in chunk_entities:
                if ent["score"] > self.post_threshold:
                    ent["chunk_id"] = chunk.id
                    ent["timestamps"] = chunk.timestamp
                    ent = self.add_location_id(ent)
                    ent = self.add_subject_id(ent)
                    interview.entities.append(ent)

    def add_location_id(self, entity: dict):
        if entity["label"] != "Location":
            return entity
        wikidata, adamlink = self.location_linker.find_street_match(entity["text"])
        entity["wikidata"] = wikidata
        entity["adamlink"] = adamlink
        if not wikidata:
            adamlink = self.location_linker.find_building_match(entity["text"])
            entity["adamlink"] = adamlink
        return entity

    def add_subject_id(self, entity: dict):
        if entity["label"] in ["Location", "Person", "Date"]:
            return entity
        else:
            gtaa_subjects = self.subject_linker.find_subject_matches(entity["text"])
            entity["gtaa_subject"] = gtaa_subjects
            return entity


class LLMTopicExtracter(Extracter):
    def __init__(self):
        self.model_name: str = config.topics.model_name
        self.model = None

    def load_model(self):
        pass

    def get_message_template(self):
        return [
            {
                "role": "system",
                "content": "You are an assistant helping with finding relevant themes and concepts in a piece of Dutch text. Focus on larger and more abstract themes. Reply always in Dutch. Return the list of concepts only, do not explain yourself or summarize the text.",
            },
            {
                "role": "user",
                "content": "Welke thema's, concepten komen hier voor? Geef alleen de lijst met concepten in korte keywords zonder uitleg, gescheiden door een komma.",
            },
            {"role": "user", "content": "[DOCUMENT]"},
        ]

    def extract(self, interview: Interview):
        logging.info(f"Extracting entities using {self.model_name}")
        for chunk in interview.transcript.chunks:
            model_input = self.get_message_template()
            model_input[-1]["content"] = model_input[-1]["content"].replace(
                "[DOCUMENT]", chunk.text
            )
            response: ChatResponse = chat(model=self.model_name, messages=model_input)
            topics = [topic.strip() for topic in response.message.content.split(",")]
            interview.chunk_topics.append({"chunk_id": chunk.id, "topics": topics})

    def aggregate_topics(self, interview):
        topic_counter = Counter()
        for chunk_topics in interview.chunk_topics:
            topic_counter.update([topic.lower() for topic in chunk_topics["topics"]])
        logging.info(f"Found the following topics: {topic_counter}")
        interview.topics = topic_counter.most_common(5)


class LocationOutput(BaseModel):
    location: str
    new: bool
    explanation: str


class ChunkLocations(BaseModel):
    locations: List[LocationOutput]


class LLMLocationExtracter(Extracter):
    def __init__(self):
        self.model_name: str = config.topics.model_name

    def get_message_template(self):
        loc_no_explanations = [
            {
                "role": "system",
                "content": "You are an assistant helping with finding relevant location in Amsterdam in a piece of Dutch text. You also receive a list of locations that are extracted. Please respond with locations that are missing, have likely misspellings due to transcription (example: Diemenpark instead of Diemerpark) or locations that do not have a literal mention (example: deduct which specific theatre is mentioned). Reply always in Dutch. Return the comma-separated list of locations only, do not explain yourself or summarize the text.",
            },
            {
                "role": "user",
                "content": "Welke locaties komen hier voor? Geef alleen de lijst met locaties, en of het correcties zijn, nieuwe locaties of afgeleide locaties (die niet expliciet genoemd worden). Geef geen locaties terug die te algemeen zijn, zoals Nederland of Amsterdam.",
            },
            {"role": "user", "content": "[DOCUMENT] \n Gevonden locaties: [LOCATIONS]"},
        ]
        loc_short_explanation = [
            {
                "role": "system",
                "content": "You are an assistant helping with finding relevant location in Amsterdam in a piece of Dutch text. You also receive a list of locations that are extracted. Please respond with locations that are missing, have likely misspellings due to transcription (example: Diemenpark instead of Diemerpark) or locations that do not have a literal mention (example: deduct which specific theatre is mentioned). Reply always in Dutch. Return the locations with a short explanation why you are outputting them.",
            },
            {
                "role": "user",
                "content": "Welke locaties komen hier voor? Geef de lijst met locaties, met korte uitleg en of het correcties zijn, nieuwe locaties of afgeleide locaties (die niet expliciet genoemd worden). Geef geen locaties terug die te algemeen zijn, zoals Nederland of Amsterdam.",
            },
            {"role": "user", "content": "[DOCUMENT] \n Gevonden locaties: [LOCATIONS]"},
        ]
        return loc_short_explanation

    def extract(self, interview: Interview):
        for chunk in interview.transcript.chunks:
            extracted_locations = [
                ent["text"]
                for ent in interview.entities
                if ent["label"] == "Location" and ent["chunk_id"] == chunk.id
            ]
            model_input = self.get_message_template()
            model_input[-1]["content"] = model_input[-1]["content"].replace(
                "[DOCUMENT]", chunk.text
            )
            model_input[-1]["content"] = model_input[-1]["content"].replace(
                "[LOCATIONS]", ",".join(extracted_locations)
            )
            response: ChatResponse = chat(
                model=self.model_name,
                messages=model_input,
                format=ChunkLocations.model_json_schema(),
            )
            output = ChunkLocations.model_validate_json(response.message.content)
            # locations = [loc.strip() for loc in response.message.content.split(",")]
            interview.chunk_locations.append(
                {"chunk_id": chunk.id, "locations": output}
            )
            print(response.message.content)
