"""
Dead Letter Queue (DLQ) management for QueueCTL

Handles jobs that have permanently failed and provides mechanisms
to retry or remove them.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

from .job import Job, JobState
from .storage import JobStorage

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """
    Dead Letter Queue management for permanently failed jobs.
    
    Features:
    - List dead jobs
    - Retry specific jobs or all dead jobs
    - Remove jobs from DLQ
    - Get DLQ statistics
    """
    
    def __init__(self, storage: JobStorage):
        """
        Initialize DLQ manager.
        
        Args:
            storage: Job storage instance
        """
        self.storage = storage
    
    def list_dead_jobs(self, limit: Optional[int] = None) -> List[Job]:
        """
        List all jobs in the dead letter queue.
        
        Args:
            limit: Optional limit on number of jobs returned
            
        Returns:
            List of dead jobs
        """
        return self.storage.list_jobs(state=JobState.DEAD, limit=limit)
    
    def get_dead_job(self, job_id: str) -> Optional[Job]:
        """
        Get a specific dead job by ID.
        
        Args:
            job_id: Job ID to retrieve
            
        Returns:
            Job instance if found and dead, None otherwise
        """
        job = self.storage.get_job(job_id)
        
        if job and job.state == JobState.DEAD:
            return job
        
        return None
    
    def retry_job(self, job_id: str, reset_attempts: bool = True) -> bool:
        """
        Retry a specific job from the DLQ.
        
        Args:
            job_id: Job ID to retry
            reset_attempts: Whether to reset attempt count
            
        Returns:
            True if job was successfully moved back to pending, False otherwise
        """
        job = self.get_dead_job(job_id)
        
        if not job:
            logger.warning(f"Job {job_id} not found in DLQ")
            return False
        
        # Reset job for retry
        if reset_attempts:
            job.attempts = 0
        
        job.update_state(JobState.PENDING)
        job.error = None  # Clear previous error
        
        # Update job in storage
        success = self.storage.update_job(job)
        
        if success:
            logger.info(f"Job {job_id} moved from DLQ back to pending queue")
        else:
            logger.error(f"Failed to update job {job_id} in storage")
        
        return success
    
    def retry_all_jobs(self, reset_attempts: bool = True) -> Dict[str, bool]:
        """
        Retry all jobs in the DLQ.
        
        Args:
            reset_attempts: Whether to reset attempt counts
            
        Returns:
            Dictionary mapping job IDs to retry success status
        """
        dead_jobs = self.list_dead_jobs()
        results = {}
        
        for job in dead_jobs:
            results[job.id] = self.retry_job(job.id, reset_attempts)
        
        successful_retries = sum(1 for success in results.values() if success)
        logger.info(f"Retried {successful_retries}/{len(dead_jobs)} jobs from DLQ")
        
        return results
    
    def remove_job(self, job_id: str) -> bool:
        """
        Permanently remove a job from the DLQ.
        
        Args:
            job_id: Job ID to remove
            
        Returns:
            True if job was removed, False otherwise
        """
        job = self.get_dead_job(job_id)
        
        if not job:
            logger.warning(f"Job {job_id} not found in DLQ")
            return False
        
        success = self.storage.delete_job(job_id)
        
        if success:
            logger.info(f"Job {job_id} permanently removed from DLQ")
        else:
            logger.error(f"Failed to remove job {job_id} from storage")
        
        return success
    
    def clear_all(self) -> Dict[str, bool]:
        """
        Remove all jobs from the DLQ.
        
        Returns:
            Dictionary mapping job IDs to removal success status
        """
        dead_jobs = self.list_dead_jobs()
        results = {}
        
        for job in dead_jobs:
            results[job.id] = self.remove_job(job.id)
        
        successful_removals = sum(1 for success in results.values() if success)
        logger.info(f"Removed {successful_removals}/{len(dead_jobs)} jobs from DLQ")
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get DLQ statistics.
        
        Returns:
            Dictionary with DLQ statistics
        """
        dead_jobs = self.list_dead_jobs()
        
        if not dead_jobs:
            return {
                'total_jobs': 0,
                'oldest_job': None,
                'newest_job': None,
                'average_attempts': 0,
                'common_errors': {}
            }
        
        # Calculate statistics
        total_jobs = len(dead_jobs)
        total_attempts = sum(job.attempts for job in dead_jobs)
        average_attempts = total_attempts / total_jobs if total_jobs > 0 else 0
        
        # Find oldest and newest jobs
        sorted_by_created = sorted(dead_jobs, key=lambda j: j.created_at or "")
        oldest_job = sorted_by_created[0]
        newest_job = sorted_by_created[-1]
        
        # Count common errors
        error_counts = {}
        for job in dead_jobs:
            if job.error:
                # Get first line of error for grouping
                error_key = job.error.split('\n')[0][:100]  # Limit length
                error_counts[error_key] = error_counts.get(error_key, 0) + 1
        
        # Get top 5 errors
        common_errors = dict(sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        
        return {
            'total_jobs': total_jobs,
            'oldest_job': {
                'id': oldest_job.id,
                'created_at': oldest_job.created_at,
                'command': oldest_job.command
            },
            'newest_job': {
                'id': newest_job.id,
                'created_at': newest_job.created_at,
                'command': newest_job.command
            },
            'average_attempts': round(average_attempts, 2),
            'common_errors': common_errors
        }
    
    def analyze_job_failure(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a specific job failure.
        
        Args:
            job_id: Job ID to analyze
            
        Returns:
            Analysis dictionary or None if job not found
        """
        job = self.get_dead_job(job_id)
        
        if not job:
            return None
        
        # Parse error for common patterns
        error_analysis = self._analyze_error(job.error) if job.error else {}
        
        return {
            'job_id': job.id,
            'command': job.command,
            'total_attempts': job.attempts,
            'max_retries': job.max_retries,
            'created_at': job.created_at,
            'updated_at': job.updated_at,
            'final_error': job.error,
            'error_analysis': error_analysis,
            'suggestions': self._get_failure_suggestions(job)
        }
    
    def _analyze_error(self, error: str) -> Dict[str, Any]:
        """
        Analyze error message for common patterns.
        
        Args:
            error: Error message
            
        Returns:
            Error analysis dictionary
        """
        analysis = {
            'error_type': 'unknown',
            'likely_cause': 'Unknown error',
            'is_retryable': False
        }
        
        error_lower = error.lower()
        
        # Common error patterns
        if 'command not found' in error_lower or 'no such file' in error_lower:
            analysis.update({
                'error_type': 'command_not_found',
                'likely_cause': 'Command or file does not exist',
                'is_retryable': False
            })
        elif 'permission denied' in error_lower:
            analysis.update({
                'error_type': 'permission_denied',
                'likely_cause': 'Insufficient permissions',
                'is_retryable': False
            })
        elif 'timeout' in error_lower or 'timed out' in error_lower:
            analysis.update({
                'error_type': 'timeout',
                'likely_cause': 'Command execution timeout',
                'is_retryable': True
            })
        elif 'connection' in error_lower and ('refused' in error_lower or 'failed' in error_lower):
            analysis.update({
                'error_type': 'connection_error',
                'likely_cause': 'Network or service connectivity issue',
                'is_retryable': True
            })
        elif 'out of memory' in error_lower or 'memory error' in error_lower:
            analysis.update({
                'error_type': 'memory_error',
                'likely_cause': 'Insufficient memory',
                'is_retryable': True
            })
        
        return analysis
    
    def _get_failure_suggestions(self, job: Job) -> List[str]:
        """
        Get suggestions for fixing job failures.
        
        Args:
            job: Failed job
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        if job.error:
            error_analysis = self._analyze_error(job.error)
            error_type = error_analysis.get('error_type', 'unknown')
            
            if error_type == 'command_not_found':
                suggestions.extend([
                    "Check if the command exists and is in PATH",
                    "Verify file paths are correct",
                    "Install missing dependencies"
                ])
            elif error_type == 'permission_denied':
                suggestions.extend([
                    "Check file/directory permissions",
                    "Run with appropriate user privileges",
                    "Verify access to required resources"
                ])
            elif error_type == 'timeout':
                suggestions.extend([
                    f"Increase job timeout (currently {job.timeout or 'default'})",
                    "Optimize command performance",
                    "Check for hanging processes"
                ])
            elif error_type == 'connection_error':
                suggestions.extend([
                    "Check network connectivity",
                    "Verify service availability",
                    "Check firewall settings"
                ])
            elif error_type == 'memory_error':
                suggestions.extend([
                    "Increase available memory",
                    "Optimize command memory usage",
                    "Process data in smaller chunks"
                ])
        
        # General suggestions
        if job.attempts >= job.max_retries:
            suggestions.append(f"Job exceeded max retries ({job.max_retries}), consider increasing max_retries")
        
        suggestions.append("Check command syntax and arguments")
        suggestions.append("Test command manually in same environment")
        
        return suggestions