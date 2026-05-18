"""Main entry point for the LocalityLens CLI."""

import typer

from localitylens.cli.commands import analyze, export
from localitylens.utils.logger import get_logger

app = typer.Typer(
    name="LocalityLens",
    help="AST-aware observability tool for coding-agent traces.",
    add_completion=False,
)

# Register command sub-modules
app.add_typer(analyze.app, name="analyze")
app.add_typer(export.app, name="export")


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging")) -> None:
    """
    LocalityLens: Detect semantic thrashing and context locality failures 
    in coding-agent workflows.
    """
    if verbose:
        get_logger("localitylens", level="DEBUG")


if __name__ == "__main__":
    app()
