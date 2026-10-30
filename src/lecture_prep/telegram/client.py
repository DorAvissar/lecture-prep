"""A thin client for the few Telegram Bot API methods the app uses: https://core.telegram.org/bots/api"""

from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import httpx

TELEGRAM_URL = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096  # Telegram rejects longer messages


class TelegramError(RuntimeError):
    """Telegram answered with ok=false."""


@dataclass(frozen=True)
class Button:
    text: str
    url: str


@dataclass(frozen=True)
class Chat:
    id: int
    name: str  # first name for a private chat, title for a group


class TelegramClient:
    """Takes an httpx.Client so tests can plug in a fake transport."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    @classmethod
    def from_token(cls, token: str) -> Self:
        # The token is part of every method's URL: /bot<token>/sendMessage
        return cls(httpx.Client(base_url=f"{TELEGRAM_URL}/bot{token}", timeout=30))

    def send_message(self, chat_id: int, html: str, buttons: list[Button] | None = None) -> None:
        """Send a message formatted with Telegram's HTML subset, with optional link buttons below it."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": html,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if buttons:
            # One button per row; "url" buttons open the link in Telegram's browser.
            payload["reply_markup"] = {"inline_keyboard": [[{"text": b.text, "url": b.url}] for b in buttons]}
        self._call("sendMessage", payload)

    def recent_chats(self) -> list[Chat]:
        """Chats that recently messaged the bot - used once, to find your own chat id."""
        chats: dict[int, Chat] = {}
        for update in self._call("getUpdates", {}):
            chat = update.get("message", {}).get("chat")
            if chat:
                chats[chat["id"]] = Chat(id=chat["id"], name=chat.get("first_name") or chat.get("title", ""))
        return list(chats.values())

    def _call(self, method: str, payload: dict[str, Any]) -> Any:
        response = self._http.post(f"/{method}", json=payload)
        body = response.json()
        if not body.get("ok"):
            raise TelegramError(f"{method} failed: {body.get('description', response.status_code)}")
        return body["result"]

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()
