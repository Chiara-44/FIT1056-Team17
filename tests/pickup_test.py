# filename: pickup_test.py
# group: Team 17
# names: Harry
# created: 16/10/26
# last modified: 16/10/26
#
# Tests for pickup management (F-06: FR-26, FR-27, NFR-15).
# Unit tests for the Pickup class, ScheduleManager pickup methods, boundary values for the
# pickup time, and end-to-end tests through the real menus.

import io
import json
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

import main
from app.pickups import Pickup, parse_pickup_time
from app.schedule import ScheduleManager

NOW = datetime(2026, 10, 20, 9, 0)          # fixed "now" so tests don't depend on the clock
LATER = "2026-10-20 14:30"
FUTURE_EXPIRY = (date.today() + timedelta(days=60)).isoformat()


def write_data(tmp_path):
    data = {
        "volunteers": [{"id": 1, "name": "Sophie Patel", "username": "sophie",
                        "password": "vol123", "role": "volunteer"}],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [],
        "clients": [
            {"id": 1, "name": "Maya Donald", "phone": "0400 000 000",
             "allergies": {"peanuts": "severe"}, "preferences": ["vegan"], "household_size": 1},
        ],
        "storeroom": [
            {"id": 1, "name": "Chickpeas", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 20, "expiry": FUTURE_EXPIRY},
        ],
        "hampers": [
            {"id": 1, "client_id": 1, "packer_username": "angela", "packer_role": "staff",
             "items": {"1": 2}, "status": "completed", "allergy_acknowledged": True},
            {"id": 2, "client_id": 1, "packer_username": "angela", "packer_role": "staff",
             "items": {"1": 1}, "status": "draft", "allergy_acknowledged": True},
        ],
        "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 1,
        "next_client_id": 2, "next_item_id": 2, "next_hamper_id": 3,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def staff_manager(tmp_path):
    path = write_data(tmp_path)
    manager = ScheduleManager(str(path))
    manager.login("angela", "staff123", "staff")
    return manager, path


# ---------- Pickup class (unit) ----------

@pytest.mark.parametrize("text, expected", [
    ("2026-10-25 14:30", datetime(2026, 10, 25, 14, 30)),   # ISO format
    ("25/10/2026 14:30", datetime(2026, 10, 25, 14, 30)),   # Australian format
    ("  25/10/2026 09:05 ", datetime(2026, 10, 25, 9, 5)),  # extra spaces
])
def test_parse_pickup_time_valid_formats(text, expected):
    assert parse_pickup_time(text) == expected


@pytest.mark.parametrize("text", ["25/10/2026", "tomorrow", "2026-10-25 25:00", "31/02/2026 10:00", ""])
def test_parse_pickup_time_invalid(text):
    with pytest.raises(ValueError, match="Pickup time must look like"):
        parse_pickup_time(text)


def test_mark_collected_records_who_and_when():
    pickup = Pickup(1, 1, 1, LATER)
    pickup.mark_collected("sophie", datetime(2026, 10, 20, 14, 35))
    assert pickup.status == "collected"
    assert pickup.collected_by == "sophie"
    assert pickup.collected_at == datetime(2026, 10, 20, 14, 35)


def test_cannot_collect_twice_or_after_cancel():
    collected = Pickup(1, 1, 1, LATER)
    collected.mark_collected("sophie")
    with pytest.raises(ValueError, match="already been collected"):
        collected.mark_collected("sophie")

    cancelled = Pickup(2, 1, 1, LATER)
    cancelled.cancel()
    with pytest.raises(ValueError, match="cancelled"):
        cancelled.mark_collected("sophie")


def test_is_overdue_only_when_time_passed_and_not_collected():
    pickup = Pickup(1, 1, 1, LATER)
    assert not pickup.is_overdue(datetime(2026, 10, 20, 14, 30))   # exactly on time
    assert pickup.is_overdue(datetime(2026, 10, 20, 14, 31))       # one minute late
    pickup.mark_collected("sophie")
    assert not pickup.is_overdue(datetime(2026, 10, 21, 9, 0))     # collected, so not overdue


def test_invalid_status_rejected():
    with pytest.raises(ValueError):
        Pickup(1, 1, 1, LATER, status="lost")


# ---------- Scheduling (FR-26) ----------

def test_schedule_pickup_for_completed_hamper(tmp_path):
    manager, path = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)
    assert pickup.client_id == 1 and pickup.status == "scheduled"

    reloaded = ScheduleManager(str(path))
    assert reloaded.find_pickup(pickup.id).scheduled_at == datetime(2026, 10, 20, 14, 30)


def test_cannot_book_draft_hamper(tmp_path):
    manager, _ = staff_manager(tmp_path)
    with pytest.raises(ValueError, match="needs to be completed"):
        manager.schedule_pickup(2, LATER, now=NOW)


def test_cannot_book_missing_hamper(tmp_path):
    manager, _ = staff_manager(tmp_path)
    with pytest.raises(ValueError, match="No hamper"):
        manager.schedule_pickup(99, LATER, now=NOW)


def test_only_one_active_pickup_per_hamper(tmp_path):
    manager, _ = staff_manager(tmp_path)
    first = manager.schedule_pickup(1, LATER, now=NOW)
    with pytest.raises(ValueError, match="already has pickup"):
        manager.schedule_pickup(1, "2026-10-21 10:00", now=NOW)
    manager.cancel_pickup(first.id)                       # after cancelling, it can be rebooked
    assert manager.schedule_pickup(1, "2026-10-21 10:00", now=NOW).id == 2


@pytest.mark.parametrize("minutes_from_now, accepted", [(-1, False), (0, True), (1, True)])
def test_pickup_time_boundary(tmp_path, minutes_from_now, accepted):
    """BVA around 'now': one minute ago is rejected; now and one minute later are accepted."""
    manager, _ = staff_manager(tmp_path)
    when = NOW + timedelta(minutes=minutes_from_now)
    if accepted:
        assert manager.schedule_pickup(1, when, now=NOW).scheduled_at == when
    else:
        with pytest.raises(ValueError, match="past"):
            manager.schedule_pickup(1, when, now=NOW)


def test_volunteer_cannot_book_but_can_record_collection(tmp_path):
    manager, path = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)

    volunteer = ScheduleManager(str(path))
    volunteer.login("sophie", "vol123", "volunteer")
    with pytest.raises(PermissionError):
        volunteer.schedule_pickup(1, LATER, now=NOW)
    with pytest.raises(PermissionError):
        volunteer.cancel_pickup(pickup.id)
    assert volunteer.record_collection(pickup.id).collected_by == "sophie"


def test_not_logged_in_is_refused(tmp_path):
    manager = ScheduleManager(str(write_data(tmp_path)))
    with pytest.raises(PermissionError):
        manager.pickups_on()


# ---------- Rescheduling and cancelling ----------

def test_reschedule_pickup(tmp_path):
    manager, _ = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)
    manager.reschedule_pickup(pickup.id, "21/10/2026 11:00", now=NOW)
    assert pickup.scheduled_at == datetime(2026, 10, 21, 11, 0)


def test_cannot_reschedule_into_past_or_after_collection(tmp_path):
    manager, _ = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)
    with pytest.raises(ValueError, match="past"):
        manager.reschedule_pickup(pickup.id, "2026-10-19 10:00", now=NOW)
    manager.record_collection(pickup.id)
    with pytest.raises(ValueError, match="Only scheduled"):
        manager.reschedule_pickup(pickup.id, "2026-10-22 10:00", now=NOW)


def test_cancel_twice_rejected(tmp_path):
    manager, _ = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)
    manager.cancel_pickup(pickup.id)
    with pytest.raises(ValueError, match="Only scheduled"):
        manager.cancel_pickup(pickup.id)


# ---------- Recording collection (FR-27) ----------

def test_record_collection_is_saved(tmp_path):
    manager, path = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)
    manager.record_collection(pickup.id, when=datetime(2026, 10, 20, 14, 40))

    saved = json.loads(path.read_text())["pickups"][0]
    assert saved["status"] == "collected"
    assert saved["collected_by"] == "angela"
    assert saved["collected_at"] == "2026-10-20 14:40"


def test_record_collection_unknown_pickup(tmp_path):
    manager, _ = staff_manager(tmp_path)
    with pytest.raises(ValueError, match="No pickup"):
        manager.record_collection(5)


# ---------- Pickup list and privacy (NFR-15) ----------

def test_pickups_on_lists_day_in_time_order_without_cancelled(tmp_path):
    manager, _ = staff_manager(tmp_path)
    manager.hampers[1].status = "completed"               # make hamper 2 bookable too
    late = manager.schedule_pickup(1, "2026-10-20 16:00", now=NOW)
    early = manager.schedule_pickup(2, "2026-10-20 10:00", now=NOW)
    assert manager.pickups_on(date(2026, 10, 20)) == [early, late]
    manager.cancel_pickup(early.id)
    assert manager.pickups_on(date(2026, 10, 20)) == [late]
    assert manager.pickups_on(date(2026, 10, 21)) == []


def test_pickup_label_hides_private_details(tmp_path):
    manager, _ = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)
    label = manager.pickup_label(pickup, now=NOW)
    assert "Client #1 (Maya)" in label and "14:30" in label
    for private in ("Donald", "0400 000 000", "peanut", "vegan", "severe"):
        assert private not in label


def test_pickup_label_flags_missed_time(tmp_path):
    manager, _ = staff_manager(tmp_path)
    pickup = manager.schedule_pickup(1, LATER, now=NOW)
    assert "time passed" in manager.pickup_label(pickup, now=datetime(2026, 10, 20, 15, 0))


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


def test_e2e_staff_books_pickup_and_volunteer_records_collection(tmp_path):
    path = write_data(tmp_path)
    tomorrow = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "7", "s", "1", f"{tomorrow} 14:30",     # book hamper 1 for tomorrow
        "b", "", "l",
        "volunteer", "sophie", "vol123",
        "7", "d", tomorrow,                     # volunteer views tomorrow's list
        "c", "1",                               # records the collection
        "b", "", "q",
    ])
    assert "Booked pickup #1" in screen
    assert "Pickup #1 marked as collected" in screen
    assert "[s] Book a pickup" in screen.split("Welcome, Sophie Patel")[0]
    assert "[s] Book a pickup" not in screen.split("Welcome, Sophie Patel")[1]  # volunteer can't book
    assert "0400 000 000" not in screen and "peanut" not in screen.split("Pickups for")[-1]

    saved = json.loads(path.read_text())["pickups"][0]
    assert saved["status"] == "collected" and saved["collected_by"] == "sophie"


def test_e2e_bad_pickup_time_shows_message(tmp_path):
    path = write_data(tmp_path)
    screen = run_app(path, [
        "staff", "angela", "staff123",
        "7", "s", "1", "next tuesday",
        "b", "", "q",
    ])
    assert "Can't do that: Pickup time must look like" in screen
    assert json.loads(path.read_text()).get("pickups", []) == []
