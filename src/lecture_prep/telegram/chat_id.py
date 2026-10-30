"""Find your Telegram chat id, once: send your bot any message, then run

    uv run python -m lecture_prep.telegram.chat_id

and put the number it prints in .env as TELEGRAM_CHAT_ID.
"""

from lecture_prep.config import get_settings
from lecture_prep.telegram.client import TelegramClient


def main() -> None:
    token = get_settings().telegram_bot_token
    if token is None:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env first (from @BotFather).")
    with TelegramClient.from_token(token.get_secret_value()) as telegram:
        chats = telegram.recent_chats()
    if not chats:
        raise SystemExit("No messages yet - send your bot any message in Telegram, then run this again.")
    for chat in chats:
        print(f"{chat.id}  {chat.name}")


if __name__ == "__main__":
    main()
