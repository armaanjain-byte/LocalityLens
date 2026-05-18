from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionState:
    """
    Tracks inferred agent workspace state during trajectory reconstruction.
    """

    current_file: Optional[str] = None
    cwd: Optional[str] = None

    def set_current_file(self, path: str) -> None:
        self.current_file = path

    def get_current_file(self) -> Optional[str]:
        return self.current_file
