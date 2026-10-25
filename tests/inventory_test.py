# filename: inventory_test.py
# group: Team 17
# names: Harry
# created: 24/10/26
# last modified: 24/10/26
#
# Tests for inventory search (FR-11), flags (FR-12), damaged/contaminated stock
# being blocked from hampers (FR-13) and stock adjustments (FR-10, NFR-12).

import json
from datetime import date, timedelta

import pytest

from app.schedule import ScheduleManager
from app.storeroom import FoodbankItem, NEAR_EXPIRY_DAYS

TODAY = date.today()


def day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


def write_data(tmp_path):
    data = {
        "volunteers": [{"id": 1, "name": "Sophie Patel", "username": "sophie",
                        "password": "vol123", "role": "volunteer"}],
        "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                   "password": "staff123", "role": "staff"}],
        "admins": [],
        "clients": [{"id": 1, "name": "Maya Donald", "phone": "0400 000 000",
                     "allergies": {"peanuts": "severe"}, "preferences": ["vegan"],
                     "household_size": 1}],
        "storeroom": [
            {"id": 1, "name": "Peanut butter", "allergens": ["peanuts"], "may_contain": [],
             "preferences": ["vegan"], "quantity": 10, "expiry": day(60)},
            {"id": 2, "name": "Chickpeas", "allergens": [], "may_contain": [],
             "preferences": ["vegan", "halal"], "quantity": 24, "expiry": day(60)},
            {"id": 3, "name": "Muesli", "allergens": ["gluten"], "may_contain": ["tree nuts"],
             "preferences": ["vegan"], "quantity": 5, "expiry": day(3)},
            {"id": 4, "name": "Brown rice", "allergens": [], "may_contain": [],
             "preferences": ["vegan"], "quantity": 0, "expiry": None},
            {"id": 5, "name": "Milk", "allergens": ["dairy"], "may_contain": [],
             "preferences": ["vegetarian"], "quantity": 4, "expiry": day(-2)},
        ],
        "stock_reports": [
            {"id": 1, "item_id": 2, "problem": "damaged", "quantity": 3,
             "reported_by": "sophie", "reported_on": day(0)},
        ],
        "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 1,
        "next_client_id": 2, "next_item_id": 6, "next_report_id": 2,
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def manager_as(tmp_path, username="angela", password="staff123", role="staff"):
    path = write_data(tmp_path)
    manager = ScheduleManager(str(path))
    manager.login(username, password, role)
    return manager, path


def names(items):
    return [i.name for i in items]


# ---------- FR-11 Search and filter ----------

def test_search_with_no_filters_returns_everything(tmp_path):
    manager, _ = manager_as(tmp_path)
    assert len(manager.search_inventory()) == 5


def test_search_by_name_ignores_case(tmp_path):
    manager, _ = manager_as(tmp_path)
    assert names(manager.search_inventory({"text": "RICE"})) == ["Brown rice"]


def test_exclude_allergens_also_removes_may_contain(tmp_path):
    manager, _ = manager_as(tmp_path)
    result = names(manager.search_inventory({"exclude_allergens": ["peanuts", "tree nuts"]}))
    assert "Peanut butter" not in result      # contains peanuts
    assert "Muesli" not in result             # may contain tree nuts
    assert "Chickpeas" in result


def test_filters_combine(tmp_path):
    manager, _ = manager_as(tmp_path)
    result = manager.search_inventory({"suitable_for": ["vegan"], "in_stock": True,
                                       "exclude_allergens": ["peanuts"]})
    assert names(result) == ["Chickpeas", "Muesli"]


@pytest.mark.parametrize("filters", [
    {"colour": "red"},                  # EP: unknown filter
    {"exclude_allergens": ["nutz"]},    # EP: unknown allergen
    {"flag": "mouldy"},                 # EP: unknown flag
])
def test_invalid_search_filters_rejected(tmp_path, filters):
    manager, _ = manager_as(tmp_path)
    with pytest.raises(ValueError):
        manager.search_inventory(filters)


def test_volunteer_can_search_but_logged_out_cannot(tmp_path):
    manager, _ = manager_as(tmp_path, "sophie", "vol123", "volunteer")
    assert manager.search_inventory({"text": "chick"})
    manager.logout()
    with pytest.raises(PermissionError):
        manager.search_inventory()


# ---------- FR-12 Flags ----------

@pytest.mark.parametrize("days_left, expected", [
    (-1, "expired"),                         # BVA: yesterday
    (0, "near expiry"),                      # BVA: today
    (NEAR_EXPIRY_DAYS, "near expiry"),       # BVA: last day of the window
    (NEAR_EXPIRY_DAYS + 1, None),            # BVA: just outside the window
])
def test_expiry_flag_boundaries(days_left, expected):
    item = FoodbankItem(1, "Bread", [], [], [], 3, day(days_left))
    expiry_flags = [f for f in item.flags() if f in ("expired", "near expiry")]
    assert expiry_flags == ([expected] if expected else [])


def test_flag_search_finds_each_problem(tmp_path):
    manager, _ = manager_as(tmp_path)
    manager.set_item_condition(1, "contaminated")
    assert names(manager.search_inventory({"flag": "expired"})) == ["Milk"]
    assert names(manager.search_inventory({"flag": "near expiry"})) == ["Muesli"]
    assert names(manager.search_inventory({"flag": "out of stock"})) == ["Brown rice"]
    assert names(manager.search_inventory({"flag": "contaminated"})) == ["Peanut butter"]
    assert names(manager.flagged_items()) == ["Peanut butter", "Muesli", "Brown rice", "Milk"]


def test_unknown_condition_rejected(tmp_path):
    manager, _ = manager_as(tmp_path)
    with pytest.raises(ValueError, match="Condition"):
        manager.set_item_condition(2, "mouldy")


def test_volunteer_cannot_change_condition(tmp_path):
    manager, _ = manager_as(tmp_path, "sophie", "vol123", "volunteer")
    with pytest.raises(PermissionError):
        manager.set_item_condition(2, "damaged")


# ---------- FR-13 Damaged stock can't be packed ----------

def test_damaged_item_blocked_from_hamper_and_safe_list(tmp_path):
    manager, _ = manager_as(tmp_path)
    manager.set_item_condition(2, "damaged")
    hamper = manager.create_hamper(1)
    manager.acknowledge_allergy_warning(hamper.id)
    with pytest.raises(ValueError, match="marked as damaged"):
        manager.add_hamper_item(hamper.id, 2, 1)
    assert "Chickpeas" not in names(manager.safe_items_for(manager.find_client(1)))


def test_condition_is_saved(tmp_path):
    manager, path = manager_as(tmp_path)
    manager.set_item_condition(2, "damaged")
    assert ScheduleManager(str(path)).find_item(2).condition == "damaged"


def test_donation_never_merges_into_damaged_batch(tmp_path):
    manager, _ = manager_as(tmp_path)
    manager.set_item_condition(2, "damaged")
    item = manager.record_donation("Chickpeas", [], [], ["vegan", "halal"], 6, day(60))
    assert item.id != 2 and item.condition == "good" and item.quantity == 6


# ---------- FR-10 / NFR-12 Stock adjustments ----------

def test_damaged_stock_removed_and_recorded(tmp_path):
    manager, path = manager_as(tmp_path)
    manager.adjust_stock(2, -3, "damaged", "Cans dented")
    saved = json.loads(path.read_text())
    assert next(i for i in saved["storeroom"] if i["id"] == 2)["quantity"] == 21
    log = saved["stock_adjustments"][0]
    assert log["change"] == -3 and log["reason"] == "damaged" and log["recorded_by"] == "angela"


@pytest.mark.parametrize("change, accepted", [
    (-24, True),    # BVA: removes all stock, leaves 0
    (-25, False),   # BVA: would go below 0
])
def test_stock_never_goes_below_zero(tmp_path, change, accepted):
    manager, _ = manager_as(tmp_path)
    if accepted:
        assert manager.adjust_stock(2, change, "discarded").quantity == 0
    else:
        with pytest.raises(ValueError, match="only 24"):
            manager.adjust_stock(2, change, "discarded")
        assert manager.find_item(2).quantity == 24


@pytest.mark.parametrize("change, reason", [
    (0, "damaged"),            # EP: no change
    (5, "damaged"),            # EP: adding stock with a removal reason
    (-1, "stolen"),            # EP: unknown reason
    ("-2", "damaged"),         # EP: not a whole number
])
def test_invalid_adjustments_rejected(tmp_path, change, reason):
    manager, _ = manager_as(tmp_path)
    with pytest.raises(ValueError):
        manager.adjust_stock(2, change, reason)
    assert manager.find_item(2).quantity == 24


def test_count_correction_can_add_stock(tmp_path):
    manager, _ = manager_as(tmp_path)
    assert manager.adjust_stock(4, 12, "count correction", "Found a box").quantity == 12


def test_adjustment_resolves_volunteer_report(tmp_path):
    manager, _ = manager_as(tmp_path)
    manager.adjust_stock(2, -3, "damaged", report_id=1)
    assert manager.open_stock_reports() == []
    with pytest.raises(ValueError, match="already been dealt with"):
        manager.adjust_stock(2, -1, "damaged", report_id=1)


def test_report_for_other_item_rejected(tmp_path):
    manager, _ = manager_as(tmp_path)
    with pytest.raises(ValueError, match="different item"):
        manager.adjust_stock(3, -1, "damaged", report_id=1)
    assert len(manager.open_stock_reports()) == 1


def test_volunteer_cannot_adjust_stock(tmp_path):
    manager, _ = manager_as(tmp_path, "sophie", "vol123", "volunteer")
    with pytest.raises(PermissionError):
        manager.adjust_stock(2, -1, "damaged")
