"""
Worker system for QueueCTL

Handles job execution, retry logic with exponential backoff,
and multi-worker coordination.
"""

import os
import signal
import subprocess
import time
import threading
import multiprocessing
from datetime import datetime, timezone
from typing import Optional, Dict, List
from pathlib import Path
import logging

from .job import Job, JobState
from .storage import JobStorage
from .config import Config


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Worker:
    """
    Individual worker process that executes jobs from the queue.
    
    Features:
    - Job execution with timeout support
    - Retry logic with exponential backoff
    - Graceful shutdown handling
    - Job locking to prevent race conditions
    """
    
    def __init__(self, worker_id: str, storage: JobStorage, config: Config):
        """
        Initialize worker.
        
        Args:
            worker_id: Unique worker identifier
            storage: Job storage instance
            config: Configuration instance
        """
        self.worker_id = worker_id
        self.storage = storage
        self.config = config
        self.running = False
        self.current_job: Optional[Job] = None
        self.shutdown_requested = False
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Worker {self.worker_id}: Received signal {signum}, initiating graceful shutdown")
        self.shutdown_requested = True
    
    def start(self):
        """Start the worker main loop"""
        self.running = True
        logger.info(f"Worker {self.worker_id}: Starting")
        
        try:
            while self.running and not self.shutdown_requested:
                # Get next job
                job = self.storage.get_next_job(self.worker_id)
                
                if job is None:
                    # No jobs available, wait and continue
                    time.sleep(1)
                    continue
                
                self.current_job = job
                logger.info(f"Worker {self.worker_id}: Processing job {job.id}")
                
                try:
                    # Execute the job
                    self._execute_job(job)
                except Exception as e:
                    logger.error(f"Worker {self.worker_id}: Error processing job {job.id}: {e}")
                    self._handle_job_failure(job, str(e))
                finally:
                    # Unlock the job
                    self.storage.unlock_job(job.id, self.worker_id)
                    self.current_job = None
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Fatal error: {e}")
        finally:
            self.running = False
            logger.info(f"Worker {self.worker_id}: Stopped")
    
    def stop(self):
        """Stop the worker gracefully"""
        logger.info(f"Worker {self.worker_id}: Stop requested")
        self.running = False
        self.shutdown_requested = True
    
    def _execute_job(self, job: Job):
        """
        Execute a job command.
        
        Args:
            job: Job to execute
        """
        job.increment_attempts()
        
        try:
            # Execute command with timeout
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=job.timeout or self.config.get('worker_timeout', 300),
                cwd=os.getcwd()
            )
            
            # Check return code
            if result.returncode == 0:
                # Job succeeded
                output = result.stdout.strip() if result.stdout else ""
                job.update_state(JobState.COMPLETED, output=output)
                logger.info(f"Worker {self.worker_id}: Job {job.id} completed successfully")
            else:
                # Job failed
                error = result.stderr.strip() if result.stderr else f"Command failed with return code {result.returncode}"
                self._handle_job_failure(job, error)
                
        except subprocess.TimeoutExpired:
            error = f"Job timed out after {job.timeout or self.config.get('worker_timeout', 300)} seconds"
            self._handle_job_failure(job, error)
            
        except Exception as e:
            error = f"Execution error: {str(e)}"
            self._handle_job_failure(job, error)
        
        # Update job in storage
        self.storage.update_job(job)
    
    def _handle_job_failure(self, job: Job, error: str):
        """
        Handle job failure with retry logic.
        
        Args:
            job: Failed job
            error: Error message
        """
        job.update_state(JobState.FAILED, error=error)
        
        if job.should_retry():
            # Schedule retry with exponential backoff
            delay = job.get_retry_delay(self.config.get('backoff_base', 2.0))
            logger.info(f"Worker {self.worker_id}: Job {job.id} failed (attempt {job.attempts}), retrying in {delay} seconds")
            
            # For simplicity, we'll reset to pending state immediately
            # In a production system, you might want to implement scheduled retries
            time.sleep(min(delay, 60))  # Cap delay at 60 seconds for responsiveness
            job.update_state(JobState.PENDING)
        else:
            # Move to dead letter queue
            logger.warning(f"Worker {self.worker_id}: Job {job.id} exceeded max retries, moving to DLQ")
            job.update_state(JobState.DEAD)
    
    def get_status(self) -> Dict:
        """
        Get worker status.
        
        Returns:
            Dictionary with worker status information
        """
        return {
            'worker_id': self.worker_id,
            'running': self.running,
            'current_job': self.current_job.id if self.current_job else None,
            'shutdown_requested': self.shutdown_requested
        }


def _run_worker_process(worker_id: str, storage_dir: str):
    """
    Run worker in separate process (standalone function to avoid pickle issues).
    
    Args:
        worker_id: Worker identifier
        storage_dir: Storage directory path
    """
    try:
        # Create fresh storage and config instances in the worker process
        # to avoid pickle issues with thread locks on Windows
        from queuectl.storage import JobStorage
        from queuectl.config import Config
        
        storage = JobStorage(storage_dir)
        config = Config()
        
        worker = Worker(worker_id, storage, config)
        worker.start()
    except Exception as e:
        logger.error(f"Worker {worker_id} crashed: {e}")


class WorkerManager:
    """
    Manages multiple worker processes.
    
    Features:
    - Start/stop multiple workers
    - Monitor worker health
    - Graceful shutdown coordination
    """
    
    def __init__(self, storage: JobStorage, config: Config):
        """
        Initialize worker manager.
        
        Args:
            storage: Job storage instance
            config: Configuration instance
        """
        self.storage = storage
        self.config = config
        self.workers: Dict[str, multiprocessing.Process] = {}
        self.worker_threads: Dict[str, threading.Thread] = {}
        self.running = False
        self.shutdown_event = multiprocessing.Event()
        
        # Create PID file for tracking
        self.pid_file = Path(storage.storage_dir) / "workers.pid"
    
    def start_workers(self, count: int = 1) -> List[str]:
        """
        Start worker processes.
        
        Args:
            count: Number of workers to start
            
        Returns:
            List of worker IDs started
        """
        started_workers = []
        
        for i in range(count):
            worker_id = f"worker-{int(time.time())}-{i}"
            
            # Create worker process
            process = multiprocessing.Process(
                target=_run_worker_process,
                args=(worker_id, str(self.storage.storage_dir)),
                name=f"queuectl-{worker_id}"
            )
            
            process.start()
            self.workers[worker_id] = process
            started_workers.append(worker_id)
            
            logger.info(f"Started worker {worker_id} (PID: {process.pid})")
        
        self.running = True
        self._update_pid_file()
        
        return started_workers

    def stop_workers(self, graceful: bool = True, timeout: int = 30):
        """
        Stop all worker processes.
        
        Args:
            graceful: Whether to wait for current jobs to complete
            timeout: Maximum time to wait for graceful shutdown
        """
        if not self.workers:
            logger.info("No workers to stop")
            return
        
        logger.info(f"Stopping {len(self.workers)} workers...")
        
        if graceful:
            # Signal all workers to stop gracefully
            self.shutdown_event.set()
            
            # Wait for workers to finish current jobs
            start_time = time.time()
            for worker_id, process in self.workers.items():
                remaining_time = max(0, timeout - (time.time() - start_time))
                if remaining_time > 0:
                    process.join(timeout=remaining_time)
                
                if process.is_alive():
                    logger.warning(f"Worker {worker_id} did not stop gracefully, terminating")
                    process.terminate()
                    process.join(timeout=5)
                    
                    if process.is_alive():
                        logger.error(f"Worker {worker_id} did not respond to termination, killing")
                        process.kill()
                        process.join()
        else:
            # Force stop all workers
            for worker_id, process in self.workers.items():
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                    
                    if process.is_alive():
                        process.kill()
                        process.join()
        
        self.workers.clear()
        self.running = False
        self._cleanup_pid_file()
        
        logger.info("All workers stopped")
    
    def get_worker_status(self) -> List[Dict]:
        """
        Get status of all workers.
        
        Returns:
            List of worker status dictionaries
        """
        status_list = []
        
        for worker_id, process in self.workers.items():
            status = {
                'worker_id': worker_id,
                'pid': process.pid,
                'alive': process.is_alive(),
                'exitcode': process.exitcode
            }
            status_list.append(status)
        
        return status_list
    
    def _update_pid_file(self):
        """Update PID file with current worker PIDs"""
        try:
            pids = [str(process.pid) for process in self.workers.values()]
            with open(self.pid_file, 'w') as f:
                f.write('\n'.join(pids))
        except Exception as e:
            logger.warning(f"Could not update PID file: {e}")
    
    def _cleanup_pid_file(self):
        """Remove PID file"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception as e:
            logger.warning(f"Could not remove PID file: {e}")
    
    def cleanup_dead_workers(self):
        """Remove dead worker processes from tracking"""
        dead_workers = []
        
        for worker_id, process in self.workers.items():
            if not process.is_alive():
                dead_workers.append(worker_id)
        
        for worker_id in dead_workers:
            del self.workers[worker_id]
            logger.info(f"Removed dead worker {worker_id}")
        
        if dead_workers:
            self._update_pid_file()


def get_running_workers(storage_dir: Optional[str] = None) -> List[int]:
    """
    Get list of running worker PIDs.
    
    Args:
        storage_dir: Storage directory path
        
    Returns:
        List of PIDs
    """
    if storage_dir is None:
        storage_dir = os.path.expanduser("~/.queuectl")
    
    pid_file = Path(storage_dir) / "workers.pid"
    
    if not pid_file.exists():
        return []
    
    try:
        with open(pid_file, 'r') as f:
            pids = [int(line.strip()) for line in f if line.strip()]
        
        # Verify PIDs are still running
        running_pids = []
        for pid in pids:
            try:
                os.kill(pid, 0)  # Check if process exists
                running_pids.append(pid)
            except (OSError, ProcessLookupError):
                pass
        
        return running_pids
        
    except Exception as e:
        logger.warning(f"Could not read PID file: {e}")
        return []