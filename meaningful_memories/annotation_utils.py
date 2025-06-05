def generate_web_annotations(data, original_uri: str = ""):
    w3_annotations = []
    for i, ent in enumerate(data["entities"]):
        body = [
            {
                "type": "TextualBody",
                "value": ent["label"],
                "purpose": "tagging"
            }
        ]

        for datalink in ["wikidata", "adamlink"]:
            datalink_value = ent.get(datalink) or ent.get("metadata", {}).get(datalink)
            if datalink_value:
                body.append({
                    "type": "SpecificResource",
                    "purpose": "identifying",
                    "source": {
                        "id": datalink_value,
                        "type": "Place",
                        "label": datalink_value
                    }
                })

        context_size = 30  # for TextQuoteSelector

        start = ent["global_start"]
        end = ent["global_end"]
        full_text = data["data"]["text"]

        prefix = full_text[max(0, start - context_size):start]
        suffix = full_text[end:end + context_size]
        exact = ent["text"]

        w3_annotations.append({
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "id": original_uri,  # f"urn:uuid:{uuid.uuid4()}",
            "type": "Annotation",
            "body": body,
            "target": {
                "source": original_uri,
                "selector": {
                    "type": "TextQuoteSelector",
                    "exact": exact,
                    "prefix": prefix,
                    "suffix": suffix
                }
            }
        })

    return w3_annotations





