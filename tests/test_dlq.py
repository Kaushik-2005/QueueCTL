"""
Dead Letter Queue tests for QueueCTL

Tests DLQ functionality, retry mechanisms, and failure analysis.
"""

import tempfile
import unittest
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))

from queuectl.job import Job, JobState
from queuectl.storage import JobStorage
from queuectl.dlq import DeadLetterQueue


class TestDeadLetterQueue(unittest.TestCase):
    """Test Dead Letter Queue functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = JobStorage(self.temp_dir)
        self.dlq = DeadLetterQueue(self.storage)
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_list_dead_jobs(self):
        """Test listing dead jobs"""
        # Initially empty
        dead_jobs = self.dlq.list_dead_jobs()
        self.assertEqual(len(dead_jobs), 0)
        
        # Add some jobs with different states
        jobs = [
            Job.create("echo 'dead1'", job_id="dead1"),
            Job.create("echo 'dead2'", job_id="dead2"),
            Job.create("echo 'alive'", job_id="alive")
        ]
        
        jobs[0].update_state(JobState.DEAD)
        jobs[1].update_state(JobState.DEAD)
        jobs[2].update_state(JobState.COMPLETED)
        
        for job in jobs:
            self.storage.add_job(job)
        
        # Should only return dead jobs
        dead_jobs = self.dlq.list_dead_jobs()
        self.assertEqual(len(dead_jobs), 2)
        
        dead_ids = {job.id for job in dead_jobs}
        self.assertEqual(dead_ids, {"dead1", "dead2"})
    
    def test_get_dead_job(self):
        """Test getting specific dead job"""
        # Add a dead job
        job = Job.create("echo 'test'", job_id="dead-job")
        job.update_state(JobState.DEAD)
        self.storage.add_job(job)
        
        # Add a live job
        live_job = Job.create("echo 'live'", job_id="live-job")
        self.storage.add_job(live_job)
        
        # Should get dead job
        retrieved = self.dlq.get_dead_job("dead-job")
        self.assertIsNotNone(retrieved)
        if retrieved:
            self.assertEqual(retrieved.id, "dead-job")
        
        # Should not get live job
        not_dead = self.dlq.get_dead_job("live-job")
        self.assertIsNone(not_dead)
        
        # Should not get non-existent job
        not_exists = self.dlq.get_dead_job("not-exists")
        self.assertIsNone(not_exists)
    
    def test_retry_job(self):
        """Test retrying individual dead job"""
        # Create a dead job
        job = Job.create("echo 'retry test'", job_id="retry-job")
        job.update_state(JobState.DEAD, error="Test error")
        job.attempts = 3
        self.storage.add_job(job)
        
        # Retry the job
        success = self.dlq.retry_job("retry-job", reset_attempts=True)
        self.assertTrue(success)
        
        # Verify job is back to pending
        retrieved = self.storage.get_job("retry-job")
        self.assertIsNotNone(retrieved)
        if retrieved:
            self.assertEqual(retrieved.state, JobState.PENDING)
            self.assertEqual(retrieved.attempts, 0)  # Should be reset
            self.assertIsNone(retrieved.error)  # Error should be cleared
        
        # Try to retry non-existent job
        no_retry = self.dlq.retry_job("not-exists")
        self.assertFalse(no_retry)
    
    def test_retry_job_keep_attempts(self):
        """Test retrying job while keeping attempt count"""
        job = Job.create("echo 'retry keep'", job_id="retry-keep")
        job.update_state(JobState.DEAD)
        job.attempts = 2
        self.storage.add_job(job)
        
        # Retry without resetting attempts
        success = self.dlq.retry_job("retry-keep", reset_attempts=False)
        self.assertTrue(success)
        
        # Verify attempts preserved
        retrieved = self.storage.get_job("retry-keep")
        self.assertEqual(retrieved.attempts, 2)
        self.assertEqual(retrieved.state, JobState.PENDING)
    
    def test_retry_all_jobs(self):
        """Test retrying all dead jobs"""
        # Create multiple dead jobs
        dead_jobs = [
            Job.create("echo 'dead1'", job_id="dead1"),
            Job.create("echo 'dead2'", job_id="dead2"),
            Job.create("echo 'dead3'", job_id="dead3")
        ]
        
        for job in dead_jobs:
            job.update_state(JobState.DEAD)
            job.attempts = 3
            self.storage.add_job(job)
        
        # Add a live job (should not be affected)
        live_job = Job.create("echo 'live'", job_id="live")
        self.storage.add_job(live_job)
        
        # Retry all dead jobs
        results = self.dlq.retry_all_jobs(reset_attempts=True)
        
        # Should have 3 successful retries
        self.assertEqual(len(results), 3)
        self.assertTrue(all(results.values()))
        
        # Verify all jobs are back to pending
        for job_id in ["dead1", "dead2", "dead3"]:
            job = self.storage.get_job(job_id)
            self.assertEqual(job.state, JobState.PENDING)
            self.assertEqual(job.attempts, 0)
        
        # Live job should be unchanged
        live_job = self.storage.get_job("live")
        self.assertEqual(live_job.state, JobState.PENDING)
    
    def test_remove_job(self):
        """Test removing job from DLQ"""
        # Add dead job
        job = Job.create("echo 'remove me'", job_id="remove-job")
        job.update_state(JobState.DEAD)
        self.storage.add_job(job)
        
        # Remove job
        success = self.dlq.remove_job("remove-job")
        self.assertTrue(success)
        
        # Verify job is completely gone
        retrieved = self.storage.get_job("remove-job")
        self.assertIsNone(retrieved)
        
        # Try to remove non-existent job
        no_remove = self.dlq.remove_job("not-exists")
        self.assertFalse(no_remove)
    
    def test_clear_all(self):
        """Test clearing all jobs from DLQ"""
        # Add multiple dead jobs
        for i in range(3):
            job = Job.create(f"echo 'job{i}'", job_id=f"job{i}")
            job.update_state(JobState.DEAD)
            self.storage.add_job(job)
        
        # Add live job
        live_job = Job.create("echo 'live'", job_id="live")
        self.storage.add_job(live_job)
        
        # Clear all dead jobs
        results = self.dlq.clear_all()
        self.assertEqual(len(results), 3)
        self.assertTrue(all(results.values()))
        
        # Verify dead jobs are gone
        dead_jobs = self.dlq.list_dead_jobs()
        self.assertEqual(len(dead_jobs), 0)
        
        # Live job should remain
        live_job = self.storage.get_job("live")
        self.assertIsNotNone(live_job)
    
    def test_dlq_statistics(self):
        """Test DLQ statistics"""
        # Empty DLQ
        stats = self.dlq.get_statistics()
        self.assertEqual(stats['total_jobs'], 0)
        
        # Add dead jobs with different errors
        jobs = [
            Job.create("echo 'job1'", job_id="job1"),
            Job.create("echo 'job2'", job_id="job2"),
            Job.create("echo 'job3'", job_id="job3")
        ]
        
        jobs[0].update_state(JobState.DEAD, error="Command not found")
        jobs[0].attempts = 2
        
        jobs[1].update_state(JobState.DEAD, error="Permission denied")
        jobs[1].attempts = 3
        
        jobs[2].update_state(JobState.DEAD, error="Command not found")
        jobs[2].attempts = 1
        
        for job in jobs:
            self.storage.add_job(job)
        
        # Check statistics
        stats = self.dlq.get_statistics()
        self.assertEqual(stats['total_jobs'], 3)
        self.assertEqual(stats['average_attempts'], 2.0)  # (2+3+1)/3
        
        # Check common errors
        self.assertIn("Command not found", stats['common_errors'])
        self.assertEqual(stats['common_errors']["Command not found"], 2)
        
        # Check oldest/newest jobs
        self.assertIsNotNone(stats['oldest_job'])
        self.assertIsNotNone(stats['newest_job'])
    
    def test_failure_analysis(self):
        """Test job failure analysis"""
        # Create job with specific error
        job = Job.create("nonexistent-command", job_id="analyze-job")
        job.update_state(JobState.DEAD, error="command not found: nonexistent-command")
        job.attempts = 3
        self.storage.add_job(job)
        
        # Analyze failure
        analysis = self.dlq.analyze_job_failure("analyze-job")
        self.assertIsNotNone(analysis)
        
        self.assertEqual(analysis['job_id'], "analyze-job")
        self.assertEqual(analysis['total_attempts'], 3)
        self.assertIn('error_analysis', analysis)
        self.assertIn('suggestions', analysis)
        
        # Check error analysis
        error_analysis = analysis['error_analysis']
        self.assertEqual(error_analysis['error_type'], 'command_not_found')
        self.assertFalse(error_analysis['is_retryable'])
        
        # Should have suggestions
        suggestions = analysis['suggestions']
        self.assertGreater(len(suggestions), 0)
        
        # Test non-existent job
        no_analysis = self.dlq.analyze_job_failure("not-exists")
        self.assertIsNone(no_analysis)
    
    def test_error_pattern_recognition(self):
        """Test error pattern recognition"""
        test_cases = [
            ("command not found: test", "command_not_found", False),
            ("permission denied", "permission_denied", False),
            ("connection refused", "connection_error", True),
            ("timed out after 30 seconds", "timeout", True),
            ("out of memory", "memory_error", True),
            ("unknown error message", "unknown", False)
        ]
        
        for error_msg, expected_type, expected_retryable in test_cases:
            analysis = self.dlq._analyze_error(error_msg)
            self.assertEqual(analysis['error_type'], expected_type, 
                           f"Failed for error: {error_msg}")
            self.assertEqual(analysis['is_retryable'], expected_retryable,
                           f"Wrong retryable status for: {error_msg}")


if __name__ == '__main__':
    unittest.main()