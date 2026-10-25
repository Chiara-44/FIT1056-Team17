# filename: food_requirement_test.py
# group: Team 17
# names: Chiara
# created: 29/09/26
# last modified: 29/09/26

import json

import pytest
from app.clients import Client
from app.storeroom import FoodbankItem
from app.schedule import ScheduleManager


def make_item(allergens=(), may_contain=(), preferences=("vegan", "vegetarian")):
    return FoodbankItem(1, "Test item", list(allergens), list(may_contain), list(preferences), 5)


def make_client(allergies=None, preferences=()):
    return Client(1, "Test client", "0400 000 000", allergies or {}, list(preferences))


# ---- Positive ----

def test_item_with_no_allergens_is_safe():
    client = make_client({"peanuts": "severe"})
    assert client.can_have(make_item())


def test_may_contain_allowed_for_mild_allergy():
    client = make_client({"dairy": "mild"})
    assert client.can_have(make_item(may_contain=["dairy"]))


# ---- Negative (FR-16) ----

def test_contains_allergen_blocked_even_if_mild():
    client = make_client({"dairy": "mild"})
    item = make_item(allergens=["dairy"])
    assert not client.can_have(item)
    assert item.allergy_conflicts(client.allergies) == ["contains dairy"]


def test_may_contain_blocked_for_severe_allergy():
    client = make_client({"tree nuts": "severe"})
    item = make_item(may_contain=["tree nuts"])
    assert not client.can_have(item)
    assert item.allergy_conflicts(client.allergies) == ["may contain tree nuts (severe allergy)"]


def test_unknown_allergen_rejected():
    with pytest.raises(ValueError):
        make_client({"nutz": "severe"})


def test_unknown_severity_rejected():
    with pytest.raises(ValueError):
        make_client({"peanuts": "very bad"})


# ---- Edge ----

def test_allergen_names_are_case_insensitive():
    client = make_client({"  Peanuts ": "SEVERE"})
    assert client.allergies == {"peanuts": "severe"}
    assert not client.can_have(make_item(allergens=["PEANUTS"]))


def test_list_format_without_severity_rejected():
    # Allergies must always have a severity, so a plain list gives a clear error
    with pytest.raises(ValueError, match="severity"):
        Client(1, "Old", "0400 000 000", ["peanuts"], [])


def test_client_record_without_allergies_loads(tmp_path):
    # A saved client with no "allergies" field should load as having no allergies
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"clients": [{"id": 1, "name": "Sam", "phone": ""}]}))
    manager = ScheduleManager(str(path))
    assert manager.find_client(1).allergies == {}


def test_severe_allergies_listed_for_packer_warning():
    client = make_client({"peanuts": "severe", "dairy": "mild", "sesame": "severe"})
    assert client.severe_allergies() == ["peanuts", "sesame"]

