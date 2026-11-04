"""Lets tests import the back end's rules engine directly, without starting the server."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tof.characters import engine  # noqa: E402

__all__ = ["engine"]
