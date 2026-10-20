# filename: tasks.py
# group: Team 17
# names: Chiara
# created: 20/10/26
# last modified: 20/10/26
# 
# Tests for volunteer tasks (FR-20 to FR-24, AC-12, AC-13) and stock reports (FR-25).

from datetime import date, timedelta

import pytest

from app.schedule import ScheduleManager
from app.tasks import Task, StockReport, TODO, IN_PROGRESS, DONE

FUTURE = (date.today() + timedelta(days=30)).isoformat()


@pytest.fixture
def manager(tmp_path):
    """Admin, one staff member, two volunteers and one stock item. Nobody logged in."""
    m = ScheduleManager(str(tmp_path / "data.json"))
    m.add_user("Ada Admin", "ada", "admin123", "admin")
    m.login("ada", "admin123", "admin")
    m.add_user("Angela Bjork", "angela", "staff123", "staff")
    m.add_user("Sophie Patel", "sophie", "vol123", "volunteer")
    m.add_user("Tom Nguyen", "tom", "vol456", "volunteer")
    m.record_donation("Rice", [], [], ["vegan"], 10, FUTURE)
    m.logout()
    return m


def as_staff(m):
    m.login("angela", "staff123", "staff")
    return m


def as_sophie(m):
    m.login("sophie", "vol123", "volunteer")
    return m


# ---------- Task model ----------

def test_new_task_starts_as_to_do():
    task = Task(1, "Check expiry dates")
    assert task.status == TODO and task.assigned_to == ""


@pytest.mark.parametrize("title", ["", "   ", "x" * 101])
def test_task_title_must_be_1_to_100_characters(title):
    with pytest.raises(ValueError):
        Task(1, title)


def test_task_title_of_exactly_100_characters_is_allowed():
    assert len(Task(1, "x" * 100).title) == 100


def test_unknown_task_status_is_rejected():
    with pytest.raises(ValueError):
        Task(1, "Sort tins", status="finished")


def test_done_task_cannot_be_reassigned():
    task = Task(1, "Sort tins", assigned_to="sophie", status=DONE)
    with pytest.raises(ValueError):
        task.assign("tom")


def test_task_round_trips_through_to_dict():
    task = Task(3, "Pack hampers", "Saturday morning", "sophie", IN_PROGRESS, "Halfway", "angela")
    assert Task(**task.to_dict()).to_dict() == task.to_dict()


# ---------- Creating and assigning (FR-20 to FR-22) ----------

def test_staff_create_and_assign_task_volunteer_sees_it(manager):
    """AC-12: a task created and assigned by staff appears in the volunteer's list."""
    as_staff(manager)
    task = manager.create_task("Check expiry dates", "Tinned food shelf", assign_to="sophie")
    manager.logout()
    as_sophie(manager)
    assert [t.id for t in manager.tasks_for_current_user()] == [task.id]


def test_task_can_be_created_unassigned_then_assigned(manager):
    as_staff(manager)
    task = manager.create_task("Sort donations")
    assert task.assigned_to == ""
    manager.assign_task(task.id, "tom")
    assert manager.find_task(task.id).assigned_to == "tom"


def test_task_can_be_reassigned(manager):
    as_staff(manager)
    task = manager.create_task("Sort donations", assign_to="sophie")
    manager.assign_task(task.id, "tom")
    manager.logout()
    as_sophie(manager)
    assert manager.tasks_for_current_user() == []


def test_cannot_assign_to_unknown_volunteer(manager):
    as_staff(manager)
    with pytest.raises(ValueError):
        manager.create_task("Sort donations", assign_to="nobody")


def test_cannot_assign_task_to_staff_member(manager):
    as_staff(manager)
    with pytest.raises(ValueError):
        manager.create_task("Sort donations", assign_to="angela")


def test_volunteer_cannot_create_tasks(manager):
    as_sophie(manager)
    with pytest.raises(PermissionError):
        manager.create_task("Give myself a day off")


def test_logged_out_user_cannot_see_tasks(manager):
    with pytest.raises(PermissionError):
        manager.tasks_for_current_user()


# ---------- Updating progress (FR-23, FR-24) ----------

def test_volunteer_updates_own_task_and_it_is_saved(manager, tmp_path):
    """AC-13: a volunteer's progress update is saved."""
    as_staff(manager)
    task = manager.create_task("Check expiry dates", assign_to="sophie")
    manager.logout()
    as_sophie(manager)
    manager.update_task_progress(task.id, IN_PROGRESS, "Done the top shelf")

    reloaded = ScheduleManager(str(tmp_path / "data.json"))
    saved = reloaded.find_task(task.id)
    assert saved.status == IN_PROGRESS and saved.progress_note == "Done the top shelf"


def test_volunteer_cannot_update_someone_elses_task(manager):
    as_staff(manager)
    task = manager.create_task("Sort donations", assign_to="tom")
    manager.logout()
    as_sophie(manager)
    with pytest.raises(PermissionError):
        manager.update_task_progress(task.id, DONE)


def test_unfinished_tasks_are_listed_first(manager):
    as_staff(manager)
    first = manager.create_task("Task A", assign_to="sophie")
    second = manager.create_task("Task B", assign_to="sophie")
    manager.logout()
    as_sophie(manager)
    manager.update_task_progress(first.id, DONE)
    assert [t.id for t in manager.tasks_for_current_user()] == [second.id, first.id]


def test_staff_member_with_same_username_does_not_see_volunteer_tasks(manager):
    manager.login("ada", "admin123", "admin")
    manager.add_user("Sophie Staff", "sophie", "staff456", "staff")
    manager.logout()
    as_staff(manager)
    manager.create_task("Volunteer job", assign_to="sophie")
    manager.logout()
    manager.login("sophie", "staff456", "staff")
    assert manager.tasks_for_current_user() == []


# ---------- Reporting stock problems (FR-25) ----------

def test_volunteer_reports_damaged_stock_without_changing_quantity(manager):
    as_sophie(manager)
    report = manager.report_stock_problem(1, "damaged", 2, "Two bags split open")
    assert report.reported_by == "sophie"
    assert manager.find_item(1).quantity == 10
    manager.logout()
    as_staff(manager)
    assert [r.id for r in manager.open_stock_reports()] == [report.id]


@pytest.mark.parametrize("quantity", [0, 11])
def test_stock_report_quantity_must_be_1_to_stock_level(manager, quantity):
    as_sophie(manager)
    with pytest.raises(ValueError):
        manager.report_stock_problem(1, "missing", quantity)


def test_stock_report_quantity_equal_to_stock_level_is_allowed(manager):
    as_sophie(manager)
    assert manager.report_stock_problem(1, "missing", 10).quantity == 10


def test_unknown_stock_problem_is_rejected():
    with pytest.raises(ValueError):
        StockReport(1, 1, "smelly", 1)


def test_volunteer_cannot_see_open_stock_reports(manager):
    as_sophie(manager)
    with pytest.raises(PermissionError):
        manager.open_stock_reports()