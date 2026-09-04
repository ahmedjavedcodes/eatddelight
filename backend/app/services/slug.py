import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _NON_ALNUM.sub("-", name.strip().lower()).strip("-")
    return slug or "item"
