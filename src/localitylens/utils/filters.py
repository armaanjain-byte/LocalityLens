IGNORED_TARGETS = {
    "session",
    "unknown_file",
    "search_operation",
}


def is_real_file_target(target: str) -> bool:
    return target not in IGNORED_TARGETS