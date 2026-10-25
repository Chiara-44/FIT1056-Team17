# filename: hamper_item_test.py
# group: Team 17
# names: Harry
# created: 16/10/26
# last modified: 16/10/26
#
# Tests for HamperItem and how a Hamper manages its item lines (F-04, FR-18).

import json
from datetime import date, timedelta

import pytest

from app.hampers import Hamper, HamperItem
from app.schedule import ScheduleManager
from app.users import hash_password

FUTURE = (date.today() + timedelta(days=60)).isoformat()


# ---------- HamperItem (unit) ----------

@pytest.mark.parametrize("quantity, valid", [
    (1, True),        # BVA: smallest valid
    (0, False),       # BVA: just below
    (-2, False),      # EP: negative
    (True, False),    # EP: bool is not a quantity
    ("3", False),     # EP: text
])
def test_hamper_item_quantity(quantity, valid):
    if valid:
        assert HamperItem(5, quantity).quantity == quantity
    else:
        with pytest.raises(ValueError, match="at least 1"):
            HamperItem(5, quantity)


def test_hamper_item_add_and_remove():
    line = HamperItem(5, 2)
    line.add(3)
    assert line.quantity == 5
    assert line.remove(2) == 2 and line.quantity == 3
    assert line.remove(10) == 3 and line.quantity == 0   # can't remove more than is there


# ---------- Hamper lines ----------

def test_adding_same_item_twice_uses_one_line():
    hamper = Hamper(1, 1, "angela", "staff")
    hamper.add(2, 1)
    hamper.add(2, 2)
    hamper.add(3, 1)
    assert len(hamper.lines) == 2
    assert hamper.items == {2: 3, 3: 1}
    assert hamper.total_items() == 4


def test_remove_part_then_all_of_a_line():
    hamper = Hamper(1, 1, "angela", "staff", items={"2": 3})
    assert hamper.remove(2, 1) == 1 and hamper.quantity_of(2) == 2
    assert hamper.remove(2) == 2 and hamper.line_for(2) is None
    assert hamper.remove(2) == 0                          # nothing left to remove


def test_save_format_is_unchanged_for_old_data():
    hamper = Hamper(1, 1, "angela", "staff", items={"2": 3, "4": 1})
    saved = hamper.to_dict()
    assert saved["items"] == {"2": 3, "4": 1}
    assert saved["substitutions"] == {}
    assert Hamper(1, 1, "angela", "staff", items=saved["items"]).items == {2: 3, 4: 1}


# ---------- Substitution is recorded on the line (FR-18) ----------

def make_manager(tmp_path):
    data = {
        "staff": [{"id": 1, "name": "Angela", "username": "angela",
                   "password_hash": hash_password("staff123"), "role": "staff"}],
        "clients": [{"id": 1, "name": "Alex Nguyen", "phone": "0411 111 111", "allergies": {"peanuts": "severe"},
                     "preferences": [], "household_size": 2}],
        "storeroom": [
            {"id": 1, "name": "Chickpeas", "allergens": [], "may_contain": [], "preferences": [],
             "quantity": 5, "expiry": FUTURE},
            {"id": 2, "name": "Rice", "allergens": [], "may_contain": [], "preferences": [],
             "quantity": 5, "expiry": FUTURE},
            {"id": 3, "name": "Peanut butter", "allergens": ["peanuts"], "may_contain": [],
             "preferences": [], "quantity": 5, "expiry": FUTURE},
        ],
        "next_staff_id": 2, "next_client_id": 2, "next_item_id": 4,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    manager = ScheduleManager(str(path))
    manager.login("angela", "staff123", "staff")
    return manager, path


def test_substitute_marks_line_and_is_saved(tmp_path):
    manager, path = make_manager(tmp_path)
    hamper = manager.create_hamper(1)
    manager.acknowledge_allergy_warning(hamper.id)
    manager.add_hamper_item(hamper.id, 1, 2)
    manager.substitute_item(hamper.id, 1, 2)
    assert hamper.line_for(2).substituted_for == 1

    reloaded = ScheduleManager(str(path)).find_hamper(hamper.id)
    assert reloaded.line_for(2).substituted_for == 1
    assert reloaded.items == {2: 2}


def test_failed_substitution_leaves_lines_unchanged(tmp_path):
    manager, _ = make_manager(tmp_path)
    hamper = manager.create_hamper(1)
    manager.acknowledge_allergy_warning(hamper.id)
    manager.add_hamper_item(hamper.id, 1, 2)
    with pytest.raises(ValueError):
        manager.substitute_item(hamper.id, 1, 3)          # peanut butter: severe allergy
    assert hamper.items == {1: 2}
    assert hamper.line_for(1).substituted_for is None
    assert hamper.line_for(3) is None
