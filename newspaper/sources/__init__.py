"""Collectors that fill one edition snapshot."""


def response_text(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    content = response.content
    if isinstance(content, str):
        return content
    return content.decode("utf-8")


def status_code(response) -> int:
    return int(getattr(response, "status_code", 200))
