"""Party ids. The slug is the id; a DUNS number is stored beside it and never used as one."""

import re

_SUFFIXES = {"inc", "llc", "lp", "ltd", "limited", "co", "corp", "corporation", "company"}


def slug(name: str) -> str:
    text = name.casefold().replace("&", " and ")
    text = re.sub(r"\bl\.p\.?\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [word for word in text.split() if word not in _SUFFIXES]
    return "-".join(words)


def party_id(kind: str, name: str) -> str:
    return f"{kind}:{slug(name)}"
