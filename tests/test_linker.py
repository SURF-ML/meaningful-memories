import pytest

from meaningful_memories.linker import LocationLinker, SubjectLinker

building_examples = [
    ("Paleis op de Dam", True),
    ("huis", False),
]


@pytest.mark.parametrize("label, expected", building_examples)
def test_building_lookup(label, expected):
    linker = LocationLinker()
    building_match = linker.find_building_match(label)
    assert bool(building_match) == expected


street_examples = [
    ("Warmoesstraat", True),
    ("straat", False),
]


@pytest.mark.parametrize("label, expected", street_examples)
def test_street_lookup(label, expected):
    linker = LocationLinker()
    street_match = linker.find_street_match(label)
    assert bool(street_match[0]) == expected


def test_thesauri_lookup():
    linker = SubjectLinker()
    uris = linker.find_subject_matches("brood")
    print(uris)

