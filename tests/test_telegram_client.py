"""Telegram client tests. httpx.MockTransport plays the role of the Bot API."""

import json
from collections.abc import Callable

import httpx
import pytest

from lecture_prep.telegram.client import Button, Chat, TelegramClient, TelegramError

Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler) -> TelegramClient:
    http = httpx.Client(base_url="https://api.telegram.org/botTEST", transport=httpx.MockTransport(handler))
    return TelegramClient(http)


def ok(result: object = True) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": result})


def test_send_message_posts_html_to_the_chat():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok({"message_id": 1})

    make_client(handler).send_message(42, "<b>שלום</b>")

    [request] = seen
    body = json.loads(request.content)
    assert request.url.path == "/botTEST/sendMessage"
    assert body["chat_id"] == 42
    assert body["text"] == "<b>שלום</b>"
    assert body["parse_mode"] == "HTML"
    assert "reply_markup" not in body


def test_buttons_go_one_per_row():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return ok()

    buttons = [
        Button("Recap", "https://example.com/1"),
        Button("Prep", "https://example.com/2", web_app=True),
    ]
    make_client(handler).send_message(42, "hi", buttons)

    assert seen[0]["reply_markup"] == {
        "inline_keyboard": [
            [{"text": "Recap", "url": "https://example.com/1"}],
            [{"text": "Prep", "web_app": {"url": "https://example.com/2"}}],
        ]
    }


def test_telegram_errors_are_raised():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})

    with pytest.raises(TelegramError, match="chat not found"):
        make_client(handler).send_message(1, "hi")


def test_recent_chats_lists_each_chat_once():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/botTEST/getUpdates"
        return ok(
            [
                {"update_id": 1, "message": {"chat": {"id": 7, "first_name": "Dor"}}},
                {"update_id": 2, "message": {"chat": {"id": 7, "first_name": "Dor"}}},
                {"update_id": 3, "edited_message": {}},
            ]
        )

    assert make_client(handler).recent_chats() == [Chat(id=7, name="Dor")]
