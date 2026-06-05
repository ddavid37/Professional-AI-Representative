#!/usr/bin/env python3
"""Send a test WhatsApp message via Twilio sandbox."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from backend.whatsapp import send_test_message  # noqa: E402


def main() -> None:
    result = send_test_message()
    print(result)
    if result.get("status") != "sent":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
