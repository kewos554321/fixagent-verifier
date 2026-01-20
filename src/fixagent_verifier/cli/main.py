"""Main CLI entry point."""

import asyncio
from pathlib import Path
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fixagent_verifier.github.client import GitHubClient
from fixagent_verifier.models.task import TaskConfig
from fixagent_verifier.models.trial import EnvironmentConfig, TrialConfig, VerifierConfig
from fixagent_verifier.utils.trial import run_trial
from fixagent_verifier.cli import compose_commands

app = typer.Typer(
    name="fixagent-verifier",
    help="CLI tool for automated PR verification through isolated Docker environments",
)
console = Console()

# Add compose commands
app.command(name="generate-compose")(compose_commands.generate_compose)
app.command(name="run-compose")(compose_commands.run_compose)
app.command(name="run-all-compose")(compose_commands.run_all_compose)
app.command(name="list-compose")(compose_commands.list_compose_tasks)


@app.command()
def run_single(
    pr_url: str = typer.Option(..., "--pr-url", help="GitHub PR URL to verify"),
    project_type: str = typer.Option("gradle", "--project-type", help="Project type"),
    output_dir: Path = typer.Option(
        Path("results"), "--output", "-o", help="Output directory"
    ),
    github_token: str = typer.Option(
        None, "--token", envvar="GITHUB_TOKEN", help="GitHub API token"
    ),
    cpus: int = typer.Option(2, "--cpus", help="CPU cores"),
    memory_mb: int = typer.Option(4096, "--memory", help="Memory in MB"),
    timeout_sec: float = typer.Option(1800.0, "--timeout", help="Timeout in seconds"),
):
    """
    Verify a single PR by URL.

    Example:
        fixagent-verifier run-single --pr-url https://github.com/owner/repo/pull/123
    """
    console.print("[bold blue]FixAgent Verifier[/bold blue] - PR Verification via Docker\n")

    asyncio.run(
        _run_single_async(
            pr_url, project_type, output_dir, github_token, cpus, memory_mb, timeout_sec
        )
    )


async def _run_single_async(
    pr_url: str,
    project_type: str,
    output_dir: Path,
    github_token: str | None,
    cpus: int,
    memory_mb: int,
    timeout_sec: float,
):
    """Async implementation of run_single."""
    console.print(f"[bold]1. Fetching PR info:[/bold] {pr_url}")
    github_client = GitHubClient(token=github_token)
    try:
        pr_info = await github_client.get_pr_info(pr_url)
        console.print(f"   ✓ #{pr_info.pr_number}: {pr_info.repo_owner}/{pr_info.repo_name}")
        console.print(f"   ✓ {pr_info.source_branch}@{pr_info.source_commit[:7]} → {pr_info.target_branch}@{pr_info.target_commit[:7]}")
    except Exception as e:
        console.print(f"   [red]✗ Failed: {e}[/red]")
        raise typer.Exit(1)

    # Create task config
    task_config = TaskConfig(
        task_id=f"pr-{pr_info.pr_number}",
        pr_url=pr_url,
        project_type=project_type,
        timeout_sec=timeout_sec,
        cpus=cpus,
        memory_mb=memory_mb,
    )

    # Create trial config
    trial_config = TrialConfig(
        trial_id=uuid4(),
        trial_name=f"pr-{pr_info.pr_number}__trial-{uuid4().hex[:8]}",
        task=task_config,
        pr_info=pr_info,
        environment=EnvironmentConfig(cpus=cpus, memory_mb=memory_mb),
        verifier=VerifierConfig(timeout_sec=timeout_sec, project_type=project_type),
        output_dir=output_dir,
    )

    console.print(f"\n[bold]2. Docker:[/bold] {cpus}CPU/{memory_mb}MB | [bold]3. Merging PR[/bold] | [bold]4. Verifying ({project_type}, {timeout_sec}s)[/bold]")

    with console.status("[bold green]Running verification..."):
        result = await run_trial(trial_config)

    console.print(f"\n[bold]Results:[/bold]")

    status = "[green]✓ PASSED[/green]" if result.success else "[red]✗ FAILED[/red]"
    console.print(f"   {status}")

    if result.verification_result:
        duration = result.verification_result.duration_sec
        tasks = ", ".join(result.verification_result.tasks_run) or "N/A"
        console.print(f"   Duration: {duration:.1f}s | Tasks: {tasks}")

    console.print(f"   Logs: {result.trial_dir}")

    if result.exception_info:
        console.print(f"\n[red]Error: {result.exception_info.exception_type} - {result.exception_info.exception_message}[/red]")

    if result.verification_result and not result.verification_result.success:
        console.print(f"\n[yellow]Last 30 lines:[/yellow]")
        lines = result.verification_result.compilation_output.split("\n")
        for line in lines[-30:]:
            console.print(f"   {line}")

    if not result.success:
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    from fixagent_verifier import __version__

    console.print(f"fixagent-verifier version {__version__}")


if __name__ == "__main__":
    app()
