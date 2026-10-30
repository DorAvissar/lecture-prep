"""The Mini App's routes: the page itself, a lecture's summaries, and the lecture chat.

Every API request must carry Telegram's signed init data (header X-Telegram-Init-Data) from the one
Telegram user the app belongs to. In development, a request without it is let through, so the page can
be opened in a normal browser.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.config import Settings, get_settings
from lecture_prep.db.models import Course, Lecture, Summary, SummaryKind
from lecture_prep.db.session import get_session
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.lecture_chat import ChatMessage, LectureChat
from lecture_prep.lecture_locator import LectureMaterial, course_lectures
from lecture_prep.summarizer import LectureFile, SummaryError, claude_client
from lecture_prep.web.render import render_markdown
from lecture_prep.web.telegram_auth import InvalidInitData, verify_init_data

PAGE = Path(__file__).parent / "static" / "app.html"

router = APIRouter()
SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]


def require_owner(
    settings: SettingsDep, init_data: Annotated[str | None, Header(alias="X-Telegram-Init-Data")] = None
) -> None:
    if not init_data:
        if settings.environment == "development":
            return
        raise HTTPException(401, "open this page from Telegram")
    if settings.telegram_bot_token is None or settings.telegram_chat_id is None:
        raise HTTPException(503, "Telegram is not configured")
    try:
        user_id = verify_init_data(
            init_data, settings.telegram_bot_token.get_secret_value(), datetime.now(UTC)
        )
    except InvalidInitData as error:
        raise HTTPException(401, "invalid Telegram data") from error
    if user_id != settings.telegram_chat_id:  # in a private chat, the chat id is the user's id
        raise HTTPException(403, "not your app")


def get_drive(settings: SettingsDep) -> Iterator[DriveClient]:
    with DriveClient.from_settings(settings) as drive:
        yield drive


def get_chat(settings: SettingsDep) -> LectureChat:
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    return LectureChat(claude_client(api_key), settings.anthropic_model)


Owner = Depends(require_owner)


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


@router.get("/api/lectures/{course_id}/{number}", dependencies=[Owner])
def lecture_view(course_id: int, number: int, session: SessionDep) -> LectureView:
    course = _course(session, course_id)
    prep = _summary(session, course_id, number, SummaryKind.PREP)
    recap = _summary(session, course_id, number - 1, SummaryKind.RECAP)
    return LectureView(
        course=course.name,
        number=number,
        prep=render_markdown(prep.content) if prep else None,
        recap=render_markdown(recap.content) if recap else None,
    )


@router.post("/api/chat", dependencies=[Owner])
def chat(
    request: ChatRequest,
    session: SessionDep,
    drive: Annotated[DriveClient, Depends(get_drive)],
    lecture_chat: Annotated[LectureChat, Depends(get_chat)],
) -> ChatAnswer:
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
    except SummaryError as error:
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
