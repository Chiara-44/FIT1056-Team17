# filename: menu_test.py
# group: Team 17
# names: Harry
# created: 24/10/26
# last modified: 24/10/26
#
# End-to-end tests for the stock search, stock adjustment, role change and
# report menus (FR-02, FR-10 to FR-12, FR-28 to FR-32).

import io
import json
from contextlib import redirect_stdout
from datetime import date, timedelta
from unittest.mock import patch

import main

FUTURE = (date.today() + timedelta(days=60)).isoformat()
SOON = (date.today() + timedelta(days=2)).isoformat()


def write_data(tmp_path):
    data = {
        "volunteers": [{"id": 1, "name": "Sophie Patel", "username": "sophie",
                        "password": "vol123", "role": "volunteer"}],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [{"id": 1, "name": "Ada Admin", "username": "ada",
                    "password": "admin123", "role": "admin"}],
        "clients": [],
        "storeroom": [
            {"id": 1, "name": "Peanut butter", "allergens": ["peanuts"], "may_contain": [],
             "preferences": ["vegan"], "quantity": 10, "expiry": FUTURE},
            {"id": 2, "name": "Chickpeas", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 24, "expiry": FUTURE},
            {"id": 3, "name": "Bread", "allergens": ["gluten"], "may_contain": [],
             "preferences": ["vegan"], "quantity": 6, "expiry": SOON},
        ],
        "stock_reports": [{"id": 1, "item_id": 2, "problem": "damaged", "quantity": 3,
                           "reported_by": "sophie"}],
        "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 2,
        "next_client_id": 1, "next_item_id": 4, "next_report_id": 2,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


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


def test_e2e_volunteer_searches_for_peanut_free_stock(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "volunteer", "sophie", "vol123",
        "13", "", "5", "", "y", "",     # no name, leave out peanuts (5th in the list), in stock only
        "", "q",
    ])
    results = screen.split("item(s) found.")[1]
    assert "2 item(s) found." in screen
    assert "Chickpeas" in results and "Bread" in results and "Peanut butter" not in results
    assert "NEAR EXPIRY" in results                      # bread expires in 2 days (FR-12)


def test_e2e_staff_removes_damaged_stock_and_closes_report(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "14", "2", "1",                 # chickpeas, change the quantity
        "1", "3", "Cans dented", "1",   # reason damaged, 3, note, closes report #1
        "",
        "12", "", "q",
    ])
    assert "Done. Chickpeas now has 21 in stock." in screen
    assert "Nothing reported." in screen
    saved = json.loads(path.read_text())
    assert saved["stock_adjustments"][0]["reason"] == "damaged"
    assert saved["stock_reports"][0]["resolved"] is True


def test_e2e_removing_too_much_stock_shows_message(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "14", "3", "1", "4", "50", "", "",   # discard 50 bread, only 6
        "", "q",
    ])
    assert "Can't do that: There are only 6 x Bread in stock" in screen
    assert json.loads(path.read_text())["storeroom"][2]["quantity"] == 6


def test_e2e_staff_marks_batch_contaminated(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "14", "1", "2", "3",            # peanut butter, mark condition, contaminated
        "", "1", "", "q",
    ])
    assert "Peanut butter is now marked as contaminated." in screen
    assert "** CONTAMINATED **" in screen


def test_e2e_admin_promotes_volunteer_who_then_logs_in_as_staff(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "admin", "ada", "admin123",
        "15", "3", "1",                 # 3rd user listed is Sophie; new role staff
        "", "l",
        "staff", "sophie", "vol123", "q",
    ])
    assert "Sophie Patel is now staff." in screen
    assert "Welcome, Sophie Patel! You're logged in as staff." in screen


def test_e2e_admin_runs_shortage_report_and_staff_cannot(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "admin", "ada", "admin123",
        "16", "3", "", "l",             # shortages report
        "staff", "angela", "staff123",
        "16", "q",
    ])
    report = screen.split("Shortages (under 10 left)")[-1]
    assert "name: Bread, quantity: 6" in report
    assert "Chickpeas" not in report.split("Press Enter")[0]
    assert "Please choose one of the options shown." in screen   # staff has no option 16
