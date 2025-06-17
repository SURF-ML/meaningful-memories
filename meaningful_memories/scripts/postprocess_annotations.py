import argparse
import copy
import json
import logging
import os
import re

from meaningful_memories.annotation_utils import generate_web_annotations

logging.basicConfig(level=logging.INFO)


def extract_entities_from_labelstudio_results(results):
    grouped = {}

    for r in results:
        region_id = r.get("id")
        if r["type"] == "labels":
            grouped[region_id] = {
                "global_start": r["value"]["start"],
                "global_end": r["value"]["end"],
                "text": r["value"]["text"],
                "label": r["value"]["labels"][0],
            }
        elif r["type"] == "textarea":
            if region_id not in grouped:
                grouped[region_id] = {}
            grouped[region_id][r["from_name"]] = r["value"]["text"][0]

    return list(grouped.values())


def update_entity_file_with_labelstudio(original_path, labelstudio_result):
    with open(original_path, "r") as f:
        original = json.load(f)

    original["entities_original"] = original.get("entities", [])

    new_entities = []

    for annotation in labelstudio_result.get("annotations", []):
        for item in annotation.get("result", []):
            if item["type"] == "labels" and "value" in item:
                val = item["value"]
                start = val["start"]
                end = val["end"]
                chunk_info = find_chunk_info(start, original.get("transcript_chunks", []))

                ent = {
                    "global_start": start,
                    "global_end": end,
                    "text": val["text"],
                    "label": val["labels"][0],
                    "chunk_id": chunk_info["chunk_id"],
                    "timestamps": chunk_info["timestamp"],
                }

                # Add per-region metadata (like wikidata/adamlink)
                for extra in annotation.get("result", []):
                    if (
                            extra["type"] == "textarea"
                            and extra.get("id") == item.get("id")
                    ):
                        ent[extra["from_name"]] = extra["value"]["text"][0]

                new_entities.append(ent)

    original["entities"] = new_entities
    original["annotations"] = labelstudio_result["annotations"]

    return original


def find_chunk_info(start, transcript_chunks):
    offset = 0
    for chunk in transcript_chunks:
        chunk_len = len(chunk["text"])
        if offset <= start < offset + chunk_len:
            return {
                "chunk_id": chunk.get("id"),
                "timestamp": chunk.get("timestamp")
            }
        offset += chunk_len
    return {"chunk_id": None, "timestamp": None}


def normalize_filename(name):
    name = os.path.splitext(name)[0]
    name = re.sub(r"[^a-z0-9]", "", name.lower())
    return name


def find_matching_original_file(file_upload_value, original_dir):
    norm_upload = normalize_filename(file_upload_value)
    for original_filename in os.listdir(original_dir):
        norm_original = normalize_filename(original_filename)
        if norm_original in norm_upload or norm_upload in norm_original:
            return os.path.join(original_dir, original_filename, original_filename + ".json")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline for running transcription and entity extraction. "
    )
    parser.add_argument("-l", "--ls-input", help="Path to LabelStudio export file.")
    parser.add_argument(
        "-p", "--pred-input", help="Path to folder containing original predictions."
    )
    parser.add_argument(
        "-o", "--output-dir", help="Path to output dir to store result json files."
    )
    parser.add_argument(
        "-t", "--text-only", help="Flag to set if selected data is not audio, to avoid adding empty timestamps in W3."
    )

    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)

    with open(args.ls_input) as f:
        ls_export = json.load(f)

    for item in ls_export:
        file_upload = item.get("file_upload")
        if not file_upload:
            continue
        match_path = find_matching_original_file(file_upload, args.pred_input)

        logging.info(f"Found matching path: {match_path}")
        if match_path:
            dir_name = os.path.basename(os.path.dirname(match_path))
            output_file_name = os.path.basename(match_path)
            output_path = os.path.join(args.output_dir, dir_name, output_file_name)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            output_json = update_entity_file_with_labelstudio(match_path, item)
            with open(output_path, "w") as f:
                json.dump(output_json, f, indent=2)

            w3_annotations = generate_web_annotations(
                output_json, output_json["metadata"]["label"], text_only=args.text_only
            )

            with open(
                    os.path.join(args.output_dir, dir_name, "annotations_ls.jsonld"), "w", encoding="utf-8"
            ) as f:
                json.dump(w3_annotations, f, ensure_ascii=False, indent=2)
            print(f"Updated: {output_path}")
        else:
            print(f"No match for Label Studio file_upload: {file_upload}")




if __name__ == "__main__":
    main()
