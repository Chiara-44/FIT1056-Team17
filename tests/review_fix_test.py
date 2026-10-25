# filename: review_fix_test.py
# group: Team 17
# names: Bao Nguyen
# created: 25/10/26
# last modified: 25/10/26
#
# Tests for the fixes made after the Deliverable 2 review: two sessions saving the
# same data file (NFR-12), client privacy in the service layer (NFR-02, NFR-15)
# and the expiry report window (FR-29).

from datetime import date, timedelta

import pytest

from app.clients import Client, ClientPackingView
from app.schedule import ScheduleManager
from app.storeroom import NEAR_EXPIRY_DAYS


@pytest.fixture
def path(tmp_path):
    p = str(tmp_path / "data.json")
    m = ScheduleManager(p)
    m.add_user("Ada Admin", "ada", "admin123", "admin")
    m.login("ada", "admin123", "admin")
    m.add_user("Angela Bjork", "angela", "staff123", "staff")
    m.add_user("Sophie Patel", "sophie", "vol123", "volunteer")
    m.logout()
    m.login("angela", "staff123", "staff")
    m.add_client("Maya Donald", "0412345678", {"peanuts": "severe"}, ["vegan"], 2)
    m.add_client_note(1, "Prefers a quiet pickup time")
    return p


def staff(path):
    m = ScheduleManager(path)
    m.login("angela", "staff123", "staff")
    return m


def volunteer(path):
    m = ScheduleManager(path)
    m.login("sophie", "vol123", "volunteer")
    return m


# ---------- Two sessions saving the same file (NFR-12) ----------

def test_stale_session_cannot_overwrite_another_save(path):
    a, b = staff(path), staff(path)
    a.record_donation("Chickpeas", [], [], ["vegan"], 12)
    with pytest.raises(ValueError, match="Someone else saved"):
        b.record_donation("Rice", [], [], ["vegan"], 5)
    names = {i.name for i in ScheduleManager(path).storeroom}
    assert "Chickpeas" in names and "Rice" not in names


def test_retry_after_conflict_keeps_both_changes(path):
    a, b = staff(path), staff(path)
    a.record_donation("Chickpeas", [], [], ["vegan"], 12)
    with pytest.raises(ValueError):
        b.record_donation("Rice", [], [], ["vegan"], 5)
    b.record_donation("Rice", [], [], ["vegan"], 5)  # b has reloaded, so the retry works
    names = {i.name for i in ScheduleManager(path).storeroom}
    assert {"Chickpeas", "Rice"} <= names


def test_reload_if_changed_picks_up_other_saves(path):
    a, b = staff(path), staff(path)
    assert b.reload_if_changed() is False   # nothing changed yet
    a.record_donation("Chickpeas", [], [], ["vegan"], 12)
    assert b.reload_if_changed() is True
    assert any(i.name == "Chickpeas" for i in b.storeroom)
    b.record_donation("Rice", [], [], ["vegan"], 5)  # no conflict after reloading
    assert len(ScheduleManager(path).donations) == 2


def test_reload_keeps_user_logged_in(path):
    a, b = staff(path), staff(path)
    a.record_donation("Chickpeas", [], [], ["vegan"], 12)
    b.reload_if_changed()
    assert b.current_user is not None and b.current_user.username == "angela"


# ---------- Client privacy in the service layer (NFR-02, NFR-15) ----------

def test_staff_get_full_client_record(path):
    m = staff(path)
    client = m.find_client(1)
    assert isinstance(client, Client)
    assert client.phone == "0412345678"


def test_volunteer_gets_packing_view_only(path):
    m = volunteer(path)
    client = m.find_client(1)
    assert isinstance(client, ClientPackingView)
    assert client.name == "Maya"
    assert client.severe_allergies() == ["peanuts"]
    assert "Maya" in client.packing_summary()


@pytest.mark.parametrize("hidden", ["phone", "email", "private_notes", "accessibility_needs",
                                    "contact_method", "staff_details", "to_dict"])
def test_volunteer_cannot_read_private_fields(path, hidden):
    client = volunteer(path).find_client(1)
    with pytest.raises(PermissionError):
        getattr(client, hidden)


def test_volunteer_client_list_is_packing_views(path):
    clients = volunteer(path).list_clients()
    assert len(clients) == 1 and isinstance(clients[0], ClientPackingView)


def test_packing_view_cannot_be_changed(path):
    client = volunteer(path).find_client(1)
    with pytest.raises(PermissionError):
        client.phone = "0400000000"


def test_logged_out_user_cannot_list_clients(path):
    with pytest.raises(PermissionError):
        ScheduleManager(path).list_clients()


def test_volunteer_can_still_pack_with_view(path):
    m = volunteer(path)
    client = m.get_client_for_packing(1)
    assert m.safe_items_for(client) == []   # works with the view (no stock yet)


# ---------- Expiry report window (FR-29) ----------

@pytest.mark.parametrize("days, expected", [
    (-1, "expired"),                         # already expired
    (0, "near expiry"),                      # expires today
    (NEAR_EXPIRY_DAYS, "near expiry"),       # BVA: last day of the window
    (NEAR_EXPIRY_DAYS + 1, None),            # BVA: just outside the window
])
def test_expiry_report_window(path, days, expected):
    m = staff(path)
    m.add_item("Milk", [], [], [], 3, (date.today() + timedelta(days=days)).isoformat())
    m.logout()
    m.login("ada", "admin123", "admin")
    rows = [r for r in m.generate_report("expiry") if r["name"] == "Milk"]
    if expected is None:
        assert rows == []
    else:
        assert rows[0]["status"] == expected
