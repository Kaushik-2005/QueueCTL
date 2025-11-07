"""
Demo script to test QueueCTL CLI functionality
"""
import sys
import json
import subprocess
import time
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from queuectl.job import Job, JobState
from queuectl.storage import JobStorage
from queuectl.config import Config
from queuectl.dlq import DeadLetterQueue

def demo_basic_functionality():
    """Demonstrate basic QueueCTL functionality without CLI"""
    print("🚀 QueueCTL Demo - Basic Functionality")
    print("=" * 50)
    
    # Initialize storage
    storage = JobStorage()
    config = Config()
    dlq = DeadLetterQueue(storage)
    
    print("\n1. Creating and enqueuing jobs...")
    
    # Create some test jobs
    jobs = [
        Job.create("echo 'Job 1: Hello World!'", job_id="demo-job-1"),
        Job.create("echo 'Job 2: QueueCTL is working!'", job_id="demo-job-2"),
        Job.create("echo 'Job 3: Testing priority'", job_id="demo-job-3", priority=10),
        Job.create("nonexistent-command", job_id="demo-job-fail", max_retries=2),  # Will fail
    ]
    
    # Add jobs to storage
    for job in jobs:
        success = storage.add_job(job)
        print(f"   ✓ Added job '{job.id}': {job.command[:50]}...")
    
    print(f"\n2. Current job counts:")
    counts = storage.get_job_counts()
    for state, count in counts.items():
        if count > 0:
            print(f"   {state}: {count}")
    
    print(f"\n3. Listing pending jobs:")
    pending_jobs = storage.list_jobs(state=JobState.PENDING)
    for job in pending_jobs:
        print(f"   ID: {job.id}, Priority: {job.priority}, Command: {job.command}")
    
    print(f"\n4. Simulating job processing...")
    
    # Simulate processing jobs
    for job in pending_jobs[:2]:  # Process first 2 jobs
        print(f"   Processing job: {job.id}")
        
        # Get job for worker
        worker_job = storage.get_next_job("demo-worker")
        if worker_job:
            # Simulate successful execution
            worker_job.update_state(JobState.COMPLETED, output="Success!")
            storage.update_job(worker_job)
            storage.unlock_job(worker_job.id, "demo-worker")
            print(f"   ✓ Completed job: {worker_job.id}")
    
    # Simulate failing job
    failed_job = storage.get_next_job("demo-worker")
    if failed_job and failed_job.id == "demo-job-fail":
        print(f"   Processing failing job: {failed_job.id}")
        failed_job.increment_attempts()
        failed_job.update_state(JobState.FAILED, error="Command not found")
        
        if not failed_job.should_retry():
            failed_job.update_state(JobState.DEAD)
            print(f"   ✗ Job moved to DLQ: {failed_job.id}")
        
        storage.update_job(failed_job)
        storage.unlock_job(failed_job.id, "demo-worker")
    
    print(f"\n5. Final status:")
    final_counts = storage.get_job_counts()
    for state, count in final_counts.items():
        if count > 0:
            print(f"   {state}: {count}")
    
    print(f"\n6. Dead Letter Queue:")
    dead_jobs = dlq.list_dead_jobs()
    if dead_jobs:
        for job in dead_jobs:
            print(f"   Dead Job: {job.id} - Error: {job.error}")
        
        print(f"\n   Analyzing failure...")
        analysis = dlq.analyze_job_failure(dead_jobs[0].id)
        if analysis:
            print(f"   Error Type: {analysis['error_analysis']['error_type']}")
            print(f"   Suggestions: {len(analysis['suggestions'])} recommendations")
    else:
        print("   No dead jobs found")
    
    print(f"\n7. Configuration:")
    config_data = config.get_all()
    important_settings = ['max_retries', 'backoff_base', 'worker_timeout']
    for setting in important_settings:
        print(f"   {setting}: {config_data.get(setting)}")
    
    print("\n" + "=" * 50)
    print("✅ Demo completed successfully!")
    print("\nTo use the CLI interface:")
    print("  queuectl status")
    print("  queuectl list")
    print("  queuectl dlq list")
    
    return True

def demo_cli_usage():
    """Show CLI usage examples"""
    print("\n🖥️  CLI Usage Examples")
    print("=" * 50)
    
    examples = [
        ("Show status", "queuectl status"),
        ("List jobs", "queuectl list"),
        ("List DLQ", "queuectl dlq list"),
        ("Show config", "queuectl config show"),
        ("Worker help", "queuectl worker --help"),
    ]
    
    for description, command in examples:
        print(f"\n{description}:")
        print(f"  {command}")
    
    print(f"\nTo enqueue a job (note: JSON escaping needed in PowerShell):")
    print(f'  queuectl enqueue \'{{"command": "echo test"}}\'')

    print(f"\n🎉 QueueCTL demonstration completed successfully!")

if __name__ == "__main__":
    success = demo_basic_functionality()
    demo_cli_usage()
    
    if not success:
        print(f"\n❌ Some issues were encountered during the demo.")