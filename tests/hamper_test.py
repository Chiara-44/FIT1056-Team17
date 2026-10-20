# filename: hamper_test.py
# group: Team 17
# names: Chiara
# created: 11/10/26
# last modified: 11/10/26
#
# Unit tests for permissions, donations and the hamper workflow (UC-01).
# Each test builds its own data file in a temporary folder, so the real data is never touched.

import json
from datetime import date, timedelta

import pytest

from app.schedule import ScheduleManager
from app.users import hash_password

FUTURE = (date.today() + timedelta(days=60)).isoformat()
PAST = (date.today() - timedelta(days=1)).isoformat()


def make_manager(tmp_path):
    data = {
        "volunteers": [{"id": 1, "name": "Sam Lee", "username": "sam",
                        "password_hash": hash_password("vol123"), "role": "volunteer"}],
        "staff": [{"id": 1, "name": "Priya Shah", "username": "priya",
                   "password_hash": hash_password("staff123"), "role": "staff"}],
        "admins": [{"id": 1, "name": "Admin", "username": "admin",
                    "password_hash": hash_password("admin123"), "role": "admin"}],
        "clients": [
            {"id": 1, "name": "Maya Donald", "phone": "0400 000 000",
             "allergies": {"peanuts": "severe"}, "preferences": ["vegan"], "household_size": 1},
            {"id": 2, "name": "Alex Nguyen", "phone": "0411 111 111",
             "allergies": {"dairy": "mild"}, "preferences": [], "household_size": 3},
        ],
        "storeroom": [
            {"id": 1, "name": "Peanut butter", "allergens": ["peanuts"], "may_contain": [],
             "preferences": ["vegan", "vegetarian"], "quantity": 10, "expiry": FUTURE},
            {"id": 2, "name": "Chickpeas", "allergens": [], "may_contain": [],
             "preferences": ["vegan", "vegetarian", "halal"], "quantity": 5, "expiry": FUTURE},
            {"id": 3, "name": "Rice", "allergens": [], "may_contain": [],
             "preferences": ["vegan", "vegetarian"], "quantity": 2, "expiry": FUTURE},
            {"id": 4, "name": "Old bread", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 3, "expiry": PAST},
            {"id": 5, "name": "Tuna", "allergens": ["fish"], "may_contain": [],
             "preferences": ["halal"], "quantity": 4, "expiry": FUTURE},
        ],
        "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 2,
        "next_client_id": 3, "next_item_id": 6,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return ScheduleManager(str(path)), path


def logged_in(tmp_path, username="priya", password="staff123", role="staff"):
    manager, path = make_manager(tmp_path)
    assert manager.login(username, password, role) is not None
    return manager, path


# ---------- Permissions (FR-03) ----------

def test_not_logged_in_is_refused(tmp_path):
    manager, _ = make_manager(tmp_path)
    with pytest.raises(PermissionError):
        manager.create_hamper(1)


def test_volunteer_cannot_add_clients(tmp_path):
    manager, _ = logged_in(tmp_path, "sam", "vol123", "volunteer")
    with pytest.raises(PermissionError):
        manager.add_client("New", "", {}, [], 1)


def test_volunteer_can_pack_hamper(tmp_path):
    manager, _ = logged_in(tmp_path, "sam", "vol123", "volunteer")
    hamper = manager.create_hamper(2)
    assert hamper.packer_username == "sam"


def test_failed_login_logs_out_previous_user(tmp_path):
    manager, _ = logged_in(tmp_path)
    assert manager.login("priya", "wrong", "staff") is None
    assert manager.current_user is None


def test_only_admin_can_add_users_once_admin_exists(tmp_path):
    manager, _ = logged_in(tmp_path)
    with pytest.raises(PermissionError):
        manager.add_user("X", "x", "secret1", "volunteer")
    manager.login("admin", "admin123", "admin")
    assert manager.add_user("X", "x", "secret1", "volunteer").role == "volunteer"


# ---------- Hamper workflow (UC-01, FR-14 to FR-19) ----------

def test_severe_allergy_must_be_acknowledged_before_adding(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(1)
    with pytest.raises(PermissionError):
        manager.add_hamper_item(hamper.id, 2, 1)
    manager.acknowledge_allergy_warning(hamper.id)
    manager.add_hamper_item(hamper.id, 2, 1)
    assert hamper.items == {2: 1}


def test_no_acknowledgement_needed_without_severe_allergy(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    manager.add_hamper_item(hamper.id, 2, 2)
    assert hamper.quantity_of(2) == 2


def test_allergen_item_is_blocked(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(1)
    manager.acknowledge_allergy_warning(hamper.id)
    with pytest.raises(ValueError, match="peanuts"):
        manager.add_hamper_item(hamper.id, 1, 1)
    assert hamper.items == {}


def test_item_not_meeting_diet_is_blocked(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(1)  # client 1 is vegan
    manager.acknowledge_allergy_warning(hamper.id)
    with pytest.raises(ValueError, match="vegan"):
        manager.add_hamper_item(hamper.id, 5, 1)


def test_expired_item_is_blocked(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    with pytest.raises(ValueError, match="expiry"):
        manager.add_hamper_item(hamper.id, 4, 1)


def test_cannot_add_more_than_in_stock(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    manager.add_hamper_item(hamper.id, 3, 2)  # boundary: exactly all the stock
    with pytest.raises(ValueError, match="Only 0"):
        manager.add_hamper_item(hamper.id, 3, 1)  # boundary: one more than stock


@pytest.mark.parametrize("bad_quantity", [0, -1, "abc"])
def test_invalid_quantity_rejected(tmp_path, bad_quantity):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    with pytest.raises(ValueError):
        manager.add_hamper_item(hamper.id, 2, bad_quantity)


def test_complete_hamper_deducts_stock_and_saves(tmp_path):
    manager, path = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    manager.add_hamper_item(hamper.id, 2, 3)
    manager.complete_hamper(hamper.id)
    assert manager.find_item(2).quantity == 2

    reloaded = ScheduleManager(str(path))
    assert reloaded.find_item(2).quantity == 2
    assert reloaded.find_hamper(hamper.id).status == "completed"


def test_completed_hamper_cannot_be_completed_again(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    manager.add_hamper_item(hamper.id, 2, 1)
    manager.complete_hamper(hamper.id)
    with pytest.raises(ValueError, match="already been completed"):
        manager.complete_hamper(hamper.id)
    assert manager.find_item(2).quantity == 4  # only deducted once


def test_empty_hamper_cannot_be_completed(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    with pytest.raises(ValueError, match="empty"):
        manager.complete_hamper(hamper.id)


def test_failed_completion_leaves_stock_unchanged(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    manager.add_hamper_item(hamper.id, 2, 1)
    manager.add_hamper_item(hamper.id, 3, 2)
    manager.find_item(3).quantity = 1  # someone else used the rice meanwhile
    with pytest.raises(ValueError):
        manager.complete_hamper(hamper.id)
    assert manager.find_item(2).quantity == 5
    assert hamper.is_draft()


def test_cancel_hamper_uses_no_stock(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    manager.add_hamper_item(hamper.id, 2, 2)
    manager.cancel_hamper(hamper.id)
    assert manager.find_hamper(hamper.id) is None
    assert manager.find_item(2).quantity == 5


def test_substitution_creates_respectful_note(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(2)
    manager.add_hamper_item(hamper.id, 3, 1)
    note = manager.substitute_item(hamper.id, 3, 2)
    assert hamper.items == {2: 1}
    assert "Chickpeas instead of Rice" in note
    assert "dairy" not in note and "allerg" not in note  # no medical details in the note


def test_unsafe_substitution_is_rolled_back(tmp_path):
    manager, _ = logged_in(tmp_path)
    hamper = manager.create_hamper(1)
    manager.acknowledge_allergy_warning(hamper.id)
    manager.add_hamper_item(hamper.id, 2, 1)
    with pytest.raises(ValueError):
        manager.substitute_item(hamper.id, 2, 1)  # peanut butter for a peanut allergy
    assert hamper.items == {2: 1}
    assert hamper.substitution_notes == []


# ---------- Donations (FR-09, FR-10) ----------

def test_donation_adds_to_matching_batch(tmp_path):
    manager, _ = logged_in(tmp_path)
    existing = manager.find_item(2)
    before = existing.quantity
    item = manager.record_donation(
        existing.name, sorted(existing.allergens), sorted(existing.may_contain),
        sorted(existing.preferences), 4, existing.expiry, "Local Grocer")
    assert item.id == 2
    assert item.quantity == before + 4


def test_donation_with_new_expiry_creates_new_batch(tmp_path):
    manager, _ = logged_in(tmp_path)
    later = (date.today() + timedelta(days=90)).isoformat()
    item = manager.record_donation("Chickpeas", [], [], ["vegan"], 4, later)
    assert item.id == 6


def test_expired_donation_rejected(tmp_path):
    manager, _ = logged_in(tmp_path)
    with pytest.raises(ValueError, match="expired"):
        manager.record_donation("Milk", ["dairy"], [], [], 2, PAST)


def test_volunteer_cannot_record_donation(tmp_path):
    manager, _ = logged_in(tmp_path, "sam", "vol123", "volunteer")
    with pytest.raises(PermissionError):
        manager.record_donation("Rice", [], [], [], 1)


# ---------- Privacy (NFR-02, NFR-15) ----------

def test_packing_summary_hides_contact_details(tmp_path):
    manager, _ = make_manager(tmp_path)
    summary = manager.find_client(1).packing_summary()
    assert "0400" not in summary and "Donald" not in summary
    assert "peanuts (severe)" in summary


@pytest.mark.parametrize("size, ok", [(0, False), (1, True), (20, True), (21, False)])
def test_household_size_boundaries(tmp_path, size, ok):
    manager, _ = logged_in(tmp_path)
    if ok:
        assert manager.add_client("Test", "", {}, [], size).household_size == size
    else:
        with pytest.raises(ValueError):
            manager.add_client("Test", "", {}, [], size)
