import csv
import logging
import os
from collections import defaultdict

import requests
from rapidfuzz import process
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDFS

from meaningful_memories import here
from meaningful_memories.config import config


class Linker:
    def __init__(self):
        self.name = ""


class LocationLinker(Linker):
    def __init__(self):
        self.data_path = os.path.join(here, "data/streets.csv")
        self.street_data = defaultdict(list)
        self.building_data = None
        if not self.street_data:
            self.load_data()
        if not self.building_data:
            self.building_data = Buildings(
                os.path.join(here, "data/adamlinkgebouwen.ttl")
            )

    def load_data(self):
        with open(self.data_path, mode="r", newline="") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                self.street_data[row["preflabel"]] = row

    def find_street_match(self, streetname: str):
        streetname = streetname.title()
        if config.entities.fuzzy_search_locations:
            match = process.extractOne(
                streetname,
                self.street_data.keys(),
                score_cutoff=config.entities.fuzzy_threshold,
            )
            match = self.street_data.get(match[0]) if match else None
        else:
            match = self.street_data[streetname]
        if match:
            return match["wikidata"], match["adamlink_uri"]
        else:
            return "", ""

    def find_building_match(self, building_name):
        match_results = self.building_data.get_subject_by_label(building_name)
        if match_results:
            return match_results[0]  # currently only returning first result

    # TODO: skip buildings: "Nederland", "Europa"


class Buildings:
    def __init__(self, file_path):
        """
        Initializes and loads the Turtle file into an RDF graph.
        :param file_path: Path to the Turtle file
        """
        self.graph = Graph()
        self.graph.parse(file_path, format="turtle")

    def get_subject_by_label(self, label_value):
        """
        Finds the subject (key) associated with a given rdfs:label.
        """
        return [
            str(subject)
            for subject in self.graph.subjects(
                predicate=RDFS.label, object=Literal(label_value)
            )
        ]


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
