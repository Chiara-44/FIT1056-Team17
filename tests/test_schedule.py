import pytest
from app.schedule import ScheduleManager


@pytest.fixture
def manager(tmp_path):
    # str() matters: _save_data does data_path + ".tmp", which fails on a Path object
    return ScheduleManager(str(tmp_path / "test.json"))


@pytest.fixture
def admin(manager):
    manager.add_user("Ada Admin", "ada", "secret123", "admin")
    manager.login("ada", "secret123", "admin")
    return manager


def test_fresh_install_needs_setup(manager):
    assert manager.needs_setup()


def test_first_account_must_be_admin(manager):
    with pytest.raises(ValueError):
        manager.add_user("Sam Staff", "sam", "secret123", "staff")


def test_first_admin_created_without_login(manager):
    manager.add_user("Ada Admin", "ada", "secret123", "admin")
    assert not manager.needs_setup()


def test_second_account_needs_admin_login(manager):
    manager.add_user("Ada Admin", "ada", "secret123", "admin")
    with pytest.raises(PermissionError):
        manager.add_user("Sam Staff", "sam", "secret123", "staff")


def test_donations_with_different_diet_tags_stay_separate(admin):
    vegan = admin.record_donation("Pasta sauce", [], [], ["vegan"], 5)
    plain = admin.record_donation("Pasta sauce", [], [], [], 3)
    assert vegan.id != plain.id
    assert vegan.quantity == 5


def test_matching_donation_merges(admin):
    first = admin.record_donation("Rice", [], [], ["vegan"], 5)
    second = admin.record_donation("Rice", [], [], ["vegan"], 2)
    assert first.id == second.id
    assert second.quantity == 7