# filename: client_test.py
# group: Team 17
# names: Harry
# created: 16/10/26
# last modified: 25/10/26
#
# Tests for client profiles (F-02: FR-04 to FR-08, NFR-02, NFR-03, NFR-15).
# Covers household composition, contact method, accessibility needs, food preferences,
# editing a client, private notes and what volunteers can and can't see.

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

import main
from app.clients import Client
from app.schedule import ScheduleManager


def write_data(tmp_path, clients=None):
    data = {
        "volunteers": [{"id": 1, "name": "Sophie Patel", "username": "sophie",
                        "password": "vol123", "role": "volunteer"}],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [],
        "clients": clients if clients is not None else [
            {"id": 1, "name": "Maya Donald", "phone": "0400 000 000",
             "allergies": {"peanuts": "severe"}, "preferences": ["vegan"],
             "household": {"adults": 1, "children": 0, "infants": 1},
             "contact_method": "sms", "accessibility_needs": ["help carrying"],
             "food_notes": "prefers fresh vegetables", "language": "English",
             "private_notes": [{"text": "Recently moved", "by": "angela", "date": "2026-10-10"}]},
        ],
        "storeroom": [],
        "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 1, "next_client_id": 2,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def staff_manager(tmp_path):
    path = write_data(tmp_path)
    manager = ScheduleManager(str(path))
    manager.login("angela", "staff123", "staff")
    return manager, path


def make_client(**kwargs):
    defaults = dict(id=1, name="Test Client", phone="0400 000 000", allergies={}, preferences=[])
    defaults.update(kwargs)
    return Client(**defaults)


# ---------- Household composition (FR-06) ----------

def test_household_composition_and_total():
    client = make_client(household={"adults": 2, "children": 1, "infants": 1})
    assert client.household_size == 4
    assert client.household_text() == "4 (2 adults, 1 child, 1 infant)"


def test_old_records_with_only_a_total_are_treated_as_adults():
    client = make_client(household_size=3)
    assert client.household == {"adults": 3, "children": 0, "infants": 0}


@pytest.mark.parametrize("household, valid", [
    ({"adults": 0, "children": 0, "infants": 0}, False),   # BVA: total 0
    ({"adults": 1}, True),                                  # BVA: total 1
    ({"adults": 18, "children": 2}, True),                  # BVA: total 20
    ({"adults": 19, "children": 2}, False),                 # BVA: total 21
    ({"adults": 1, "children": -1}, False),                 # EP: negative count
    ({"adults": "two"}, False),                             # EP: not a number
])
def test_household_partitions(household, valid):
    if valid:
        assert make_client(household=household).household_size == sum(household.values())
    else:
        with pytest.raises(ValueError):
            make_client(household=household)


# ---------- Contact method (FR-08) ----------

def test_default_contact_method_depends_on_phone():
    assert make_client(phone="0400 000 000").contact_method == "sms"
    assert make_client(phone="").contact_method == "in person"


@pytest.mark.parametrize("method, phone, email, valid", [
    ("sms", "0400 000 000", "", True),
    ("phone call", "0400 000 000", "", True),
    ("email", "", "a@b.com", True),
    ("in person", "", "", True),
    ("sms", "", "", False),             # no phone number to text
    ("email", "0400 000 000", "not-an-email", False),
    ("carrier pigeon", "0400 000 000", "", False),
])
def test_contact_method_needs_matching_details(method, phone, email, valid):
    if valid:
        assert make_client(phone=phone, email=email, contact_method=method).contact_method == method
    else:
        with pytest.raises(ValueError):
            make_client(phone=phone, email=email, contact_method=method)


# ---------- Accessibility needs and food preferences (FR-07) ----------

def test_accessibility_needs_are_checked():
    client = make_client(accessibility_needs=["Help Carrying ", "interpreter"])
    assert client.accessibility_needs == {"help carrying", "interpreter"}
    with pytest.raises(ValueError, match="Unknown accessibility"):
        make_client(accessibility_needs=["teleporter"])


@pytest.mark.parametrize("length, valid", [(300, True), (301, False)])
def test_food_notes_length_boundary(length, valid):
    if valid:
        assert len(make_client(food_notes="x" * length).food_notes) == length
    else:
        with pytest.raises(ValueError, match="300 characters"):
            make_client(food_notes="x" * length)


# ---------- What each role can see (NFR-02, NFR-15) ----------

def test_packing_summary_has_food_info_but_no_private_details(tmp_path):
    manager, _ = staff_manager(tmp_path)
    summary = manager.find_client(1).packing_summary()
    assert "household of 2 (1 adult, 1 infant)" in summary   # infant matters for packing
    assert "prefers fresh vegetables" in summary
    for private in ("0400 000 000", "Donald", "help carrying", "Recently moved", "sms"):
        assert private not in summary


def test_staff_details_include_contact_access_and_notes(tmp_path):
    manager, _ = staff_manager(tmp_path)
    details = manager.find_client(1).staff_details()
    for shown in ("Maya Donald", "0400 000 000", "sms", "help carrying", "Recently moved"):
        assert shown in details


# ---------- Saving and loading ----------

def test_new_fields_survive_save_and_reload(tmp_path):
    manager, path = staff_manager(tmp_path)
    manager.add_client("Jordan Lee", "", {"eggs": "moderate"}, ["halal"],
                       household={"adults": 2, "infants": 1}, email="j@example.com",
                       contact_method="email", accessibility_needs=["interpreter"],
                       food_notes="no pork", language="Arabic")
    client = ScheduleManager(str(path)).find_client(2)
    assert client.household == {"adults": 2, "children": 0, "infants": 1}
    assert client.contact_method == "email" and client.email == "j@example.com"
    assert client.accessibility_needs == {"interpreter"}
    assert client.language == "Arabic" and client.food_notes == "no pork"


def test_old_client_record_still_loads(tmp_path):
    path = write_data(tmp_path, clients=[
        {"id": 1, "name": "Alex Nguyen", "phone": "0411 111 111", "allergies": {"dairy": "mild"},
         "preferences": [], "household_size": 3}])
    client = ScheduleManager(str(path)).find_client(1)
    assert client.household_size == 3 and client.contact_method == "sms"


# ---------- Editing a client (FR-05) ----------

def test_update_client_changes_and_saves(tmp_path):
    manager, path = staff_manager(tmp_path)
    manager.update_client(1, household={"adults": 1, "children": 2}, language="Vietnamese")
    client = ScheduleManager(str(path)).find_client(1)
    assert client.household_size == 3 and client.language == "Vietnamese"
    assert client.private_notes[0]["text"] == "Recently moved"   # notes kept


def test_invalid_update_leaves_client_unchanged(tmp_path):
    manager, _ = staff_manager(tmp_path)
    with pytest.raises(ValueError):
        manager.update_client(1, phone="", language="French")   # sms needs a phone
    client = manager.find_client(1)
    assert client.phone == "0400 000 000" and client.language == "English"


def test_update_rejects_unknown_fields(tmp_path):
    manager, _ = staff_manager(tmp_path)
    with pytest.raises(ValueError, match="can't be changed"):
        manager.update_client(1, id=99)
    with pytest.raises(ValueError, match="can't be changed"):
        manager.update_client(1, private_notes=[])


def test_volunteer_cannot_edit_or_add_notes(tmp_path):
    path = write_data(tmp_path)
    manager = ScheduleManager(str(path))
    manager.login("sophie", "vol123", "volunteer")
    with pytest.raises(PermissionError):
        manager.update_client(1, language="French")
    with pytest.raises(PermissionError):
        manager.add_client_note(1, "hello")


# ---------- Private notes ----------

def test_add_private_note_records_author(tmp_path):
    manager, path = staff_manager(tmp_path)
    manager.add_client_note(1, "  Can only come after 5pm  ")
    note = ScheduleManager(str(path)).find_client(1).private_notes[-1]
    assert note["text"] == "Can only come after 5pm" and note["by"] == "angela"


def test_empty_note_rejected(tmp_path):
    manager, _ = staff_manager(tmp_path)
    with pytest.raises(ValueError, match="empty"):
        manager.add_client_note(1, "   ")


# ---------- End-to-end through the menus ----------

def run_app(path, typed):
    answers = iter(typed)

    def fake_input(prompt=""):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError

    out = io.StringIO()
    with patch("builtins.input", fake_input), patch("main.getpass", fake_input), \
            redirect_stdout(out):
        main.main(str(path))
    return out.getvalue()


def test_e2e_register_client_by_picking_from_lists(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "4", "y", "Jordan Lee",   # client has agreed to their details being stored
        "2", "", "1",           # 2 adults, 0 children, 1 infant
        "1",                    # dietary: halal
        "2", "2",               # allergy: eggs, moderate
        "no pork",              # food preferences
        "1", "0412 345 678",    # contact by sms, then phone number
        "Arabic",               # language
        "",                     # no accessibility needs
        "", "q",
    ])
    assert "Saved. Jordan Lee is client #2." in screen
    saved = json.loads(path.read_text())["clients"][1]
    assert saved["household"] == {"adults": 2, "children": 0, "infants": 1}
    assert saved["allergies"] == {"eggs": "moderate"}
    assert saved["preferences"] == ["halal"] and saved["contact_method"] == "sms"


def test_e2e_bad_pick_is_asked_again(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "4", "y", "Sam", "1", "", "",
        "9",                    # dietary: out of range, asked again
        "",                     # then none
        "", "", "4", "", "", "", "q",
    ])
    assert "Please type a number from 1 to 4" in screen
    assert "Saved. Sam is client #2." in screen


def test_e2e_staff_edits_client_and_adds_note_volunteer_cannot_see_it(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "8", "1",
        "n", "Needs a quiet pickup time",
        "e", "7", "Vietnamese",          # change preferred language
        "b", "", "l",
        "volunteer", "sophie", "vol123",
        "3", "", "q",
    ])
    staff_part, volunteer_part = screen.split("Welcome, Sophie Patel")
    assert "Note saved." in staff_part and "Saved." in staff_part
    assert "Preferred language: Vietnamese" in staff_part
    assert "Client details" not in volunteer_part           # no menu option for volunteers
    assert "Needs a quiet pickup time" not in volunteer_part
    assert "0400 000 000" not in volunteer_part
    assert "Client #1 (Maya)" in volunteer_part
