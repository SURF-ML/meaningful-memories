import argparse
import json
import logging
import os


def search_entity_in_folder(folder_path, entity_name):
    results = {}
    for dir in os.listdir(folder_path):
        sub_dir = os.path.join(folder_path, dir)
        logging.info(f"Checking folder {dir}")
        for filename in os.listdir(sub_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(folder_path, sub_dir, filename)
                file_id = os.path.join(sub_dir, filename)
                logging.info(f"Checking {file_path}")
                with open(file_path, "r", encoding="utf-8") as file:
                    try:
                        data = json.load(file)
                        entities = data["entities"]
                        if isinstance(entities, list):
                            matching_entries = [
                                entry
                                for entry in entities
                                if entry.get("text") == entity_name
                            ]
                            if matching_entries:
                                results[file_id] = matching_entries
                        if matching_entries:
                            results[file_id] = (
                                matching_entries  # Store results if matches found
                            )
                    except json.JSONDecodeError:
                        print(f"Error reading {filename}: Invalid JSON format")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Find fragments in which specific topics and entities are mentioned. "
    )

    parser.add_argument(
        "-d", "--input-dir", help="Path to folder containing input data."
    )
    parser.add_argument("-e", "--entity")

    args = parser.parse_args()
    # Example usage
    matches = search_entity_in_folder(args.input_dir, args.entity)

    # Print results
    for file, entries in matches.items():
        print(f"\nMatches in {file}:")
        for entry in entries:
            print(json.dumps(entry, indent=4))


if __name__ == "__main__":
    main()
