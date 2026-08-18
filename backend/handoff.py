"""Deterministic chat-handoff helpers (question + contact). No Twilio I/O."""
from __future__ import annotations

import re
from typing import Optional, Sequence

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Consent / filler after the agent offers to collect contact details.
_ACK_RE = re.compile(
    r"""^(
        ok(ay)? |
        yes |
        yeah |
        yep |
        sure |
        please |
        thanks |
        thank\s+you |
        got\s+it |
        (alright|all\s+right) |
        sounds\s+good |
        go\s+ahead |
        do\s+that |
        let'?s\s+do\s+(that|it) |
        ok(ay)?[,.]?\s+let'?s\s+do\s+(that|it)
    )[\s.!?]*$""",
    re.IGNORECASE | re.VERBOSE,
)


def select_handoff_question(user_turns: Sequence[str]) -> Optional[str]:
    """
    Pick the visitor's original question from chat turns.

    `user_turns` is all user messages in order; the last turn is the contact
    line (name + email) and is ignored. Acknowledgements like "ok let's do that"
    are skipped so the WhatsApp payload is the real inquiry.
    """
    if len(user_turns) < 2:
        return None

    fallback: Optional[str] = None
    for turn in reversed(user_turns[:-1]):
        compact = " ".join(turn.split())
        if not compact or EMAIL_RE.search(compact):
            continue
        if _ACK_RE.match(compact):
            continue
        if fallback is None:
            fallback = compact
        if len(compact) > 10:
            return compact
    return fallback
