import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lecture_prep.db.models import Course, Lecture, Summary, SummaryKind


def make_course(**overrides) -> Course:
    fields = {"name": "Linear Algebra", "aliases": ["לינארית"], "drive_folder": "Lectures/Linear Algebra"}
    return Course(**(fields | overrides))


def test_course_lectures_are_ordered_by_number(db_session: Session):
    course = make_course()
    course.lectures = [
        Lecture(number=2, source_path="/Uni/Linear Algebra/lecture2.pdf"),
        Lecture(number=1, source_path="/Uni/Linear Algebra/lecture1.pdf"),
    ]
    db_session.add(course)
    db_session.commit()
    db_session.expire_all()  # force a fresh load from the database

    loaded = db_session.scalars(select(Course)).one()

    assert [lecture.number for lecture in loaded.lectures] == [1, 2]
    assert loaded.aliases == ["לינארית"]


def test_lecture_number_is_unique_within_a_course(db_session: Session):
    course = make_course()
    course.lectures = [
        Lecture(number=1, source_path="/a.pdf"),
        Lecture(number=1, source_path="/b.pdf"),
    ]
    db_session.add(course)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_deleting_a_course_deletes_its_lectures_and_summaries(db_session: Session):
    lecture = Lecture(number=1, source_path="/a.pdf")
    lecture.summaries = [Summary(kind=SummaryKind.PREP, content="...", model="test-model")]
    course = make_course(lectures=[lecture])
    db_session.add(course)
    db_session.commit()

    db_session.delete(course)
    db_session.commit()

    assert db_session.scalars(select(Lecture)).all() == []
    assert db_session.scalars(select(Summary)).all() == []


def test_summary_kind_is_stored_as_lowercase_value(db_session: Session):
    lecture = Lecture(number=1, source_path="/a.pdf")
    lecture.summaries = [Summary(kind=SummaryKind.RECAP, content="...", model="test-model")]
    db_session.add(make_course(lectures=[lecture]))
    db_session.commit()

    stored = db_session.execute(text("SELECT kind::text FROM summaries")).scalar_one()

    assert stored == "recap"
