"""POST /internal/tick: lets an outside scheduler run a tick, and keeps a free server awake.

On a free hosting plan the server sleeps after a few idle minutes and there is no built-in scheduler, so a
free cron service calls this address every 10 minutes with the X-Tick-Secret header. The tick runs in the
background after the response, and never twice at the same time.
"""

import hmac
import logging
import threading
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from lecture_prep.config import Settings, get_settings
from lecture_prep.tick import run_once

log = logging.getLogger(__name__)

router = APIRouter()
_running = threading.Lock()


def require_tick_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    secret: Annotated[str | None, Header(alias="X-Tick-Secret")] = None,
) -> None:
    if settings.tick_secret is None:
        raise HTTPException(503, "TICK_SECRET is not set")
    if not secret or not hmac.compare_digest(secret, settings.tick_secret.get_secret_value()):
        raise HTTPException(401, "wrong tick secret")


@router.post("/internal/tick", status_code=202, dependencies=[Depends(require_tick_secret)])
def trigger_tick(background: BackgroundTasks, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    if not _running.acquire(blocking=False):
        return {"status": "already running"}
    background.add_task(_run, settings)
    return {"status": "started"}


def _run(settings: Settings) -> None:
    try:
        run_once(settings)
    except Exception:  # a failed tick must not take the server down; the next call retries
        log.exception("Tick failed")
    finally:
        _running.release()
