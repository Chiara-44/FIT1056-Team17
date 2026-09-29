# filename: password_test.py
# group: Team 17
# names: Chiara
# created: 29/09/26
# last modified: 29/09/26


import json

from app.user import User, hash_password

from app.schedule import ScheduleManager





def test_hash_is_not_plain_password():

    h = hash_password("secret123")

    assert h != "secret123"

    assert h.startswith("$2")





def test_same_password_gives_different_hashes():

    assert hash_password("secret123") != hash_password("secret123")





def test_check_password_correct_and_wrong():

    user = User(1, "Test", "test", hash_password("secret123"), "staff")

    assert user.check_password("secret123")

    assert not user.check_password("wrong")

    assert not user.check_password("")





def test_check_password_with_missing_or_bad_hash():

    assert not User(1, "T", "t", "", "staff").check_password("anything")

    assert not User(1, "T", "t", "not-a-hash", "staff").check_password("anything")





def test_plain_passwords_in_file_are_hashed_on_load(tmp_path):

    path = tmp_path / "data.json"

    path.write_text(json.dumps({

        "staff": [{"id": 1, "name": "P", "username": "priya", "password": "staff123", "role": "staff"}]

    }))

    manager = ScheduleManager(str(path))



    saved = json.loads(path.read_text())

    assert "password" not in saved["staff"][0]

    assert saved["staff"][0]["password_hash"].startswith("$2")

    assert manager.login("priya", "staff123", "staff") is not None





def test_add_user_then_login(tmp_path):

    manager = ScheduleManager(str(tmp_path / "data.json"))

    manager.add_user("Sam", "sam", "vol123", "volunteer")



    reloaded = ScheduleManager(str(tmp_path / "data.json"))

    assert reloaded.login("sam", "vol123", "volunteer") is not None

    assert reloaded.login("sam", "wrong", "volunteer") is None
