# filename: security_test.py
# group: Team 17
# names: Harry
# created: 24/10/26
# last modified: 24/10/26
#
# Tests for the inactivity timeout (NFR-02, NFR-15), daily backups (NFR-11)
# and the audit log (accountability, Section 8.4).

import io
import json
import os
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import main
from app.schedule import ScheduleManager, SESSION_TIMEOUT_MINUTES, BACKUPS_TO_KEEP


class Clock:
    """A fake clock so tests can move time forward."""

    def __init__(self, start=datetime(2026, 10, 24, 9, 0)):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def setup(tmp_path):
    clock = Clock()
    m = ScheduleManager(str(tmp_path / "data.json"))
    m._now = clock
    m.add_user("Ada Admin", "ada", "admin123", "admin")
    m.login("ada", "admin123", "admin")
    m.add_user("Angela Bjork", "angela", "staff123", "staff")
    m.logout()
    return m, clock, tmp_path


# ---------- Inactivity timeout ----------

@pytest.mark.parametrize("minutes, logged_out", [
    (SESSION_TIMEOUT_MINUTES - 1, False),   # BVA: just inside the limit
    (SESSION_TIMEOUT_MINUTES, False),       # BVA: exactly on the limit
    (SESSION_TIMEOUT_MINUTES + 1, True),    # BVA: just over the limit
])
def test_timeout_boundary(setup, minutes, logged_out):
    m, clock, _ = setup
    m.login("angela", "staff123", "staff")
    clock.advance(minutes=minutes)
    if logged_out:
        with pytest.raises(PermissionError, match="logged out"):
            m.add_client("Maya Donald", "0400", {}, [])
        assert m.current_user is None
    else:
        m.add_client("Maya Donald", "0400", {}, [])
        assert m.current_user is not None


def test_each_action_resets_the_timer(setup):
    m, clock, _ = setup
    m.login("angela", "staff123", "staff")
    for _ in range(3):
        clock.advance(minutes=8)
        m.add_client("Client", "0400", {}, [])   # 24 minutes in total, never 10 idle
    assert m.current_user is not None


def test_cli_returns_to_login_after_timeout(setup):
    m, clock, tmp_path = setup
    answers = iter(["staff", "angela", "staff123", "4", "q"])

    def fake_input(prompt=""):
        value = next(answers, None)
        if value is None:
            raise EOFError
        if value == "4":
            clock.advance(minutes=SESSION_TIMEOUT_MINUTES + 1)   # user walked away
        return value

    out = io.StringIO()
    with patch("main.ScheduleManager", lambda path: m), patch("builtins.input", fake_input), \
            patch("main.getpass", fake_input), redirect_stdout(out):
        main.main(str(tmp_path / "data.json"))
    screen = out.getvalue()
    assert "logged out after 10 minutes" in screen
    assert screen.count("=== FoodShare Tracker: Log in ===") == 2   # back at the login screen


# ---------- Daily backups ----------

def test_backup_made_once_per_day(setup):
    m, clock, tmp_path = setup
    m.login("angela", "staff123", "staff")
    m.add_client("A", "0400", {}, [])
    m.add_client("B", "0400", {}, [])
    backups = os.listdir(tmp_path / "backups")
    assert backups == ["data-2026-10-24.json"]
    clock.advance(days=1)
    m.last_activity = clock.now   # still working, so no timeout
    m.add_client("C", "0400", {}, [])
    assert sorted(os.listdir(tmp_path / "backups")) == ["data-2026-10-24.json", "data-2026-10-25.json"]


def test_backup_holds_previous_version(setup):
    m, clock, tmp_path = setup
    m.login("angela", "staff123", "staff")
    clock.advance(days=1)
    m.last_activity = clock.now
    m.add_client("New client", "0400", {}, [])
    backup = json.loads((tmp_path / "backups" / "data-2026-10-25.json").read_text())
    assert backup["clients"] == []          # taken before today's first change


def test_only_newest_backups_kept(setup):
    m, clock, tmp_path = setup
    m.login("angela", "staff123", "staff")
    for _ in range(BACKUPS_TO_KEEP + 3):
        clock.advance(days=1)
        m.last_activity = clock.now
        m.add_client("Client", "0400", {}, [])
    assert len(os.listdir(tmp_path / "backups")) == BACKUPS_TO_KEEP


# ---------- Audit log ----------

def test_actions_are_audited_with_user_and_time(setup):
    m, clock, tmp_path = setup
    m.login("angela", "staff123", "staff")
    client = m.add_client("Maya Donald", "0400", {}, [])
    m.add_client_note(client.id, "Prefers afternoon pickups")
    item = m.record_donation("Rice", [], [], ["vegan"], 5, None, "Jessi")
    m.adjust_stock(item.id, -1, "damaged")
    saved = json.loads((tmp_path / "data.json").read_text())["audit_log"]
    actions = [e["action"] for e in saved]
    assert actions[-4:] == ["register client", "add private note", "record donation", "adjust stock"]
    assert saved[-1]["user"] == "angela" and saved[-1]["when"] == "2026-10-24T09:00:00"
    assert "Prefers afternoon" not in json.dumps(saved)   # note text itself isn't copied


def test_only_admins_can_read_audit_log(setup):
    m, clock, _ = setup
    m.login("angela", "staff123", "staff")
    with pytest.raises(PermissionError):
        m.audit_entries()
    m.logout()
    m.login("ada", "admin123", "admin")
    entries = m.audit_entries()
    assert entries[0]["action"] == "add user"           # newest first
