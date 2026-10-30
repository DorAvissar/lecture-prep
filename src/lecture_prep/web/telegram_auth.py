"""Check that a Mini App request really comes from Telegram, and from whom.

Telegram hands the page a signed "init data" string. The page sends it with every API request, and we
re-compute the signature with the bot token, as described in
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
Only someone who has the token can produce a valid one.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

MAX_AGE = timedelta(days=1)  # init data older than this is rejected


class InvalidInitData(ValueError):
    """The init data is missing, malformed, wrongly signed or too old."""


def signature(fields: dict[str, str], bot_token: str) -> str:
    """Telegram's signature: HMAC of the sorted "key=value" lines, keyed by HMAC("WebAppData", token)."""
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def verify_init_data(init_data: str, bot_token: str, now: datetime, max_age: timedelta = MAX_AGE) -> int:
    """Return the Telegram user id from valid init data, or raise InvalidInitData."""
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received = fields.pop("hash", "")
    if not hmac.compare_digest(signature(fields, bot_token), received):
        raise InvalidInitData("bad signature")
    try:
        signed_at = datetime.fromtimestamp(int(fields["auth_date"]), UTC)
        user_id = int(json.loads(fields["user"])["id"])
    except (KeyError, ValueError, TypeError) as error:
        raise InvalidInitData("missing auth_date or user") from error
    if now - signed_at > max_age:
        raise InvalidInitData("expired")
    return user_id
