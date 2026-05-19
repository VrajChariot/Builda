import os
from datetime import datetime
from typing import Literal

LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


def _get_verbosity() -> int:
    v = os.environ.get("VERBOSITY", os.environ.get("VERBOSE", ""))
    if v == "":
        return LEVEL_ORDER["INFO"]
    try:
        iv = int(v)
        # map integer levels: 0 -> WARNING, 1 -> INFO, 2 -> DEBUG
        if iv <= 0:
            return LEVEL_ORDER["WARNING"]
        if iv == 1:
            return LEVEL_ORDER["INFO"]
        return LEVEL_ORDER["DEBUG"]
    except Exception:
        return LEVEL_ORDER.get(v.upper(), LEVEL_ORDER["INFO"])


VERBOSITY = _get_verbosity()


def ui_print(level: Literal["DEBUG", "INFO", "WARNING", "ERROR"], module: str, message: str) -> None:
    """Simple CLI-style printer with verbosity control.

    - Default verbosity shows INFO, WARNING, ERROR.
    - Set `VERBOSITY=2` (or `VERBOSE=2`) to include DEBUG messages.
    """
    if LEVEL_ORDER[level] < VERBOSITY:
        return
    ts = datetime.now().isoformat(sep=" ", timespec="seconds")
    print(f"{ts} {level:<7} [{module}] {message}")
