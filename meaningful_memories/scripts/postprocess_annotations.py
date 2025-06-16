import argparse
import copy
import json
import logging
import os
import re

logging.basicConfig(level=logging.INFO)


def extract_entities_from_labelstudio_results(results):
    grouped = {}
    entities = []

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


def update_entity_file_with_labelstudio(original_path, labelstudio_result, output_path):
    with open(original_path, "r") as f:
        original = json.load(f)

    # Backup current entities
    if "entities" in original:
        original["entities_original"] = copy.deepcopy(original["entities"])

    # Extract LS results (assumes one annotation task)
    if "annotations" in labelstudio_result and labelstudio_result["annotations"]:
        ls_results = labelstudio_result["annotations"][0]["result"]
    else:
        print(f"No annotations found in {labelstudio_result}")
        return

    # Convert LS annotations to structured entities
    new_entities = extract_entities_from_labelstudio_results(ls_results)
    original["entities"] = new_entities
    original["annotations"] = labelstudio_result["annotations"]

    with open(output_path, "w") as f:
        json.dump(original, f, indent=2)


def normalize_filename(name):
    name = os.path.splitext(name)[0]
    name = re.sub(r"[^a-z0-9]", "", name.lower())
    return name


def find_matching_original_file(file_upload_value, original_dir):
    norm_upload = normalize_filename(file_upload_value)

    for original_filename in os.listdir(original_dir):
        norm_original = normalize_filename(original_filename)
        if norm_original in norm_upload or norm_upload in norm_original:
            return os.path.join(original_dir, original_filename)
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

    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
    # Load your full Label Studio export
    with open(args.ls_input) as f:
        ls_export = json.load(f)

    for item in ls_export:
        file_upload = item.get("file_upload")
        if not file_upload:
            continue

        match_path = find_matching_original_file(file_upload, args.pred_input)
        logging.info(f"Found matching path: {match_path}")
        if match_path:
            output_path = os.path.join(args.output_dir, os.path.basename(match_path))
            update_entity_file_with_labelstudio(match_path, item, output_path)
            print(f"Updated: {output_path}")
        else:
            print(f"No match for Label Studio file_upload: {file_upload}")


if __name__ == "__main__":
    main()
