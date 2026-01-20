"""Docker Compose based CLI commands."""

import asyncio
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from fixagent_verifier.compose_generator import ComposeTaskGenerator
from fixagent_verifier.project_detector import ProjectType

console = Console()


def generate_compose(
    pr_url: str = typer.Option(..., "--pr-url", help="GitHub PR URL"),
    project_type: str = typer.Option(
        None, "--project-type", help="Project type (auto-detect if not specified)"
    ),
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
    github_token: str = typer.Option(
        None, "--token", envvar="GITHUB_TOKEN", help="GitHub API token"
    ),
):
    """
    Generate a docker-compose based task from PR URL.

    Example:
        fixagent-verifier generate-compose --pr-url https://github.com/owner/repo/pull/123
    """
    console.print(
        Panel.fit(
            "[bold blue]FixAgent Verifier[/bold blue]\n"
            "Docker Compose Task Generator",
            border_style="blue",
        )
    )

    console.print(f"\n[bold]Generating task from PR...[/bold]")
    console.print(f"   PR URL: {pr_url}")

    # Convert project type string to enum
    project_type_enum = ProjectType(project_type) if project_type else None

    with console.status("[bold green]Fetching PR info and generating task..."):
        generator = ComposeTaskGenerator(tasks_dir)
        task_dir = asyncio.run(
            generator.generate_from_pr_url(pr_url, project_type_enum, github_token)
        )

    console.print(f"\n[green]✓ Task generated successfully![/green]")
    console.print(f"   Location: {task_dir}")
    console.print(f"   Task name: {task_dir.name}")

    # Show files created
    console.print(f"\n[bold]Files created:[/bold]")
    for file in task_dir.iterdir():
        if file.is_file():
            console.print(f"   - {file.name}")

    # Show usage instructions
    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"   1. Run: [cyan]fixagent-verifier run-compose --task {task_dir.name}[/cyan]")
    console.print(f"   2. Or:  [cyan]cd {task_dir} && docker compose up[/cyan]")


def run_compose(
    task: str = typer.Option(..., "--task", help="Task name (e.g., springboot-aws-k8s_1)"),
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
    follow_logs: bool = typer.Option(True, "--follow/--no-follow", help="Follow logs"),
    cleanup: bool = typer.Option(True, "--cleanup/--no-cleanup", help="Cleanup after run"),
):
    """
    Run a docker-compose based task.

    Example:
        fixagent-verifier run-compose --task springboot-aws-k8s_1
    """
    task_dir = tasks_dir / task
    compose_file = task_dir / "docker-compose.yaml"

    if not compose_file.exists():
        console.print(f"[red]✗ No docker-compose.yaml found in {task_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Running task: {task}[/bold]\n")

    # Run docker compose
    try:
        cmd = ["docker", "compose", "up"]
        if not follow_logs:
            cmd.append("-d")
        cmd.append("--abort-on-container-exit")

        console.print(f"[dim]$ cd {task_dir} && docker compose up[/dim]\n")

        result = subprocess.run(cmd, cwd=task_dir, check=False)

        # Check result
        result_file = task_dir / "logs" / "verifier" / "result.txt"
        exit_code_file = task_dir / "logs" / "verifier" / "exit_code.txt"

        if result_file.exists():
            result_content = result_file.read_text().strip()
            success = result_content == "1"

            console.print("")
            if success:
                console.print("[green]✓ Verification PASSED[/green]")
            else:
                console.print("[red]✗ Verification FAILED[/red]")

            # Show exit code
            if exit_code_file.exists():
                exit_code = exit_code_file.read_text().strip()
                console.print(f"   Exit code: {exit_code}")

            # Show result location
            console.print(f"   Results: {task_dir}/logs/verifier/")

            if not success:
                raise typer.Exit(1)
        else:
            console.print("[yellow]! No result file found[/yellow]")
            raise typer.Exit(1)

    finally:
        if cleanup:
            console.print("\n[dim]Cleaning up containers...[/dim]")
            subprocess.run(
                ["docker", "compose", "down"],
                cwd=task_dir,
                capture_output=True,
                check=False,
            )


def run_all_compose(
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
    concurrent: int = typer.Option(4, "--concurrent", "-c", help="Concurrent tasks"),
    pattern: str = typer.Option("*", "--pattern", help="Task name pattern"),
    skip_verified: bool = typer.Option(
        False, "--skip-verified", help="Skip already verified tasks"
    ),
):
    """
    Run all docker-compose tasks in parallel.

    Example:
        fixagent-verifier run-all-compose --concurrent 4
    """
    console.print(
        Panel.fit(
            "[bold blue]FixAgent Verifier[/bold blue]\n"
            "Batch Docker Compose Execution",
            border_style="blue",
        )
    )

    # Find all tasks
    task_dirs = []
    for task_dir in tasks_dir.glob(pattern):
        if task_dir.is_dir() and (task_dir / "docker-compose.yaml").exists():
            # Check if should skip
            if skip_verified:
                result_file = task_dir / "logs" / "verifier" / "result.txt"
                if result_file.exists() and result_file.read_text().strip() == "1":
                    continue
            task_dirs.append(task_dir)

    if not task_dirs:
        console.print("[yellow]No tasks found matching criteria[/yellow]")
        return

    console.print(f"\n[bold]Found {len(task_dirs)} tasks to run[/bold]")
    console.print(f"   Concurrency: {concurrent}")
    console.print(f"   Pattern: {pattern}\n")

    # Run tasks in parallel
    results = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_progress = progress.add_task(
            "[cyan]Running verifications...", total=len(task_dirs)
        )

        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = {
                executor.submit(_run_single_compose_task, task_dir): task_dir
                for task_dir in task_dirs
            }

            for future in as_completed(futures):
                task_dir = futures[future]
                try:
                    success = future.result()
                    results[task_dir.name] = success
                    status = "✓" if success else "✗"
                    console.print(f"{status} {task_dir.name}")
                except Exception as e:
                    results[task_dir.name] = False
                    console.print(f"✗ {task_dir.name}: {e}")

                progress.update(task_progress, advance=1)

    # Display summary
    _display_summary(results)

    # Exit with error if any failed
    if not all(results.values()):
        raise typer.Exit(1)


def list_compose_tasks(
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
    show_status: bool = typer.Option(True, "--status/--no-status", help="Show verification status"),
):
    """
    List all docker-compose tasks.

    Example:
        fixagent-verifier list-compose-tasks
    """
    # Find all tasks
    task_dirs = []
    for task_dir in tasks_dir.iterdir():
        if task_dir.is_dir() and (task_dir / "docker-compose.yaml").exists():
            task_dirs.append(task_dir)

    if not task_dirs:
        console.print("[yellow]No tasks found[/yellow]")
        return

    # Create table
    table = Table(title=f"Docker Compose Tasks ({len(task_dirs)})")
    table.add_column("Task Name", style="cyan")
    table.add_column("PR", style="magenta")

    if show_status:
        table.add_column("Status", style="green")

    for task_dir in sorted(task_dirs):
        # Parse task name (format: repo_pr)
        task_name = task_dir.name
        parts = task_name.rsplit("_", 1)
        repo_name = parts[0] if len(parts) > 1 else task_name
        pr_number = parts[1] if len(parts) > 1 else "?"

        row = [task_name, f"#{pr_number}"]

        if show_status:
            result_file = task_dir / "logs" / "verifier" / "result.txt"
            if result_file.exists():
                result = result_file.read_text().strip()
                status = "✓ Passed" if result == "1" else "✗ Failed"
            else:
                status = "⋯ Not run"
            row.append(status)

        table.add_row(*row)

    console.print(table)


def _run_single_compose_task(task_dir: Path) -> bool:
    """Run a single compose task (used by ThreadPoolExecutor)."""
    try:
        # Run docker compose
        result = subprocess.run(
            ["docker", "compose", "up", "--abort-on-container-exit"],
            cwd=task_dir,
            capture_output=True,
            check=False,
        )

        # Check result
        result_file = task_dir / "logs" / "verifier" / "result.txt"
        if result_file.exists():
            return result_file.read_text().strip() == "1"

        return False

    finally:
        # Cleanup
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=task_dir,
            capture_output=True,
            check=False,
        )


def _display_summary(results: dict[str, bool]):
    """Display summary of results."""
    total = len(results)
    success = sum(1 for v in results.values() if v)
    failed = total - success

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"   Total: {total}")
    console.print(f"   [green]Success: {success}[/green]")
    console.print(f"   [red]Failed: {failed}[/red]")

    if failed > 0:
        console.print(f"\n[bold]Failed tasks:[/bold]")
        for task_name, success in results.items():
            if not success:
                console.print(f"   - {task_name}")
