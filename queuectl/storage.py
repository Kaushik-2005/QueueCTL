"""
Storage layer for QueueCTL system

Provides persistent storage for jobs using JSON files with atomic operations
and file locking to prevent race conditions.
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from contextlib import contextmanager

from .job import Job, JobState


class JobStorage:
    """
    Persistent storage for jobs using JSON files.
    
    Features:
    - Atomic operations using temporary files
    - File locking to prevent race conditions
    - Cross-platform compatibility
    - Job state filtering and querying
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize storage with specified directory.
        
        Args:
            storage_dir: Directory for storage files, defaults to ~/.queuectl
        """
        if storage_dir is None:
            storage_dir = os.path.expanduser("~/.queuectl")
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.jobs_file = self.storage_dir / "jobs.json"
        self.locks_file = self.storage_dir / "locks.json"
        self.config_file = self.storage_dir / "config.json"
        
        # Thread-local lock for preventing concurrent access within same process
        self._thread_lock = threading.RLock()
        
        # Initialize files if they don't exist
        self._initialize_files()
    
    def _initialize_files(self):
        """Initialize storage files with empty data if they don't exist"""
        if not self.jobs_file.exists():
            self._write_json_file(self.jobs_file, {})
        
        if not self.locks_file.exists():
            self._write_json_file(self.locks_file, {})
        
        if not self.config_file.exists():
            default_config = {
                "max_retries": 3,
                "backoff_base": 2.0,
                "worker_timeout": 300,
                "cleanup_completed_after_hours": 24
            }
            self._write_json_file(self.config_file, default_config)
    
    @contextmanager
    def _file_lock(self, file_path: Path):
        """
        Simple file locking using lock directories.
        
        Args:
            file_path: Path to file to lock
        """
        lock_dir = file_path.with_suffix(file_path.suffix + '.lock')
        max_wait = 30  # seconds
        wait_interval = 0.1
        waited = 0
        
        # Try to acquire lock
        while waited < max_wait:
            try:
                lock_dir.mkdir(exist_ok=False)
                break
            except FileExistsError:
                time.sleep(wait_interval)
                waited += wait_interval
        else:
            raise TimeoutError(f"Could not acquire lock for {file_path} after {max_wait} seconds")
        
        try:
            yield
        finally:
            # Release lock
            try:
                lock_dir.rmdir()
            except (FileNotFoundError, OSError):
                pass
    
    def _read_json_file(self, file_path: Path) -> Dict:
        """
        Read JSON file with error handling.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON data or empty dict if file doesn't exist/is invalid
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _write_json_file(self, file_path: Path, data: Dict):
        """
        Write JSON file atomically using temporary file.
        
        Args:
            file_path: Path to JSON file
            data: Data to write
        """
        # Ensure all job states are serialized properly
        if file_path.name == "jobs.json":
            serialized_data = {}
            for key, value in data.items():
                if isinstance(value, dict) and 'state' in value:
                    # Make sure state is a string, not an enum
                    if hasattr(value['state'], 'value'):
                        value = value.copy()
                        value['state'] = value['state'].value
                serialized_data[key] = value
            data = serialized_data
        
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode='w', 
            dir=self.storage_dir, 
            delete=False,
            encoding='utf-8'
        ) as tmp_file:
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            tmp_file_path = tmp_file.name
        
        # Atomic move to final location
        if os.name == 'nt':  # Windows
            if file_path.exists():
                file_path.unlink()
        
        Path(tmp_file_path).replace(file_path)
    
    def add_job(self, job: Job) -> bool:
        """
        Add a new job to storage.
        
        Args:
            job: Job to add
            
        Returns:
            True if job was added, False if job ID already exists
        """
        with self._thread_lock:
            with self._file_lock(self.jobs_file):
                jobs_data = self._read_json_file(self.jobs_file)
                
                # Check if job already exists
                if job.id in jobs_data:
                    return False
                
                # Add job
                jobs_data[job.id] = job.to_dict()
                self._write_json_file(self.jobs_file, jobs_data)
                
                return True
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID to retrieve
            
        Returns:
            Job instance or None if not found
        """
        with self._thread_lock:
            with self._file_lock(self.jobs_file):
                jobs_data = self._read_json_file(self.jobs_file)
                
                if job_id not in jobs_data:
                    return None
                
                return Job.from_dict(jobs_data[job_id])
    
    def update_job(self, job: Job) -> bool:
        """
        Update existing job in storage.
        
        Args:
            job: Job to update
            
        Returns:
            True if job was updated, False if job doesn't exist
        """
        with self._thread_lock:
            with self._file_lock(self.jobs_file):
                jobs_data = self._read_json_file(self.jobs_file)
                
                if job.id not in jobs_data:
                    return False
                
                jobs_data[job.id] = job.to_dict()
                self._write_json_file(self.jobs_file, jobs_data)
                
                return True
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete job from storage.
        
        Args:
            job_id: Job ID to delete
            
        Returns:
            True if job was deleted, False if job doesn't exist
        """
        with self._thread_lock:
            with self._file_lock(self.jobs_file):
                jobs_data = self._read_json_file(self.jobs_file)
                
                if job_id not in jobs_data:
                    return False
                
                del jobs_data[job_id]
                self._write_json_file(self.jobs_file, jobs_data)
                
                return True
    
    def list_jobs(self, state: Optional[JobState] = None, limit: Optional[int] = None) -> List[Job]:
        """
        List jobs, optionally filtered by state.
        
        Args:
            state: Optional state filter
            limit: Optional limit on number of jobs returned
            
        Returns:
            List of Job instances
        """
        with self._thread_lock:
            with self._file_lock(self.jobs_file):
                jobs_data = self._read_json_file(self.jobs_file)
                
                jobs = []
                for job_data in jobs_data.values():
                    job = Job.from_dict(job_data)
                    
                    # Apply state filter
                    if state is None or job.state == state:
                        jobs.append(job)
                
                # Sort by priority (descending) then by created_at (ascending)
                jobs.sort(key=lambda j: (-j.priority, j.created_at))
                
                # Apply limit
                if limit is not None:
                    jobs = jobs[:limit]
                
                return jobs
    
    def get_job_counts(self) -> Dict[str, int]:
        """
        Get count of jobs by state.
        
        Returns:
            Dictionary mapping state names to counts
        """
        with self._thread_lock:
            with self._file_lock(self.jobs_file):
                jobs_data = self._read_json_file(self.jobs_file)
                
                counts = {state.value: 0 for state in JobState}
                
                for job_data in jobs_data.values():
                    state = job_data.get('state', JobState.PENDING.value)
                    if state in counts:
                        counts[state] += 1
                
                return counts
    
    def get_next_job(self, worker_id: str) -> Optional[Job]:
        """
        Get next pending job and lock it for processing.
        
        Args:
            worker_id: ID of worker requesting job
            
        Returns:
            Job instance or None if no jobs available
        """
        with self._thread_lock:
            with self._file_lock(self.jobs_file):
                jobs_data = self._read_json_file(self.jobs_file)
                
                # Find highest priority pending job
                pending_jobs = []
                for job_data in jobs_data.values():
                    if job_data.get('state') == JobState.PENDING.value:
                        pending_jobs.append(Job.from_dict(job_data))
                
                if not pending_jobs:
                    return None
                
                # Sort by priority (descending) then by created_at (ascending)
                pending_jobs.sort(key=lambda j: (-j.priority, j.created_at))
                job = pending_jobs[0]
                
                # Lock the job
                if self._lock_job(job.id, worker_id):
                    # Update job state to processing
                    job.update_state(JobState.PROCESSING)
                    # Ensure we serialize the job properly
                    jobs_data[job.id] = job.to_dict()
                    self._write_json_file(self.jobs_file, jobs_data)
                    return job
                
                return None
    
    def _lock_job(self, job_id: str, worker_id: str) -> bool:
        """
        Lock a job for a specific worker.
        
        Args:
            job_id: Job ID to lock
            worker_id: Worker ID acquiring the lock
            
        Returns:
            True if lock acquired, False if already locked
        """
        locks_data = self._read_json_file(self.locks_file)
        
        # Check if already locked
        if job_id in locks_data:
            lock_info = locks_data[job_id]
            # Check if lock is expired (older than 5 minutes)
            lock_time = lock_info.get('timestamp', 0)
            if time.time() - lock_time < 300:  # 5 minutes
                return False
        
        # Acquire lock
        locks_data[job_id] = {
            'worker_id': worker_id,
            'timestamp': time.time()
        }
        self._write_json_file(self.locks_file, locks_data)
        return True
    
    def unlock_job(self, job_id: str, worker_id: str) -> bool:
        """
        Unlock a job.
        
        Args:
            job_id: Job ID to unlock
            worker_id: Worker ID releasing the lock
            
        Returns:
            True if lock released, False if not locked by this worker
        """
        with self._thread_lock:
            with self._file_lock(self.locks_file):
                locks_data = self._read_json_file(self.locks_file)
                
                if job_id not in locks_data:
                    return False
                
                # Verify worker owns the lock
                if locks_data[job_id].get('worker_id') != worker_id:
                    return False
                
                # Release lock
                del locks_data[job_id]
                self._write_json_file(self.locks_file, locks_data)
                return True
    
    def cleanup_expired_locks(self, max_age_seconds: int = 300):
        """
        Clean up expired job locks.
        
        Args:
            max_age_seconds: Maximum age of locks in seconds
        """
        with self._thread_lock:
            with self._file_lock(self.locks_file):
                locks_data = self._read_json_file(self.locks_file)
                
                current_time = time.time()
                expired_locks = []
                
                for job_id, lock_info in locks_data.items():
                    lock_time = lock_info.get('timestamp', 0)
                    if current_time - lock_time > max_age_seconds:
                        expired_locks.append(job_id)
                
                # Remove expired locks
                for job_id in expired_locks:
                    del locks_data[job_id]
                
                if expired_locks:
                    self._write_json_file(self.locks_file, locks_data)
    
    def get_config(self) -> Dict:
        """
        Get configuration settings.
        
        Returns:
            Configuration dictionary
        """
        return self._read_json_file(self.config_file)
    
    def update_config(self, config: Dict):
        """
        Update configuration settings.
        
        Args:
            config: Configuration dictionary
        """
        with self._thread_lock:
            with self._file_lock(self.config_file):
                current_config = self._read_json_file(self.config_file)
                current_config.update(config)
                self._write_json_file(self.config_file, current_config)