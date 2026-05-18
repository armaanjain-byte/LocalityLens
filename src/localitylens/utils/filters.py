import re

IGNORED_TARGETS = {
    "session",
    "unknown_file",
    "search_operation",
    "llm",
    "bash",
    "git",
    "grep",
    "find",
    "submit",
}

_FILE_EXT_PATTERN = re.compile(r"\.[a-zA-Z0-9]{1,10}$")


def is_real_file_target(target: str) -> bool:
    target = target.strip()
    if not target or target in IGNORED_TARGETS:
        return False
    if len(target) > 300:
        return False
    if " " in target:
        return False
    return "/" in target or "\\" in target or _FILE_EXT_PATTERN.search(target) is not None
