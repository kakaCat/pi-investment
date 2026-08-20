#!/usr/bin/env python3
"""Monitor Agent OS Scheduler job status.

Displays all registered jobs, their schedules, and execution status.

Usage:
    python scripts/monitor_scheduler.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path

from application.services.agent_os_client import get_agent_os_client

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Note: Install 'rich' for better formatting: pip install rich")


async def monitor_jobs():
    """Display all jobs and their status."""
    client = get_agent_os_client()

    try:
        # Fetch all jobs
        jobs = await client.list_jobs(owner="quantsys-v2")

        if not jobs:
            print("No jobs registered in Agent OS Scheduler")
            return

        if RICH_AVAILABLE:
            # Rich table output
            console = Console()
            table = Table(title=f"Agent OS Scheduler Jobs ({len(jobs)} total)")

            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Schedule", style="yellow")
            table.add_column("Enabled", style="green", justify="center")
            table.add_column("Owner", style="blue")
            table.add_column("Timeout", style="magenta", justify="right")
            table.add_column("Retry", style="magenta", justify="right")

            for job in sorted(jobs, key=lambda j: j.get("name", "")):
                enabled_icon = "✓" if job.get("enabled") else "✗"
                enabled_style = "green" if job.get("enabled") else "red"

                table.add_row(
                    job.get("name", "N/A"),
                    job.get("cron", "N/A"),
                    f"[{enabled_style}]{enabled_icon}[/{enabled_style}]",
                    job.get("owner", "N/A"),
                    f"{job.get('timeout', 3600)}s",
                    str(job.get("retry_count", 0))
                )

            console.print(table)

            # Summary statistics
            enabled_count = sum(1 for j in jobs if j.get("enabled"))
            disabled_count = len(jobs) - enabled_count

            console.print(f"\n[green]Enabled:[/green] {enabled_count}")
            console.print(f"[red]Disabled:[/red] {disabled_count}")
            console.print(f"[cyan]Total:[/cyan] {len(jobs)}")

        else:
            # Plain text output
            print("=" * 80)
            print(f"Agent OS Scheduler Jobs ({len(jobs)} total)")
            print("=" * 80)
            print()

            # Header
            print(f"{'Name':<30} {'Schedule':<15} {'Enabled':<8} {'Timeout':<10}")
            print("-" * 80)

            for job in sorted(jobs, key=lambda j: j.get("name", "")):
                enabled = "Yes" if job.get("enabled") else "No"
                timeout = f"{job.get('timeout', 3600)}s"

                print(
                    f"{job.get('name', 'N/A'):<30} "
                    f"{job.get('cron', 'N/A'):<15} "
                    f"{enabled:<8} "
                    f"{timeout:<10}"
                )

            print()
            print("=" * 80)

            # Summary
            enabled_count = sum(1 for j in jobs if j.get("enabled"))
            disabled_count = len(jobs) - enabled_count

            print(f"Enabled: {enabled_count}")
            print(f"Disabled: {disabled_count}")
            print(f"Total: {len(jobs)}")

    except Exception as e:
        print(f"Error fetching jobs: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await client.close()


async def show_stats():
    """Display scheduler statistics."""
    client = get_agent_os_client()

    try:
        stats = await client.get_task_stats()

        if RICH_AVAILABLE:
            from rich.console import Console
            from rich.panel import Panel

            console = Console()
            console.print(Panel(
                f"[cyan]Total Tasks:[/cyan] {stats.get('total_tasks', 0)}\n"
                f"[green]Enabled:[/green] {stats.get('enabled_tasks', 0)}\n"
                f"[yellow]Pending:[/yellow] {stats.get('pending_tasks', 0)}\n"
                f"[blue]Running:[/blue] {stats.get('running_tasks', 0)}",
                title="Scheduler Statistics"
            ))
        else:
            print("\nScheduler Statistics:")
            print(f"  Total Tasks: {stats.get('total_tasks', 0)}")
            print(f"  Enabled: {stats.get('enabled_tasks', 0)}")
            print(f"  Pending: {stats.get('pending_tasks', 0)}")
            print(f"  Running: {stats.get('running_tasks', 0)}")

    except Exception as e:
        print(f"Note: Statistics not available ({e})")

    finally:
        await client.close()


async def show_recent_executions(limit: int = 10):
    """Display recent job executions."""
    client = get_agent_os_client()

    try:
        executions = await client.list_executions(limit=limit)

        if not executions:
            print("\nNo recent executions found")
            return

        if RICH_AVAILABLE:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(title=f"Recent Executions (last {len(executions)})")

            table.add_column("Time", style="cyan")
            table.add_column("Job", style="yellow")
            table.add_column("Status", style="green")
            table.add_column("Duration", style="magenta", justify="right")

            for execution in executions:
                status = execution.get("status", "unknown")
                status_style = "green" if status == "success" else "red"

                started = execution.get("started_at", "")
                if started:
                    try:
                        dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        time_str = started
                else:
                    time_str = "N/A"

                duration = execution.get("duration_ms", 0)
                duration_str = f"{duration}ms" if duration else "N/A"

                table.add_row(
                    time_str,
                    execution.get("task_name", "N/A"),
                    f"[{status_style}]{status}[/{status_style}]",
                    duration_str
                )

            console.print(table)

        else:
            print(f"\nRecent Executions (last {len(executions)}):")
            print("-" * 80)
            print(f"{'Time':<20} {'Job':<30} {'Status':<10} {'Duration':<10}")
            print("-" * 80)

            for execution in executions:
                started = execution.get("started_at", "N/A")
                if started != "N/A":
                    try:
                        dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        time_str = started
                else:
                    time_str = "N/A"

                duration = execution.get("duration_ms", 0)
                duration_str = f"{duration}ms" if duration else "N/A"

                print(
                    f"{time_str:<20} "
                    f"{execution.get('task_name', 'N/A'):<30} "
                    f"{execution.get('status', 'unknown'):<10} "
                    f"{duration_str:<10}"
                )

    except Exception as e:
        print(f"Note: Recent executions not available ({e})")

    finally:
        await client.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor Agent OS Scheduler")
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show scheduler statistics"
    )
    parser.add_argument(
        "--executions",
        type=int,
        metavar="N",
        help="Show last N executions"
    )

    args = parser.parse_args()

    # Always show jobs list
    await monitor_jobs()

    # Optionally show stats
    if args.stats:
        await show_stats()

    # Optionally show recent executions
    if args.executions:
        await show_recent_executions(limit=args.executions)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
