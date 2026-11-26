from __future__ import annotations


class Utf8ByteBudget:
    """Offline conservative budget.

    This intentionally does not claim model-token accuracy. It counts UTF-8
    bytes, which is deterministic offline and safe for enforcing a hard limit
    expressed in conservative budget units.
    """

    name = "utf8_bytes"

    def count(self, text: str) -> int:
        return len(text.encode("utf-8"))
