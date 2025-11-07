"""
Basic functionality tests for QueueCTL

Tests job creation, storage, and basic queue operations.
"""

import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))

from queuectl.job import Job, JobState
from queuectl.storage import JobStorage
from queuectl.config import Config


class TestBasicFunctionality(unittest.TestCase):
    """Test basic job queue functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = JobStorage(self.temp_dir)
        self.config = Config(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_job_creation(self):
        """Test job creation and serialization"""
        job = Job.create("echo 'hello world'", job_id="test-job-1")
        
        self.assertEqual(job.id, "test-job-1")
        self.assertEqual(job.command, "echo 'hello world'")
        self.assertEqual(job.state, JobState.PENDING)
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.max_retries, 3)
        self.assertIsNotNone(job.created_at)
        self.assertIsNotNone(job.updated_at)
    
    def test_job_serialization(self):
        """Test job JSON serialization/deserialization"""
        original_job = Job.create("echo 'test'", job_id="serialization-test")
        
        # Test to_dict and from_dict
        job_dict = original_job.to_dict()
        restored_job = Job.from_dict(job_dict)
        
        self.assertEqual(original_job.id, restored_job.id)
        self.assertEqual(original_job.command, restored_job.command)
        self.assertEqual(original_job.state, restored_job.state)
        
        # Test to_json and from_json
        job_json = original_job.to_json()
        restored_from_json = Job.from_json(job_json)
        
        self.assertEqual(original_job.id, restored_from_json.id)
        self.assertEqual(original_job.command, restored_from_json.command)
    
    def test_job_state_transitions(self):
        """Test job state transitions"""
        job = Job.create("echo 'test'")
        
        # Test state update
        job.update_state(JobState.PROCESSING)
        self.assertEqual(job.state, JobState.PROCESSING)
        
        # Test failure with retry
        job.update_state(JobState.FAILED, error="Test error")
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.error, "Test error")
        self.assertTrue(job.should_retry())
        
        # Test attempts increment
        job.increment_attempts()
        self.assertEqual(job.attempts, 1)
        
        # Test completion
        job.update_state(JobState.COMPLETED, output="Test output")
        self.assertEqual(job.state, JobState.COMPLETED)
        self.assertEqual(job.output, "Test output")
        self.assertTrue(job.is_terminal_state())
    
    def test_storage_operations(self):
        """Test storage add/get/update/delete operations"""
        job = Job.create("echo 'storage test'", job_id="storage-test")
        
        # Test add
        self.assertTrue(self.storage.add_job(job))
        
        # Test duplicate add
        self.assertFalse(self.storage.add_job(job))
        
        # Test get
        retrieved_job = self.storage.get_job("storage-test")
        self.assertIsNotNone(retrieved_job)
        self.assertEqual(retrieved_job.id, job.id)
        self.assertEqual(retrieved_job.command, job.command)
        
        # Test update
        job.update_state(JobState.COMPLETED)
        self.assertTrue(self.storage.update_job(job))
        
        # Verify update
        updated_job = self.storage.get_job("storage-test")
        self.assertEqual(updated_job.state, JobState.COMPLETED)
        
        # Test delete
        self.assertTrue(self.storage.delete_job("storage-test"))
        
        # Verify deletion
        deleted_job = self.storage.get_job("storage-test")
        self.assertIsNone(deleted_job)
    
    def test_job_listing(self):
        """Test job listing and filtering"""
        # Create test jobs
        jobs = [
            Job.create("echo 'job1'", job_id="job1"),
            Job.create("echo 'job2'", job_id="job2"),
            Job.create("echo 'job3'", job_id="job3")
        ]
        
        # Add jobs with different states
        jobs[0].update_state(JobState.PENDING)
        jobs[1].update_state(JobState.COMPLETED)
        jobs[2].update_state(JobState.FAILED)
        
        for job in jobs:
            self.storage.add_job(job)
        
        # Test list all jobs
        all_jobs = self.storage.list_jobs()
        self.assertEqual(len(all_jobs), 3)
        
        # Test filter by state
        pending_jobs = self.storage.list_jobs(state=JobState.PENDING)
        self.assertEqual(len(pending_jobs), 1)
        self.assertEqual(pending_jobs[0].id, "job1")
        
        completed_jobs = self.storage.list_jobs(state=JobState.COMPLETED)
        self.assertEqual(len(completed_jobs), 1)
        self.assertEqual(completed_jobs[0].id, "job2")
        
        # Test limit
        limited_jobs = self.storage.list_jobs(limit=2)
        self.assertEqual(len(limited_jobs), 2)
    
    def test_job_counts(self):
        """Test job count statistics"""
        # Initially empty
        counts = self.storage.get_job_counts()
        self.assertEqual(counts['pending'], 0)
        
        # Add jobs
        jobs = [
            Job.create("echo 'pending'", job_id="pending-job"),
            Job.create("echo 'completed'", job_id="completed-job"),
            Job.create("echo 'failed'", job_id="failed-job")
        ]
        
        jobs[1].update_state(JobState.COMPLETED)
        jobs[2].update_state(JobState.FAILED)
        
        for job in jobs:
            self.storage.add_job(job)
        
        # Check counts
        counts = self.storage.get_job_counts()
        self.assertEqual(counts['pending'], 1)
        self.assertEqual(counts['completed'], 1)
        self.assertEqual(counts['failed'], 1)
    
    def test_next_job_retrieval(self):
        """Test getting next job for worker"""
        # Add test jobs
        job1 = Job.create("echo 'first'", job_id="first")
        job2 = Job.create("echo 'second'", job_id="second")
        job2.priority = 10  # Higher priority
        
        self.storage.add_job(job1)
        self.storage.add_job(job2)
        
        # Get next job (should be higher priority)
        next_job = self.storage.get_next_job("worker-1")
        self.assertIsNotNone(next_job)
        self.assertEqual(next_job.id, "second")  # Higher priority
        self.assertEqual(next_job.state, JobState.PROCESSING)
        
        # Should not get the same job again
        next_job2 = self.storage.get_next_job("worker-2")
        self.assertIsNotNone(next_job2)
        self.assertEqual(next_job2.id, "first")
        
        # No more jobs
        next_job3 = self.storage.get_next_job("worker-3")
        self.assertIsNone(next_job3)
    
    def test_retry_logic(self):
        """Test job retry logic"""
        job = Job.create("echo 'test'", max_retries=2)
        
        # Initially should retry
        self.assertTrue(job.should_retry())
        
        # After first failure
        job.update_state(JobState.FAILED)
        job.increment_attempts()
        self.assertTrue(job.should_retry())
        
        # After second failure
        job.increment_attempts()
        self.assertTrue(job.should_retry())
        
        # After third failure (exceeded max_retries)
        job.increment_attempts()
        self.assertFalse(job.should_retry())
        
        # Test exponential backoff
        delays = []
        for i in range(3):
            job.attempts = i
            delays.append(job.get_retry_delay(2.0))
        
        self.assertEqual(delays, [1.0, 2.0, 4.0])  # 2^0, 2^1, 2^2


if __name__ == '__main__':
    unittest.main()