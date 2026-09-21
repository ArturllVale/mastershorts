"""Shared text utilities."""

def truncate_bytes(text: str, max_bytes: int) -> str:
    """Truncate text to fit within max_bytes when UTF-8 encoded."""
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes]
    # Back off to a valid UTF-8 boundary
    return truncated.decode('utf-8', errors='ignore')
