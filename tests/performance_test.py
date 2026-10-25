# filename: performance_test.py
# group: Team 17
# names: Harry
# created: 25/10/26
# last modified: 25/10/26
#
# Timed tests for NFR-04 and NFR-05 on a generated dataset of 10,000 inventory records.
# NFR-04: 95% of screen requests (stock list, a client's safe items, assigned tasks)
#         within 2 seconds with 10 users working at the same time.
# NFR-05: 95% of inventory searches within 2 seconds.

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import date, timedelta

import pytest

import main
from app.schedule import ScheduleManager
from app.storeroom import ALLERGENS, PREFERENCES

RECORDS = 10_000
USERS = 10
LIMIT_SECONDS = 2.0


def p95(times):
    times = sorted(times)
    return times[int(len(times) * 0.95) - 1]


@pytest.fixture
def big_store(tmp_path):
    """A data file with 10,000 stock records, 50 clients and 100 tasks."""
    allergens, diets = sorted(ALLERGENS), sorted(PREFERENCES)
    today = date.today()
    items = [{"id": i, "name": f"Item {i}",
              "allergens": [allergens[i % len(allergens)]] if i % 3 == 0 else [],
              "may_contain": [allergens[(i + 1) % len(allergens)]] if i % 7 == 0 else [],
              "preferences": [diets[i % len(diets)]], "quantity": i % 40,
              "expiry": (today + timedelta(days=i % 90 - 10)).isoformat()}
             for i in range(1, RECORDS + 1)]
    clients = [{"id": c, "name": f"Client {c}", "phone": "0400 000 000",
                "allergies": {allergens[c % len(allergens)]: "severe"},
                "preferences": [], "household": {"adults": 1}} for c in range(1, 51)]
    tasks = [{"id": t, "title": f"Task {t}", "assigned_to": "sophie"} for t in range(1, 101)]
    data = {"volunteers": [{"id": 1, "name": "Sophie Patel", "username": "sophie",
                            "password": "vol123", "role": "volunteer"}],
            "staff": [{"id": 1, "name": "Angela Bjork", "username": "angela",
                       "password": "staff123", "role": "staff"}],
            "admins": [], "clients": clients, "storeroom": items, "tasks": tasks,
            "next_volunteer_id": 2, "next_staff_id": 2, "next_admin_id": 1,
            "next_client_id": 51, "next_item_id": RECORDS + 1, "next_task_id": 101}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def timed(action):
    start = time.perf_counter()
    action()
    return time.perf_counter() - start


def test_dataset_loads_and_restarts_quickly(big_store):
    """Also supports NFR-11: the program is usable again well within 30 seconds."""
    seconds = timed(lambda: ScheduleManager(str(big_store)))
    assert seconds < LIMIT_SECONDS


def test_nfr05_inventory_search_95th_percentile(big_store):
    manager = ScheduleManager(str(big_store))
    manager.login("angela", "staff123", "staff")
    searches = [{"text": f"item {n}"} for n in range(50)] + \
               [{"exclude_allergens": ["peanuts", "tree nuts"], "suitable_for": ["vegan"],
                 "in_stock": True}] * 25 + [{"flag": "near expiry"}] * 25
    times = [timed(lambda f=f: manager.search_inventory(f)) for f in searches]
    assert len(times) == 100
    assert p95(times) < LIMIT_SECONDS


def test_nfr04_screens_with_ten_users_95th_percentile(big_store):
    staff = ScheduleManager(str(big_store))
    staff.login("angela", "staff123", "staff")
    volunteer = ScheduleManager(str(big_store))
    volunteer.login("sophie", "vol123", "volunteer")

    def stock_screen():
        main.show_stock(staff)       # printed output is captured below

    def safe_items_screen():
        staff.safe_items_for(staff.find_client(7))

    def task_screen():
        volunteer.tasks_for_current_user()

    requests = [stock_screen, safe_items_screen, task_screen] * 10   # 30 requests per user

    def one_user(_):
        return [timed(r) for r in requests]

    with redirect_stdout(io.StringIO()), ThreadPoolExecutor(max_workers=USERS) as pool:
        times = [t for user_times in pool.map(one_user, range(USERS)) for t in user_times]
    assert len(times) == USERS * len(requests)
    assert p95(times) < LIMIT_SECONDS


def test_saving_a_change_with_10000_records(big_store):
    """Every confirmed change rewrites the data file (NFR-11), so check that stays fast."""
    manager = ScheduleManager(str(big_store))
    manager.login("angela", "staff123", "staff")
    times = [timed(lambda n=n: manager.record_donation(f"New item {n}", [], [], [], 5, None))
             for n in range(20)]
    assert p95(times) < LIMIT_SECONDS
