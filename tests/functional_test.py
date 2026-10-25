# filename: functional_test.py
# group: Team 17
# names: Chiara
# created: 11/10/26
# last modified: 11/10/26
#
# Functional and end-to-end tests (Deliverable 2, section 11.3).
# - End-to-end (E2E) tests drive the real command-line menus by feeding in typed answers,
#   exactly as a user would, and check what the screen shows and what gets saved.
# - Equivalence partitioning (EP) and boundary value analysis (BVA) tests for inputs.
# - MC/DC tests for the two key safety decisions.

import io
import json
from contextlib import redirect_stdout
from datetime import date, timedelta
from unittest.mock import patch

import pytest

import main
from app.clients import Client
from app.schedule import ScheduleManager
from app.storeroom import FoodbankItem

TODAY = date.today()
FUTURE = (TODAY + timedelta(days=60)).isoformat()
PAST = (TODAY - timedelta(days=1)).isoformat()


def write_data(tmp_path):
    """Sample data with plain-text passwords (hashed automatically on first load)."""
    data = {
        "volunteers": [{"id": 1, "name": "Sophie Patel", "username": "sophie",
                        "password": "vol123", "role": "volunteer"}],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [{"id": 1, "name": "Admin", "username": "admin",
                    "password": "admin123", "role": "admin"}],
        "clients": [
            {"id": 1, "name": "Maya Donald", "phone": "0400 000 000",
             "allergies": {"peanuts": "severe", "tree nuts": "severe"},
             "preferences": ["vegan"], "household_size": 1},
        ],
        "storeroom": [
            {"id": 1, "name": "Peanut butter", "allergens": ["peanuts"], "may_contain": [],
             "preferences": ["vegan"], "quantity": 10, "expiry": FUTURE},
            {"id": 2, "name": "Chickpeas", "allergens": [], "may_contain": [],
             "preferences": ["vegan", "vegetarian"], "quantity": 24, "expiry": FUTURE},
            {"id": 3, "name": "Rice", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 30, "expiry": FUTURE},
        ],
        "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 2,
        "next_client_id": 2, "next_item_id": 4,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def run_app(path, typed):
    """Runs main.main() with the given lines typed in. Returns everything printed."""
    answers = iter(typed)

    def fake_input(prompt=""):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError  # ran out of typed answers: the app should exit cleanly

    out = io.StringIO()
    with patch("builtins.input", fake_input), patch("main.getpass", fake_input), \
            redirect_stdout(out):
        main.main(str(path))
    return out.getvalue()


# ---------- End-to-end scenarios ----------

def test_e2e_01_staff_prepares_safe_hamper(tmp_path):
    """UC-01 main flow plus allergy-conflict alternative flow (FR-14 to FR-17, AC-08 to AC-10)."""
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "5", "1",            # prepare a hamper for client 1 (Maya)
        "no", "YES",         # warning must be confirmed with YES
        "a", "1", "1",       # try peanut butter: should be blocked
        "a", "2", "2",       # add 2 chickpeas
        "c", "",             # complete, then press Enter
        "q",
    ])
    assert "SEVERE ALLERGY WARNING" in screen
    assert "Please type YES to continue or X to go back." in screen
    assert "Peanut butter is not safe for this client: contains peanuts" in screen
    assert "is complete and stock has been updated" in screen

    saved = json.loads(path.read_text())
    chickpeas = next(i for i in saved["storeroom"] if i["id"] == 2)
    assert chickpeas["quantity"] == 22
    assert saved["hampers"][0]["status"] == "completed"
    assert saved["hampers"][0]["allergy_acknowledged"] is True


def test_e2e_02_volunteer_sees_limited_menu_and_no_contact_details(tmp_path):
    """Role-based access and privacy (FR-03, NFR-02, AC-02)."""
    path = write_data(tmp_path)
    screen = run_app(path, ["volunteer", "sophie", "vol123", "3", "", "2", "q"])
    assert "Record a donation" not in screen
    assert "Register a client" not in screen
    assert "Client #1 (Maya)" in screen
    assert "0400 000 000" not in screen and "Donald" not in screen
    assert "Please choose one of the options shown." in screen  # typing 2 is refused


def test_e2e_03_wrong_password_then_correct(tmp_path):
    """Login (FR-01, AC-01) with a clear, non-revealing error (NFR-07)."""
    path = write_data(tmp_path)
    screen = run_app(path, ["staff", "angela", "wrong", "staff", "angela", "staff123", "q"])
    assert "That username and password don't match" in screen
    assert "Welcome, Angela Bjork!" in screen


def test_e2e_04_staff_records_donation(tmp_path):
    """Recording a donation updates stock and history (FR-09, FR-10, AC-05)."""
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "2", "Rice", "5", "", "", "3", FUTURE, "Jessi Lim", "",
        "q",
    ])
    assert "Rice now has 35 in stock" in screen
    saved = json.loads(path.read_text())
    assert saved["donations"][0]["donor"] == "Jessi Lim"


def test_e2e_05_invalid_donation_input_is_asked_again(tmp_path):
    """Fault tolerance (NFR-07): a typo gives a clear message and the app keeps running."""
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "2", "Muesli", "4",
        "nutz", "",          # bad pick, asked again, then none
        "", "",              # may contain: none, suitable for: none
        "2026-13-45", "",    # bad date, asked again, then no expiry
        "", "",              # no donor, press Enter
        "1", "",             # app is still usable afterwards
        "q",
    ])
    assert "Please type a number from 1 to 9" in screen
    assert "Expiry date must look like DD/MM/YYYY or YYYY-MM-DD" in screen
    assert "Muesli now has 4 in stock" in screen


def test_e2e_06_substitution_note(tmp_path):
    """Substitution flow (FR-18, FR-19, AC-11)."""
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "5", "1", "YES",
        "a", "2", "1",
        "s", "2", "3",       # swap chickpeas for rice
        "c", "", "q",
    ])
    assert "We've included Rice instead of Chickpeas today" in screen
    saved = json.loads(path.read_text())
    assert saved["hampers"][0]["substitution_notes"]


def test_e2e_07_admin_creates_user_who_can_log_in(tmp_path):
    """Admin-only account creation (FR-02 partial)."""
    path = write_data(tmp_path)
    screen = run_app(path, [
        "admin", "admin", "admin123",
        "6", "Sam Lee", "sam", "1", "secret1", "",
        "l",
        "volunteer", "sam", "secret1", "q",
    ])
    print(screen)
    assert "Created volunteer account 'sam'" in screen
    assert "Welcome, Sam Lee!" in screen


def test_e2e_08_corrupt_data_file_reports_error(tmp_path):
    """Fault tolerance (NFR-11): a damaged data file gives a message, not a crash."""
    path = tmp_path / "data.json"
    path.write_text("{ this is not json")
    screen = run_app(path, [])
    assert "couldn't start" in screen
    assert path.read_text() == "{ this is not json"  # never overwritten


# ---------- Equivalence partitioning and boundary values ----------

def logged_in_manager(tmp_path):
    manager = ScheduleManager(str(write_data(tmp_path)))
    manager.login("angela", "staff123", "staff")
    return manager


@pytest.mark.parametrize("quantity, valid", [
    (5, True),       # EP: valid positive whole number
    (1, True),       # BVA: smallest valid
    (0, False),      # BVA: just below valid
    (-3, False),     # EP: negative
    ("two", False),  # EP: not a number
])
def test_donation_quantity_partitions(tmp_path, quantity, valid):
    manager = logged_in_manager(tmp_path)
    if valid:
        assert manager.record_donation("Beans", [], [], ["vegan"], quantity, FUTURE).quantity == quantity
    else:
        with pytest.raises(ValueError):
            manager.record_donation("Beans", [], [], ["vegan"], quantity, FUTURE)


@pytest.mark.parametrize("days_from_today, accepted", [(-1, False), (0, True), (1, True)])
def test_expiry_date_boundary(tmp_path, days_from_today, accepted):
    """BVA around today: yesterday is expired; today and tomorrow are still usable."""
    manager = logged_in_manager(tmp_path)
    expiry = (TODAY + timedelta(days=days_from_today)).isoformat()
    if accepted:
        manager.record_donation("Bread", [], [], ["vegan"], 3, expiry)
    else:
        with pytest.raises(ValueError, match="expired"):
            manager.record_donation("Bread", [], [], ["vegan"], 3, expiry)


@pytest.mark.parametrize("text, valid", [
    ("2026-12-31", True), ("31/12/2026", True), ("12-31-2026", False), ("2026-02-30", False),
    ("", True),
])
def test_expiry_date_format_partitions(tmp_path, text, valid):
    """EP: ISO date, Australian date, wrong format, impossible date, blank (no expiry)."""
    manager = logged_in_manager(tmp_path)
    if valid:
        manager.add_item("Item", [], [], [], 1, text or None)
    else:
        with pytest.raises(ValueError):
            manager.add_item("Item", [], [], [], 1, text)


# ---------- MC/DC: allergy blocking decision (FR-16) ----------
# An item is blocked for an allergen when:  A or (B and C)
#   A = item contains the allergen
#   B = item may contain traces of the allergen
#   C = the client's allergy is severe
# Four cases give MC/DC: each condition is shown to change the outcome on its own.
#   Case 1 vs 4: only A changes -> outcome changes
#   Case 2 vs 4: only B changes -> outcome changes
#   Case 2 vs 3: only C changes -> outcome changes

@pytest.mark.parametrize("case, contains, may_contain, severe, blocked", [
    (1, True,  False, True,  True),
    (2, False, True,  True,  True),
    (3, False, True,  False, False),
    (4, False, False, True,  False),
])
def test_mcdc_allergy_decision(case, contains, may_contain, severe, blocked):
    item = FoodbankItem(1, "Test", ["peanuts"] if contains else [],
                        ["peanuts"] if may_contain else [], [], 5)
    client = Client(1, "Test", "", {"peanuts": "severe" if severe else "mild"}, [])
    assert (not client.can_have(item)) == blocked


# ---------- MC/DC: severe-allergy acknowledgement needed (FR-17) ----------
# Acknowledgement is needed when:  S and not K
#   S = client has a severe allergy,  K = packer has already acknowledged

@pytest.mark.parametrize("severe, acknowledged, needs_ack", [
    (True,  False, True),   # base case
    (False, False, False),  # only S changes -> outcome changes
    (True,  True,  False),  # only K changes -> outcome changes
])
def test_mcdc_acknowledgement_decision(tmp_path, severe, acknowledged, needs_ack):
    manager = logged_in_manager(tmp_path)
    allergies = {"sesame": "severe" if severe else "mild"}
    client = manager.add_client("Test Client", "", allergies, [], 1)
    hamper = manager.create_hamper(client.id)
    if acknowledged:
        manager.acknowledge_allergy_warning(hamper.id)
    if needs_ack:
        with pytest.raises(PermissionError):
            manager.add_hamper_item(hamper.id, 2, 1)
    else:
        manager.add_hamper_item(hamper.id, 2, 1)
        assert hamper.quantity_of(2) == 1
