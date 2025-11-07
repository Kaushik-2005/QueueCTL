"""
Main CLI interface for QueueCTL

Provides command-line interface for job queue management using typer.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

# Local imports
sys.path.append(str(Path(__file__).parent.parent))
from queuectl.job import Job, JobState, validate_job_data
from queuectl.storage import JobStorage
from queuectl.worker import WorkerManager, get_running_workers
from queuectl.config import Config
from queuectl.dlq import DeadLetterQueue
from queuectl.utils import (
    generate_job_id, validate_command, format_duration, 
    format_timestamp, calculate_age, truncate_string,
    safe_json_loads, validate_job_id, ColorFormatter
)

# Initialize typer app
app = typer.Typer(
    name="queuectl",
    help="CLI Background Job Queue System",
    add_completion=False
)

# Initialize console for rich output
console = Console()

# Global storage and config (initialized on first use)
_storage: Optional[JobStorage] = None
_config: Optional[Config] = None


def get_storage() -> JobStorage:
    """Get or initialize storage instance"""
    global _storage
    if _storage is None:
        _storage = JobStorage()
    return _storage


def get_config() -> Config:
    """Get or initialize config instance"""
    global _config
    if _config is None:
        storage = get_storage()
        config_data = storage.get_config()
        _config = Config(storage.storage_dir, config_data)
    return _config


def print_error(message: str):
    """Print error message"""
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str):
    """Print success message"""
    console.print(f"[green]Success:[/green] {message}")


def print_warning(message: str):
    """Print warning message"""
    console.print(f"[yellow]Warning:[/yellow] {message}")


@app.command()
def enqueue(
    job_data: str = typer.Argument(..., help="Job data as JSON string or path to JSON file"),
    validate_only: bool = typer.Option(False, "--validate", help="Only validate the job data"),
    file: bool = typer.Option(False, "--file", "-f", help="Treat job_data as a file path")
):
    """Enqueue a new job.
    
    Job data should be JSON with at minimum 'command' field.
    Optional fields: id, max_retries, timeout, priority
    
    Examples:
        queuectl enqueue '{"command": "echo hello world"}'
        queuectl enqueue '{"id": "job1", "command": "sleep 5", "max_retries": 5}'
        queuectl enqueue --file job.json
        queuectl enqueue -f job.json
    """
    try:
        # Parse job data from file or string
        if file or job_data.endswith('.json'):
            # Read from file
            try:
                import os
                if not os.path.exists(job_data):
                    print_error(f"File not found: {job_data}")
                    raise typer.Exit(1)
                
                with open(job_data, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    data = safe_json_loads(file_content)
                    if data is None:
                        print_error(f"Invalid JSON format in file: {job_data}")
                        raise typer.Exit(1)
            except Exception as e:
                print_error(f"Error reading file {job_data}: {e}")
                raise typer.Exit(1)
        else:
            # Parse as JSON string
            data = safe_json_loads(job_data)
            if data is None:
                print_error("Invalid JSON format")
                raise typer.Exit(1)
        
        # Validate required fields
        if not validate_job_data(data):
            print_error("Invalid job data. Required fields: 'command'")
            raise typer.Exit(1)
        
        # Validate command
        command = data.get('command', '')
        if not validate_command(command):
            print_error("Invalid or potentially dangerous command")
            raise typer.Exit(1)
        
        if validate_only:
            print_success("Job data is valid")
            return
        
        # Create job
        job_id = data.get('id') or generate_job_id()
        if not validate_job_id(job_id):
            print_error("Invalid job ID format")
            raise typer.Exit(1)
        
        job = Job.create(
            command=command,
            job_id=job_id,
            max_retries=data.get('max_retries', 3),
            timeout=data.get('timeout'),
            priority=data.get('priority', 0)
        )
        
        # Add to storage
        storage = get_storage()
        if storage.add_job(job):
            print_success(f"Job '{job.id}' enqueued successfully")
            console.print(f"Command: {truncate_string(job.command, 80)}")
        else:
            print_error(f"Job with ID '{job.id}' already exists")
            raise typer.Exit(1)
            
    except Exception as e:
        print_error(f"Failed to enqueue job: {e}")
        raise typer.Exit(1)


# Worker management commands
worker_app = typer.Typer(name="worker", help="Worker management commands")
app.add_typer(worker_app)


@worker_app.command("start")
def start_workers(
    count: int = typer.Option(1, "--count", "-c", help="Number of workers to start"),
    detach: bool = typer.Option(True, "--detach/--no-detach", help="Run workers in background")
):
    """Start worker processes"""
    if count < 1 or count > 10:
        print_error("Worker count must be between 1 and 10")
        raise typer.Exit(1)
    
    storage = get_storage()
    config = get_config()
    
    # Check if workers are already running
    running_pids = get_running_workers(storage.storage_dir)
    if running_pids:
        print_warning(f"Workers already running (PIDs: {', '.join(map(str, running_pids))})")
        return
    
    try:
        manager = WorkerManager(storage, config)
        worker_ids = manager.start_workers(count)
        
        print_success(f"Started {len(worker_ids)} worker(s)")
        for worker_id in worker_ids:
            console.print(f"  - {worker_id}")
            
    except Exception as e:
        print_error(f"Failed to start workers: {e}")
        raise typer.Exit(1)


@worker_app.command("stop")
def stop_workers(
    force: bool = typer.Option(False, "--force", help="Force stop workers"),
    timeout: int = typer.Option(30, "--timeout", help="Graceful shutdown timeout")
):
    """Stop all running workers"""
    storage = get_storage()
    config = get_config()
    
    running_pids = get_running_workers(storage.storage_dir)
    if not running_pids:
        print_warning("No workers are currently running")
        return
    
    try:
        manager = WorkerManager(storage, config)
        manager.stop_workers(graceful=not force, timeout=timeout)
        print_success("All workers stopped")
        
    except Exception as e:
        print_error(f"Failed to stop workers: {e}")
        raise typer.Exit(1)


@worker_app.command("status")
def worker_status():
    """Show worker status"""
    storage = get_storage()
    running_pids = get_running_workers(storage.storage_dir)
    
    if not running_pids:
        console.print("[yellow]No workers are currently running[/yellow]")
        return
    
    table = Table(title="Worker Status", box=box.ROUNDED)
    table.add_column("PID", style="cyan")
    table.add_column("Status", style="green")
    
    for pid in running_pids:
        table.add_row(str(pid), "Running")
    
    console.print(table)


@app.command()
def status():
    """Show overall system status"""
    storage = get_storage()
    
    # Get job counts
    job_counts = storage.get_job_counts()
    
    # Get worker status
    running_pids = get_running_workers(storage.storage_dir)
    
    # Create status panel
    status_text = f"""
[bold]Job Queue Status[/bold]
  Pending: {job_counts.get('pending', 0)}
  Processing: {job_counts.get('processing', 0)}
  Completed: {job_counts.get('completed', 0)}
  Failed: {job_counts.get('failed', 0)}
  Dead: {job_counts.get('dead', 0)}

[bold]Workers[/bold]
  Running: {len(running_pids)}
  PIDs: {', '.join(map(str, running_pids)) if running_pids else 'None'}

[bold]Storage[/bold]
  Directory: {storage.storage_dir}
    """
    
    console.print(Panel(status_text.strip(), title="QueueCTL Status", expand=False))


@app.command("list")
def list_jobs(
    state: Optional[str] = typer.Option(None, "--state", help="Filter by job state"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of jobs shown"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List jobs with optional filtering"""
    storage = get_storage()
    
    # Validate state filter
    job_state = None
    if state:
        try:
            job_state = JobState(state.lower())
        except ValueError:
            valid_states = [s.value for s in JobState]
            print_error(f"Invalid state '{state}'. Valid states: {', '.join(valid_states)}")
            raise typer.Exit(1)
    
    # Get jobs
    jobs = storage.list_jobs(state=job_state, limit=limit)
    
    if not jobs:
        console.print("[yellow]No jobs found[/yellow]")
        return
    
    if verbose:
        # Detailed view
        for job in jobs:
            panel_content = f"""
[bold]ID:[/bold] {job.id}
[bold]Command:[/bold] {job.command}
[bold]State:[/bold] {job.state.value}
[bold]Attempts:[/bold] {job.attempts}/{job.max_retries}
[bold]Created:[/bold] {format_timestamp(job.created_at or '')}
[bold]Updated:[/bold] {format_timestamp(job.updated_at or '')}
[bold]Age:[/bold] {calculate_age(job.created_at or '')}
"""
            if job.error:
                panel_content += f"[bold]Error:[/bold] {truncate_string(job.error, 100)}\n"
            if job.output:
                panel_content += f"[bold]Output:[/bold] {truncate_string(job.output, 100)}\n"
            
            console.print(Panel(panel_content.strip(), title=f"Job {job.id}", expand=False))
    else:
        # Table view
        table = Table(title=f"Jobs ({len(jobs)} total)", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Command", style="white")
        table.add_column("State", style="green")
        table.add_column("Attempts", style="yellow")
        table.add_column("Age", style="blue")
        
        for job in jobs:
            state_color = {
                JobState.PENDING: "yellow",
                JobState.PROCESSING: "blue", 
                JobState.COMPLETED: "green",
                JobState.FAILED: "red",
                JobState.DEAD: "magenta"
            }.get(job.state, "white")
            
            table.add_row(
                truncate_string(job.id, 20),
                truncate_string(job.command, 50),
                f"[{state_color}]{job.state.value}[/{state_color}]",
                f"{job.attempts}/{job.max_retries}",
                calculate_age(job.created_at or '')
            )
        
        console.print(table)


# DLQ management commands
dlq_app = typer.Typer(name="dlq", help="Dead Letter Queue management")
app.add_typer(dlq_app)


@dlq_app.command("list")
def dlq_list(
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of jobs shown"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List jobs in the dead letter queue"""
    storage = get_storage()
    dlq = DeadLetterQueue(storage)
    
    dead_jobs = dlq.list_dead_jobs(limit=limit)
    
    if not dead_jobs:
        console.print("[yellow]Dead letter queue is empty[/yellow]")
        return
    
    if verbose:
        for job in dead_jobs:
            analysis = dlq.analyze_job_failure(job.id)
            if analysis:
                suggestions_text = "\n".join(f"  • {s}" for s in analysis['suggestions'][:3])
                panel_content = f"""
[bold]ID:[/bold] {job.id}
[bold]Command:[/bold] {job.command}
[bold]Attempts:[/bold] {job.attempts}/{job.max_retries}
[bold]Final Error:[/bold] {truncate_string(job.error or 'Unknown', 100)}
[bold]Suggestions:[/bold]
{suggestions_text}
"""
                console.print(Panel(panel_content.strip(), title=f"Dead Job {job.id}", expand=False))
    else:
        table = Table(title=f"Dead Letter Queue ({len(dead_jobs)} jobs)", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Command", style="white")
        table.add_column("Attempts", style="yellow")
        table.add_column("Error", style="red")
        table.add_column("Age", style="blue")
        
        for job in dead_jobs:
            table.add_row(
                truncate_string(job.id, 20),
                truncate_string(job.command, 40),
                str(job.attempts),
                truncate_string(job.error or "Unknown", 30),
                calculate_age(job.created_at or '')
            )
        
        console.print(table)


@dlq_app.command("retry")
def dlq_retry(
    job_id: Optional[str] = typer.Argument(None, help="Job ID to retry (all if not specified)"),
    reset_attempts: bool = typer.Option(True, "--reset-attempts/--keep-attempts", help="Reset attempt count")
):
    """Retry jobs from the dead letter queue"""
    storage = get_storage()
    dlq = DeadLetterQueue(storage)
    
    if job_id:
        # Retry specific job
        if dlq.retry_job(job_id, reset_attempts):
            print_success(f"Job '{job_id}' moved back to pending queue")
        else:
            print_error(f"Failed to retry job '{job_id}' (not found in DLQ)")
            raise typer.Exit(1)
    else:
        # Retry all dead jobs
        results = dlq.retry_all_jobs(reset_attempts)
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        print_success(f"Retried {successful}/{total} jobs from DLQ")
        
        # Show failed retries
        for job_id, success in results.items():
            if not success:
                console.print(f"[red]Failed to retry job '{job_id}'[/red]")


@dlq_app.command("remove")
def dlq_remove(
    job_id: Optional[str] = typer.Argument(None, help="Job ID to remove (all if not specified)"),
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation prompt")
):
    """Permanently remove jobs from the dead letter queue"""
    storage = get_storage()
    dlq = DeadLetterQueue(storage)
    
    if job_id:
        # Remove specific job
        if not confirm:
            if not typer.confirm(f"Permanently remove job '{job_id}' from DLQ?"):
                print_warning("Operation cancelled")
                return
        
        if dlq.remove_job(job_id):
            print_success(f"Job '{job_id}' permanently removed from DLQ")
        else:
            print_error(f"Failed to remove job '{job_id}' (not found in DLQ)")
            raise typer.Exit(1)
    else:
        # Remove all dead jobs
        dead_jobs = dlq.list_dead_jobs()
        if not dead_jobs:
            console.print("[yellow]Dead letter queue is already empty[/yellow]")
            return
        
        if not confirm:
            if not typer.confirm(f"Permanently remove all {len(dead_jobs)} jobs from DLQ?"):
                print_warning("Operation cancelled")
                return
        
        results = dlq.clear_all()
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        print_success(f"Removed {successful}/{total} jobs from DLQ")


@dlq_app.command("stats")
def dlq_stats():
    """Show DLQ statistics"""
    storage = get_storage()
    dlq = DeadLetterQueue(storage)
    
    stats = dlq.get_statistics()
    
    if stats['total_jobs'] == 0:
        console.print("[yellow]Dead letter queue is empty[/yellow]")
        return
    
    stats_text = f"""
[bold]Total Jobs:[/bold] {stats['total_jobs']}
[bold]Average Attempts:[/bold] {stats['average_attempts']}

[bold]Oldest Job:[/bold]
  ID: {stats['oldest_job']['id']}
  Created: {format_timestamp(stats['oldest_job']['created_at'])}
  
[bold]Newest Job:[/bold]
  ID: {stats['newest_job']['id']}
  Created: {format_timestamp(stats['newest_job']['created_at'])}

[bold]Common Errors:[/bold]
"""
    
    for error, count in stats['common_errors'].items():
        stats_text += f"  {count}x: {truncate_string(error, 60)}\n"
    
    console.print(Panel(stats_text.strip(), title="DLQ Statistics", expand=False))


# Configuration commands
config_app = typer.Typer(name="config", help="Configuration management")
app.add_typer(config_app)


@config_app.command("show")
def config_show():
    """Show current configuration"""
    config = get_config()
    config_data = config.get_all()
    
    table = Table(title="Configuration", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Description", style="dim")
    
    descriptions = {
        'max_retries': 'Maximum number of job retries',
        'backoff_base': 'Exponential backoff base multiplier',
        'worker_timeout': 'Job execution timeout (seconds)',
        'cleanup_completed_after_hours': 'Auto-cleanup completed jobs after hours',
        'job_lock_timeout': 'Job lock expiration timeout (seconds)',
        'storage_dir': 'Data storage directory',
        'log_level': 'Logging verbosity level',
        'max_workers': 'Maximum number of workers'
    }
    
    for key, value in config_data.items():
        desc = descriptions.get(key, 'Custom setting')
        table.add_row(key, str(value), desc)
    
    console.print(table)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value")
):
    """Set configuration value"""
    config = get_config()
    storage = get_storage()
    
    # Try to convert value to appropriate type
    converted_value = value
    try:
        # Try integer
        if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
            converted_value = int(value)
        # Try float
        elif '.' in value:
            converted_value = float(value)
        # Try boolean
        elif value.lower() in ('true', 'false'):
            converted_value = value.lower() == 'true'
    except ValueError:
        pass
    
    # Set configuration
    if config.set(key, converted_value):
        # Update storage
        storage.update_config({key: converted_value})
        print_success(f"Set {key} = {converted_value}")
    else:
        validation_info = config.get_validation_info()
        if key in validation_info:
            print_error(f"Invalid value for '{key}'. Expected: {validation_info[key]}")
        else:
            print_error(f"Failed to set configuration '{key}'")
        raise typer.Exit(1)


@config_app.command("reset")
def config_reset(
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation prompt")
):
    """Reset configuration to defaults"""
    if not confirm:
        if not typer.confirm("Reset all configuration to defaults?"):
            print_warning("Operation cancelled")
            return
    
    config = get_config()
    storage = get_storage()
    
    config.reset_to_defaults()
    storage.update_config(config.get_all())
    
    print_success("Configuration reset to defaults")


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main()