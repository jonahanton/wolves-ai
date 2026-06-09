_MARKER = "\n\n[... truncated ...]\n\n"


def truncate_result(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= len(_MARKER):
        return text[:max_chars]
    # Keep opening context (2/3) and tail (1/3), dropping the middle.
    usable = max_chars - len(_MARKER)
    front = usable * 2 // 3
    back = usable - front
    return text[:front] + _MARKER + text[-back:]
