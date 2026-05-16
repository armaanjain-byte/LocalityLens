from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionState:
    """
    Tracks inferred agent workspace state during trajectory reconstruction.
    """

    current_file: Optional[str] = None
    cwd: Optional[str] = None
    open_buffers: set[str] = field(default_factory=set)

    def set_current_file(self, path: str) -> None:
        self.current_file = path
        self.open_buffers.add(path)

    def get_current_file(self) -> Optional[str]:
        return self.current_file