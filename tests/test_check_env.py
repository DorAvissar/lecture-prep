from lecture_prep.check_env import REQUIRED, missing


def test_nothing_missing_when_all_are_set():
    assert missing(dict.fromkeys(REQUIRED, "x")) == []


def test_blank_and_absent_settings_are_missing():
    environ = dict.fromkeys(REQUIRED, "x") | {"DATABASE_URL": "  "}
    del environ["TICK_SECRET"]

    assert missing(environ) == ["DATABASE_URL", "TICK_SECRET"]


def test_database_description_never_shows_the_password():
    from lecture_prep.check_env import describe_database

    description = describe_database("postgresql://owner:s3cret@ep-x.neon.tech/neondb")

    assert description == "host ep-x.neon.tech, database neondb"
    assert "s3cret" not in description


def test_database_without_a_host_is_called_out():
    from lecture_prep.check_env import describe_database

    assert "localhost" in describe_database("postgresql:///neondb")
