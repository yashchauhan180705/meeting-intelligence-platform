"""Speaker renaming module.

Pure function — no I/O. Substitutes speaker names in text
while respecting word boundaries to avoid partial matches.
"""

from __future__ import annotations

import re


def apply_rename(summary_text: str, old_name: str, new_name: str) -> str:
    """Replace all occurrences of *old_name* with *new_name* in text.

    Uses word-boundary matching to avoid partial replacements
    (e.g. "Speaker 1" should not match inside "Speaker 10").

    Args:
        summary_text: The text to transform.
        old_name: The name to find (case-sensitive).
        new_name: The replacement name.

    Returns:
        Transformed text with all occurrences replaced.
    """
    if not old_name or not summary_text:
        return summary_text

    # Word boundaries only work when both ends are word characters. Names
    # ending in punctuation (for example, "Dr. Smith (PhD)") need a
    # lookaround-based boundary instead.
    pattern = r"(?<!\w)" + re.escape(old_name) + r"(?!\w)"
    return re.sub(pattern, new_name, summary_text)
