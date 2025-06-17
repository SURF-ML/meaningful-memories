import json
import os
import re
import uuid

from meaningful_memories import here
from meaningful_memories.utils import get_adamlink_coordinates

def get_non_truncated_context(text, start, end, min_context_len=30):
    exact = text[start:end]

    prefix_start = max(0, start - min_context_len * 2)
    raw_prefix = text[prefix_start:start]

    prefix_words = re.findall(r"\S+\s*", raw_prefix)
    prefix_words = prefix_words[1:]  # drop half-words at start
    prefix = "".join(prefix_words[-min(len(prefix_words), 10) :])

    suffix_end = min(len(text), end + min_context_len * 2)
    raw_suffix = text[end:suffix_end]

    suffix_words = re.findall(r"\s*\S+", raw_suffix)
    suffix_words = suffix_words[:-1]  # drop half-words at end
    suffix = "".join(suffix_words[: min(len(suffix_words), 10)])

    return prefix, exact, suffix


def look_up_uri(str_identifier):
    with open(
        os.path.join(here, "annotation_data/amsterdammuseum_uva_videos.json"),
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)
    for item in data:
        if item.get("identifier").split(".")[0] == str_identifier:
            return item.get("name"), item.get("identifier"), item.get("@id")
    return "", "", ""


def generate_web_annotations(data, original_uri: str = "", text_only=False):
    w3_annotations = []
    name, identifier, video_id = look_up_uri(original_uri)
    for ent in data["entities"]:
        body = [
            {"type": "TextualBody", "value": ent["label"], "purpose": "classifying"}
        ]

        for datalink in ["wikidata", "adamlink"]:
            datalink_value = ent.get(datalink) or ent.get("metadata", {}).get(datalink)
            if datalink_value:
                resource = {
                        "type": "SpecificResource",
                        "purpose": "identifying",
                        "source": {
                            "@context": "https://schema.org",
                            "id": datalink_value,
                            "type": "Place",
                            "label": ent.get("preflabel"),
                        },
                    }
                if datalink == "adamlink":
                    long, lat = get_adamlink_coordinates(datalink_value)
                    resource["source"]["longitude"] = long
                    resource["source"]["latitude"] = lat
                body.append(resource)

        start = ent["global_start"]
        end = ent["global_end"]
        full_text = data["data"]["text"]

        prefix, exact, suffix = get_non_truncated_context(full_text, start, end)
        selector = [
            {
                "type": "TextQuoteSelector",
                "exact": exact,
                "prefix": prefix,
                "suffix": suffix,
            }
        ]
        if not text_only:
            selector.append(
                {
                    "type": "FragmentSelector",
                    "conformsTo": "http://www.w3.org/TR/media-frags/",
                    "values": f"t={ent['timestamps'][0]},{ent['timestamps'][1]}",
                }
            )
            source = {"@context": "https://schema.org",
        "id": video_id,
        "type": "VideoObject",
        "name": name,},

        else:
            source = {"id": original_uri}

        w3_annotations.append(
            {
                "@context": "http://www.w3.org/ns/anno.jsonld",
                "id": str(uuid.uuid4()),
                "type": "Annotation",
                "body": body,
                "target": {
                    "source": source,
                    "selector": selector},
            }
        )
    topics = [topic[0] for topic in data["topics_aggregate"]]    # topics are tuples (topic, count)
    for topic in topics:
        body = [
            {"type": "TextualBody", "value": topic, "purpose": "classifying"}
        ]
        if not text_only:
            source = {"@context": "https://schema.org",
                      "id": video_id,
                      "type": "VideoObject",
                      "name": name, },

        else:
            source = {"id": original_uri}

        w3_annotations.append(
            {
                "@context": "http://www.w3.org/ns/anno.jsonld",
                "id": str(uuid.uuid4()),
                "type": "Annotation",
                "body": body,
                "target": {
                    "source": source,}
            }
        )


    return w3_annotations
