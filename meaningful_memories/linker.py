import csv
import logging
import os
from collections import defaultdict

import requests
from rapidfuzz import process

from meaningful_memories import here
from meaningful_memories.config import config


class Linker:
    def __init__(self):
        self.name = ""


class LocationLinker(Linker):
    def __init__(self):
        self.data_path = os.path.join(here, "data/adamlink_streets_buildings.csv")
        self.location_data = defaultdict(list)
        self.skip_list = ["Nederland", "Europa"]  # too often extracted and unlikely as buildings in Amsterdam
        if not self.location_data:
            self.load_data()

    def load_data(self):
        with open(self.data_path, mode="r", newline="") as file:
            reader = csv.DictReader(file, delimiter=",")
            for row in reader:
                self.location_data[row["preflabel"]] = row

    def find_location_match(self, location: str):
        location = location.title()
        if location in self.skip_list:
            return "", "", "", "", ""
        if config.entities.fuzzy_search_locations:
            match = process.extractOne(
                location,
                self.location_data.keys(),
                score_cutoff=config.entities.fuzzy_threshold,
            )
            match = self.location_data.get(match[0]) if match else None
        else:
            match = self.location_data[location]
        if match:
            return match["preflabel"], match["wikidata"], match["adamlink_uri"], match["longitude"], match["latitude"]
        else:
            return "", "", "", "", ""


class SubjectLinker(Linker):
    def __init__(self):
        self.api_uris = config.thesauri.uris
        self.graphql_uri = "https://termennetwerk-api.netwerkdigitaalerfgoed.nl/graphql"

    def _query_api(self, api_uri, query_input):
        query = f"""
        query {{
          terms(
            sources: ["{api_uri}"],
            query: "{query_input}",
          ) {{
            source {{
              uri
              name
              creators {{
                uri
                name
                alternateName
              }}
            }}
            result {{
              __typename
              ... on Terms {{
                terms {{
                  uri
                  prefLabel
                  altLabel
                  hiddenLabel
                  definition 
                  scopeNote
                  seeAlso
                  broader {{
                    uri
                    prefLabel
                  }}
                  narrower {{
                    uri
                    prefLabel
                  }}
                  related {{
                    uri
                    prefLabel
                  }}
                  exactMatch {{
                    uri
                    prefLabel
                  }}
                }}
              }}
              ... on Error {{
                message
              }}
            }}
            responseTimeMs
          }}
        }}
        """

        headers = {"Content-Type": "application/json"}

        # Send the request
        response = requests.post(
            self.graphql_uri, json={"query": query}, headers=headers
        )

        # Check for errors
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Error {response.status_code}: {response.text}")
            return {}

    def find_subject_matches(self, label_value):
        all_uris = set()
        for api_uri in self.api_uris:
            response = self._query_api(api_uri, label_value)
        if response:
            uris = self.extract_uris(response)
            for uri in uris:
                all_uris.add(uri)
        return list(all_uris)

    def extract_uris(self, response):
        uris = []
        terms = response.get("data", {}).get("terms", [])
        for term in terms:
            result = term.get("result", {})
            if result.get("__typename") == "Terms":
                for item in result.get("terms", []):
                    uris.append(item.get("uri"))
        return uris
