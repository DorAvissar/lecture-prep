from lecture_prep.check_env import REQUIRED, missing


def test_nothing_missing_when_all_are_set():
    assert missing(dict.fromkeys(REQUIRED, "x")) == []


def test_blank_and_absent_settings_are_missing():
    environ = dict.fromkeys(REQUIRED, "x") | {"DATABASE_URL": "  "}
    del environ["TICK_SECRET"]

    assert missing(environ) == ["DATABASE_URL", "TICK_SECRET"]
