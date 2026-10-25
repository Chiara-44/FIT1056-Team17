# filename: report_test.py
# group: Team 17
# names: Harry
# created: 23/10/26
# last modified: 23/10/26
#
# Tests for operational reports (F-07: FR-28 to FR-32, AC-15).
# Covers who can run reports, each report type, and the expiry and shortage boundaries.

import json
from datetime import date, timedelta

import pytest

from app.schedule import ScheduleManager

TODAY = date.today()


def day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


def write_data(tmp_path):
    """Stock chosen to sit on the expiry and shortage boundaries."""
    data = {
        "volunteers": [{"id": 1, "name": "Sophie Patel", "username": "sophie",
                        "password": "vol123", "role": "volunteer"}],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [{"id": 1, "name": "Ada Admin", "username": "ada",
                    "password": "admin123", "role": "admin"}],
        "clients": [{"id": 1, "name": "Maya Donald", "phone": "0400 000 000", "allergies": {},
                     "preferences": [], "household_size": 1}],
        "storeroom": [
            {"id": 1, "name": "Milk", "allergens": [], "may_contain": [], "preferences": [],
             "quantity": 9, "expiry": day(-1)},       # expired yesterday, 9 left
            {"id": 2, "name": "Bread", "allergens": [], "may_contain": [], "preferences": [],
             "quantity": 10, "expiry": day(0)},       # expires today, 10 left
            {"id": 3, "name": "Rice", "allergens": [], "may_contain": [], "preferences": [],
             "quantity": 30, "expiry": day(1)},       # expires tomorrow
            {"id": 4, "name": "Salt", "allergens": [], "may_contain": [], "preferences": [],
             "quantity": 0, "expiry": None},          # no expiry, out of stock
        ],
        "hampers": [
            {"id": 1, "client_id": 1, "packer_username": "angela", "packer_role": "staff",
             "items": {"3": 2}, "status": "completed", "allergy_acknowledged": True},
            {"id": 2, "client_id": 1, "packer_username": "angela", "packer_role": "staff",
             "items": {"3": 1}, "status": "completed", "allergy_acknowledged": True},
            {"id": 3, "client_id": 1, "packer_username": "angela", "packer_role": "staff",
             "items": {}, "status": "draft", "allergy_acknowledged": False},
        ],
        "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 2,
        "next_client_id": 2, "next_item_id": 5, "next_hamper_id": 4,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def manager_as(tmp_path, username, password, role):
    manager = ScheduleManager(str(write_data(tmp_path)))
    manager.login(username, password, role)
    return manager


@pytest.fixture
def admin(tmp_path):
    return manager_as(tmp_path, "ada", "admin123", "admin")


# ---------- Who can run reports (FR-03, NFR-02) ----------

@pytest.mark.parametrize("username, password, role", [
    ("angela", "staff123", "staff"),       # EP: staff
    ("sophie", "vol123", "volunteer"),     # EP: volunteer
])
def test_only_admin_can_run_reports(tmp_path, username, password, role):
    manager = manager_as(tmp_path, username, password, role)
    with pytest.raises(PermissionError):
        manager.generate_report("stock")


def test_logged_out_user_cannot_run_reports(tmp_path):
    manager = ScheduleManager(str(write_data(tmp_path)))
    with pytest.raises(PermissionError):
        manager.generate_report("stock")


def test_unknown_report_type_rejected(admin):
    with pytest.raises(ValueError, match="Unknown report type"):
        admin.generate_report("profits")


# ---------- FR-28 Current stock ----------

def test_stock_report_lists_every_item_with_quantity(admin):
    report = admin.generate_report("stock")
    assert {(r["name"], r["quantity"]) for r in report} == {
        ("Milk", 9), ("Bread", 10), ("Rice", 30), ("Salt", 0)}


# ---------- FR-29 Expiry (BVA around today) ----------

def test_expiry_report_boundary(admin):
    names = {r["name"] for r in admin.generate_report("expiry")}
    assert "Milk" in names          # BVA: expired yesterday
    assert "Bread" in names         # BVA: expires today
    assert "Rice" not in names      # BVA: expires tomorrow
    assert "Salt" not in names      # EP: no expiry date


# ---------- FR-30 Shortages (BVA around 10) ----------

def test_shortage_report_boundary(admin):
    names = {r["name"] for r in admin.generate_report("shortages")}
    assert "Milk" in names          # BVA: 9, just below the limit
    assert "Bread" not in names     # BVA: 10, on the limit
    assert "Salt" in names          # BVA: 0, out of stock
    assert "Rice" not in names      # EP: well stocked


# ---------- FR-31 Donations ----------

def test_donation_report_includes_new_donation(tmp_path):
    manager = manager_as(tmp_path, "angela", "staff123", "staff")
    manager.record_donation("Pasta", [], [], [], 5, day(30), "Jessi Lim")
    manager.logout()
    manager.login("ada", "admin123", "admin")
    donations = manager.generate_report("donations")
    assert donations[-1]["name"] == "Pasta"
    assert donations[-1]["quantity"] == 5 and donations[-1]["donor"] == "Jessi Lim"


# ---------- FR-32 Hamper distribution ----------

def test_hamper_report_counts_completed_and_drafts(admin):
    assert admin.generate_report("hampers") == {"total_completed": 2, "total_drafts": 1}
