# filename: human_centred_test.py
# group: Team 17
# names: Harry
# created: 25/10/26
# last modified: 25/10/26
#
# Tests for the human-centred requirements in Section 4.6 of the report:
# consent before a client's details are stored (privacy and consent, NFR-03) and the
# same hamper allowance per household member for every client (fairness, NFR-13).

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

import main
from app.clients import ITEMS_PER_PERSON
from app.schedule import ScheduleManager


def write_data(tmp_path):
    data = {
        "volunteers": [],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [],
        "clients": [
            {"id": 1, "name": "Maya Donald", "phone": "0400 000 000", "allergies": {},
             "preferences": ["vegan"], "household": {"adults": 1}},
            {"id": 2, "name": "Lena Ruiz", "phone": "0411 111 111", "allergies": {},
             "preferences": ["vegan"], "household": {"adults": 1}},
            {"id": 3, "name": "Tom Okafor", "phone": "0412 345 678", "allergies": {},
             "preferences": [], "household": {"adults": 2, "children": 1}},
        ],
        "storeroom": [
            {"id": 1, "name": "Rice", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 100, "expiry": None},
            {"id": 2, "name": "Chickpeas", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 100, "expiry": None},
        ],
        "next_volunteer_id": 1, "next_staff_id": 2, "next_admin_id": 1,
        "next_client_id": 4, "next_item_id": 3,
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


# ---------- Privacy and consent ----------

def test_client_without_consent_is_not_saved(tmp_path):
    manager = staff_manager(tmp_path)
    with pytest.raises(ValueError, match="agree"):
        manager.add_client("Jordan Lee", "0412 000 000", {}, [], consent=False)
    assert len(manager.clients) == 3


def test_consent_date_is_saved_and_shown_to_staff(tmp_path):
    manager = staff_manager(tmp_path)
    client = manager.add_client("Jordan Lee", "0412 000 000", {}, [], consent=True)
    saved = json.loads((tmp_path / "data.json").read_text())["clients"][-1]
    assert saved["consent_date"] == client.consent_date is not None
    assert "Consent to store details: given on" in client.staff_details()
    assert "Consent" not in client.packing_summary()          # volunteers don't see it


def test_consent_date_kept_when_client_is_edited(tmp_path):
    manager = staff_manager(tmp_path)
    client = manager.add_client("Jordan Lee", "0412 000 000", {}, [], consent=True)
    edited = manager.update_client(client.id, language="Arabic")
    assert edited.consent_date == client.consent_date


def test_cli_explains_why_and_saves_nothing_without_consent(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, ["staff", "angela", "staff123", "4", "n", "", "q"])
    assert "so no unsafe food is packed" in screen          # explains why details are needed
    assert "Nothing was saved." in screen
    assert len(json.loads(path.read_text())["clients"]) == 3


# ---------- Fairness: the same allowance per person ----------

@pytest.mark.parametrize("quantity, allowed", [
    (ITEMS_PER_PERSON - 1, True),   # BVA: one under the allowance
    (ITEMS_PER_PERSON, True),       # BVA: exactly the allowance
    (ITEMS_PER_PERSON + 1, False),  # BVA: one over
])
def test_hamper_allowance_boundary(tmp_path, quantity, allowed):
    manager = staff_manager(tmp_path)
    hamper = manager.create_hamper(1)                       # household of 1
    if allowed:
        manager.add_hamper_item(hamper.id, 1, quantity)
        assert hamper.total_items() == quantity
    else:
        with pytest.raises(ValueError, match="can hold up to 5 items"):
            manager.add_hamper_item(hamper.id, 1, quantity)
        assert hamper.total_items() == 0


def test_allowance_counts_every_item_in_the_hamper(tmp_path):
    manager = staff_manager(tmp_path)
    hamper = manager.create_hamper(1)
    manager.add_hamper_item(hamper.id, 1, 3)
    with pytest.raises(ValueError, match="already has 3"):
        manager.add_hamper_item(hamper.id, 2, 3)


def test_allowance_grows_with_household_size(tmp_path):
    manager = staff_manager(tmp_path)
    tom = manager.find_client(3)                            # 2 adults and 1 child
    assert tom.hamper_allowance == 3 * ITEMS_PER_PERSON
    hamper = manager.create_hamper(3)
    manager.add_hamper_item(hamper.id, 1, 3 * ITEMS_PER_PERSON)
    assert hamper.total_items() == 15


def test_equivalent_clients_get_the_same_items_and_allowance(tmp_path):
    manager = staff_manager(tmp_path)
    maya, lena = manager.find_client(1), manager.find_client(2)
    assert maya.hamper_allowance == lena.hamper_allowance
    assert ([i.id for i in manager.safe_items_for(maya)]
            == [i.id for i in manager.safe_items_for(lena)])


def test_cli_shows_allowance_while_packing(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, ["staff", "angela", "staff123", "5", "2", "x", "", "q"])
    assert "0 of 5 items" in screen

