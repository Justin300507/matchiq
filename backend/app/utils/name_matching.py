def names_match(name: str, candidate: str) -> bool:
    name, candidate = name.lower(), candidate.lower()
    return name in candidate or candidate in name
