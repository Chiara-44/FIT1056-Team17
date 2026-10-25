# filename: usability_fix_test.py
# group: Team 17
# names: Harry
# created: 25/10/26
# last modified: 25/10/26
#
# Tests for the fixes made after the usability walkthrough (Section 9.4, Table 15):
# WF-01 allergy confirmation, WF-02 contradictory dietary tags, WF-03 phone numbers
# and WF-04 Australian date format.

import io
import json
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

import pytest

import main
from app.clients import Client
from app.schedule import ScheduleManager
from app.storeroom import FoodbankItem, parse_expiry


def write_data(tmp_path):
    """One staff member, a vegan client with a severe nut allergy, and a mis-tagged item."""
    data = {
        "volunteers": [],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [],
        "clients": [{"id": 1, "name": "Maya Donald", "phone": "0400 000 000",
                     "allergies": {"peanuts": "severe"}, "preferences": ["vegan"],
                     "household_size": 1}],
        "storeroom": [
            {"id": 1, "name": "Rice", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 10, "expiry": None},
            # Entered before the donation check existed: tagged vegan but lists dairy
            {"id": 2, "name": "Milk biscuits", "allergens": ["dairy"], "may_contain": [],
             "preferences": ["vegan"], "quantity": 10, "expiry": None},
        ],
        "next_volunteer_id": 1, "next_staff_id": 2, "next_admin_id": 1,
        "next_client_id": 2, "next_item_id": 3,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def staff_manager(tmp_path):
    manager = ScheduleManager(str(write_data(tmp_path)))
    manager.login("angela", "staff123", "staff")
    return manager


def run_app(path, answers):
    answers = iter(answers)

    def fake_input(prompt=""):
        value = next(answers, None)
        if value is None:
            raise EOFError
        return value

    out = io.StringIO()
    with patch("builtins.input", fake_input), patch("main.getpass", fake_input), \
            redirect_stdout(out):
        main.main(str(path))
    return out.getvalue()


# ---------- WF-01 Allergy confirmation ----------

@pytest.mark.parametrize("answer", ["y", "yes", "YES"])   # EP: every accepted spelling
def test_allergy_warning_accepts_short_answers(tmp_path, answer):
    path = write_data(tmp_path)
    screen = run_app(path, ["staff", "angela", "staff123", "5", "1", answer, "a", "1", "1", "c",
                            "", "q"])
    assert "Hamper #1 is complete" in screen


def test_going_back_at_warning_leaves_no_draft(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, ["staff", "angela", "staff123", "5", "1", "maybe", "x", "", "q"])
    assert "Please type YES to continue or X to go back." in screen
    assert "No hamper was started." in screen
    assert json.loads(path.read_text()).get("hampers", []) == []


# ---------- WF-02 Contradictory dietary tags ----------

@pytest.mark.parametrize("allergens, tags", [
    (["dairy"], ["vegan"]),          # EP: animal product tagged vegan
    (["eggs"], ["vegan"]),
    (["fish"], ["vegetarian"]),      # EP: fish tagged vegetarian
])
def test_contradictory_donation_rejected(tmp_path, allergens, tags):
    manager = staff_manager(tmp_path)
    with pytest.raises(ValueError, match="can't be"):
        manager.record_donation("Biscuits", allergens, [], tags, 5, None)
    assert len(manager.storeroom) == 2                  # nothing was added


def test_plant_allergens_can_still_be_vegan(tmp_path):
    manager = staff_manager(tmp_path)
    item = manager.record_donation("Biscoff", ["gluten", "soy"], [], ["vegan"], 5, None)
    assert item.preferences == {"vegan"}


def test_mis_tagged_item_not_offered_or_packed_for_vegan_client(tmp_path):
    manager = staff_manager(tmp_path)
    client = manager.find_client(1)
    assert [i.name for i in manager.safe_items_for(client)] == ["Rice"]
    hamper = manager.create_hamper(1)
    manager.acknowledge_allergy_warning(hamper.id)
    with pytest.raises(ValueError, match="not vegan"):
        manager.add_hamper_item(hamper.id, 2, 1)
    assert FoodbankItem(9, "Milk", ["dairy"], [], ["vegan", "halal"]).suitable_diets() == {"halal"}


# ---------- WF-03 Phone numbers ----------

@pytest.mark.parametrize("phone, valid", [
    ("b", False),                 # EP: letters
    ("1234567", False),           # BVA: 7 digits, one too few
    ("12345678", True),           # BVA: 8 digits, the minimum
    ("0400 000 000", True),       # EP: mobile with spaces
    ("+61 400 000 000", True),    # BVA: 11 digits with country code
    ("(03) 9905 1234", True),     # EP: landline with brackets
    ("1234567890123", False),     # BVA: 13 digits, one too many
    ("", True),                   # EP: no phone recorded
])
def test_phone_number_partitions(phone, valid):
    if valid:
        assert Client(1, "Maya Donald", phone, {}, []).phone == phone
    else:
        with pytest.raises(ValueError, match="Phone number"):
            Client(1, "Maya Donald", phone, {}, [])


def test_invalid_phone_update_keeps_original(tmp_path):
    manager = staff_manager(tmp_path)
    with pytest.raises(ValueError):
        manager.update_client(1, phone="b", contact_method="sms")
    assert manager.find_client(1).phone == "0400 000 000"


# ---------- WF-04 Australian date format ----------

@pytest.mark.parametrize("text, expected", [
    ("25/04/2027", date(2027, 4, 25)),    # EP: Australian format
    ("2027-04-25", date(2027, 4, 25)),    # EP: ISO format
])
def test_both_date_formats_accepted(text, expected):
    assert parse_expiry(text) == expected


def test_impossible_australian_date_rejected():
    with pytest.raises(ValueError, match="DD/MM/YYYY"):
        parse_expiry("31/02/2027")
