"""The Mini App's routes: the page itself, a lecture's summaries, and the lecture chat.

Every API request must carry Telegram's signed init data (header X-Telegram-Init-Data) from the owner or
a classmate who joined (see members.py); members have a daily limit on chat questions. In development,
a request from this computer without it is let through, so the page can be opened in a normal browser.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.config import Settings, get_settings
from lecture_prep.db.models import Course, Lecture, Summary, SummaryKind
from lecture_prep.db.session import get_session
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.lecture_chat import LectureChat
from lecture_prep.lecture_locator import LectureMaterial, course_lectures
from lecture_prep.llm import ChatMessage, LectureFile, ModelError, make_model
from lecture_prep.members import is_member, use_question
from lecture_prep.web.render import render_markdown
from lecture_prep.web.telegram_auth import InvalidInitData, verify_init_data

STATIC = Path(__file__).parent / "static"
PAGE = STATIC / "app.html"

router = APIRouter()
SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]


LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def require_user(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    init_data: Annotated[str | None, Header(alias="X-Telegram-Init-Data")] = None,
) -> int:
    """The Telegram user id of the owner or a member making the request; anyone else is refused."""
    if not init_data:
        # The browser shortcut is for your own computer only: in the cloud, a wrong ENVIRONMENT must never
        # open the summaries and the paid chat to anyone who finds the address.
        is_local = request.client is not None and request.client.host in LOCAL_CLIENTS
        if settings.environment == "development" and is_local:
            return settings.telegram_chat_id or 0
        raise HTTPException(401, "open this page from Telegram")
    if settings.telegram_bot_token is None or settings.telegram_chat_id is None:
        raise HTTPException(503, "Telegram is not configured")
    try:
        user_id = verify_init_data(
            init_data, settings.telegram_bot_token.get_secret_value(), datetime.now(UTC)
        )
    except InvalidInitData as error:
        raise HTTPException(401, "invalid Telegram data") from error
    # In a private chat, the chat id is the user's id.
    if user_id != settings.telegram_chat_id and not is_member(session, user_id):
        raise HTTPException(403, "this bot is private")
    return user_id


def get_drive(settings: SettingsDep) -> Iterator[DriveClient]:
    with DriveClient.from_settings(settings) as drive:
        yield drive


def get_chat(settings: SettingsDep) -> LectureChat:
    return LectureChat(make_model(settings))


UserId = Annotated[int, Depends(require_user)]


class LectureView(BaseModel):
    course: str
    number: int
    prep: str | None  # HTML; None until the prep brief is written
    recap: str | None  # HTML recap of the previous lecture; None for the first lecture


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    course_id: int
    number: int
    messages: list[ChatTurn] = Field(min_length=1, max_length=50)


class ChatAnswer(BaseModel):
    answer: str  # HTML


@router.get("/app", include_in_schema=False)
def page() -> FileResponse:
    return FileResponse(PAGE, media_type="text/html")


# Public pages that Google's OAuth consent screen links to (app home page and privacy policy).
@router.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC / "home.html", media_type="text/html")


@router.get("/privacy", include_in_schema=False)
def privacy() -> FileResponse:
    return FileResponse(STATIC / "privacy.html", media_type="text/html")


@router.get("/api/lectures/{course_id}/{number}")
def lecture_view(course_id: int, number: int, session: SessionDep, user_id: UserId) -> LectureView:
    course = _course(session, course_id)
    prep = _summary(session, course_id, number, SummaryKind.PREP)
    recap = _summary(session, course_id, number - 1, SummaryKind.RECAP)
    return LectureView(
        course=course.name,
        number=number,
        prep=render_markdown(prep.content) if prep else None,
        recap=render_markdown(recap.content) if recap else None,
    )


@router.post("/api/chat")
def chat(
    request: ChatRequest,
    session: SessionDep,
    settings: SettingsDep,
    user_id: UserId,
    drive: Annotated[DriveClient, Depends(get_drive)],
    lecture_chat: Annotated[LectureChat, Depends(get_chat)],
) -> ChatAnswer:
    if user_id != settings.telegram_chat_id:  # members have a daily limit; the owner does not
        today = datetime.now(ZoneInfo(settings.timezone)).date()
        if not use_question(session, user_id, today, settings.member_daily_questions):
            raise HTTPException(
                429, f"הגעת למגבלה של {settings.member_daily_questions} שאלות ביום. נתראה מחר!"
            )
    course = _course(session, request.course_id)
    lectures = course_lectures(drive, course)
    current = lectures.get(request.number)
    if current is None:
        raise HTTPException(404, "no files for this lecture yet")
    history = [ChatMessage(turn.role, turn.content) for turn in request.messages]
    try:
        text = lecture_chat.answer(
            course.name,
            request.number,
            _download(drive, current),
            _download(drive, lectures.get(request.number - 1)),
            history,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except ModelError as error:
        raise HTTPException(502, str(error)) from error
    return ChatAnswer(answer=render_markdown(text))


def _course(session: Session, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "no such course")
    return course


def _summary(session: Session, course_id: int, number: int, kind: SummaryKind) -> Summary | None:
    return session.scalar(
        select(Summary)
        .join(Lecture)
        .where(Lecture.course_id == course_id, Lecture.number == number, Summary.kind == kind)
    )


def _download(drive: DriveClient, material: LectureMaterial | None) -> list[LectureFile]:
    return [LectureFile(item.name, drive.download(item)) for item in material.files] if material else []
