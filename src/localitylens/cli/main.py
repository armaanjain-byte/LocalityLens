"""Main entry point for the LocalityLens CLI."""

from pathlib import Path

import typer
from rich.console import Console

from localitylens.cli.commands import analyze, export
from localitylens.cli.commands.analyze import analyze_file
from localitylens.utils.logger import get_logger

console = Console()

app = typer.Typer(
    name="localitylens",
    help="AST-aware observability tool for coding-agent traces.",
    add_completion=False,
    no_args_is_help=True,
)

# Register command groups
app.add_typer(analyze.app, name="analyze")
app.add_typer(export.app, name="export")


@app.command("analyze-file")
def analyze_file_alias(
    trace_path: Path,
    output_dir: Path = typer.Option(
        Path("."),
        "--output-dir",
        help="Directory where reports/dashboard are generated.",
    ),
) -> None:
    """
    Shortcut command for analyzing a trace directly.
    """

    analyze_file(
        trace_path=trace_path,
        output_dir=output_dir,
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """
    LocalityLens:
    Detect semantic thrashing and context locality failures
    in coding-agent workflows.
    """

    if verbose:
        get_logger("localitylens", level="DEBUG")

    if ctx.invoked_subcommand is None:
        console.print(
            "\n[bold red]Missing command.[/bold red]\n"
        )

        console.print(
            "[bold]Examples:[/bold]\n"
        )

        console.print(
            "  localitylens analyze file data/processed/normalized_trace.json\n"
        )

        console.print(
            "  localitylens analyze-file data/processed/normalized_trace.json\n"
        )

        raise typer.Exit()


if __name__ == "__main__":
    app()