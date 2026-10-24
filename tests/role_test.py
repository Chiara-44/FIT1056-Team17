# filename: role_test.py
# group: Team 17
# names: Harry
# created: 24/10/26
# last modified: 24/10/26
#
# Tests for changing a user's role (FR-02, FR-03).

import pytest

from app.schedule import ScheduleManager


@pytest.fixture
def admin(tmp_path):
    """One admin (logged in), one staff member and one volunteer with a task."""
    m = ScheduleManager(str(tmp_path / "data.json"))
    m.add_user("Ada Admin", "ada", "admin123", "admin")
    m.login("ada", "admin123", "admin")
    m.add_user("Angela Bjork", "angela", "staff123", "staff")
    m.add_user("Sophie Patel", "sophie", "vol123", "volunteer")
    m.create_task("Check tinned food", assign_to="sophie")
    return m


def test_volunteer_promoted_to_staff_can_log_in_with_same_password(admin):
    user = admin.assign_role(1, "volunteer", "staff")
    assert user.role == "staff" and user.id == 2      # next staff number
    assert admin.volunteers == []
    admin.logout()
    assert admin.login("sophie", "vol123", "volunteer") is None
    assert admin.login("sophie", "vol123", "staff") is not None
    assert admin.can("manage_clients")                 # now has staff permissions


def test_role_change_is_saved(admin, tmp_path):
    admin.assign_role(1, "staff", "admin")
    reloaded = ScheduleManager(str(tmp_path / "data.json"))
    assert [u.username for u in reloaded.admins] == ["ada", "angela"]
    assert reloaded.staff == []


def test_unfinished_tasks_unassigned_when_volunteer_moves(admin):
    admin.assign_role(1, "volunteer", "staff")
    assert admin.tasks[0].assigned_to == ""


@pytest.mark.parametrize("user_id, current, new, message", [
    (1, "volunteer", "volunteer", "already"),     # EP: same role
    (9, "volunteer", "staff", "No volunteer"),    # EP: user doesn't exist
    (1, "volunteer", "manager", "Role must be"),  # EP: invalid role
    (1, "admin", "staff", "own role"),            # admin can't demote themselves
])
def test_invalid_role_changes_rejected(admin, user_id, current, new, message):
    with pytest.raises(ValueError, match=message):
        admin.assign_role(user_id, current, new)


def test_last_admin_cannot_be_removed(admin):
    admin.assign_role(1, "staff", "admin")          # Angela becomes admin #2
    admin.logout()
    admin.login("angela", "staff123", "admin")
    admin.assign_role(1, "admin", "staff")          # Angela demotes Ada: allowed, 2 admins
    assert [u.username for u in admin.admins] == ["angela"]
    with pytest.raises(ValueError):
        admin.assign_role(2, "admin", "staff")      # Angela is now the only admin (and herself)


def test_username_clash_in_new_role_rejected(admin):
    admin.add_user("Other Sophie", "sophie", "other123", "staff")
    with pytest.raises(ValueError, match="already exists"):
        admin.assign_role(1, "volunteer", "staff")


def test_staff_cannot_change_roles(admin):
    admin.logout()
    admin.login("angela", "staff123", "staff")
    with pytest.raises(PermissionError):
        admin.assign_role(1, "volunteer", "staff")
    with pytest.raises(PermissionError):
        admin.all_users()


def test_all_users_lists_every_account(admin):
    assert {(u.username, u.role) for u in admin.all_users()} == {
        ("ada", "admin"), ("angela", "staff"), ("sophie", "volunteer")}
