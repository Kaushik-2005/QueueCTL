"""
Simple validation tests for QueueCTL

Basic tests to validate the core functionality works.
"""

import os
import tempfile
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from queuectl.job import Job, JobState
from queuectl.storage import JobStorage
from queuectl.config import Config
from queuectl.dlq import DeadLetterQueue


def test_job_creation():
    """Test basic job creation"""
    print("Testing job creation...")
    
    job = Job.create("echo 'hello world'", job_id="test-job")
    assert job.id == "test-job"
    assert job.command == "echo 'hello world'"
    assert job.state == JobState.PENDING
    assert job.attempts == 0
    
    print("✓ Job creation test passed")


def test_storage_operations():
    """Test storage operations"""
    print("Testing storage operations...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        storage = JobStorage(temp_dir)
        
        # Test add
        job = Job.create("echo 'test'", job_id="storage-test")
        assert storage.add_job(job) == True
        
        # Test get
        retrieved = storage.get_job("storage-test")
        assert retrieved is not None
        assert retrieved.id == "storage-test"
        
        # Test update
        job.update_state(JobState.COMPLETED)
        assert storage.update_job(job) == True
        
        # Test list
        jobs = storage.list_jobs()
        assert len(jobs) == 1
        
        print("✓ Storage operations test passed")
        
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_job_state_transitions():
    """Test job state transitions"""
    print("Testing job state transitions...")
    
    job = Job.create("echo 'test'")
    
    # Test pending -> processing
    job.update_state(JobState.PROCESSING)
    assert job.state == JobState.PROCESSING
    
    # Test processing -> completed
    job.update_state(JobState.COMPLETED, output="Success")
    assert job.state == JobState.COMPLETED
    assert job.output == "Success"
    
    # Test retry logic
    retry_job = Job.create("echo 'retry'", max_retries=2)
    retry_job.update_state(JobState.FAILED)
    retry_job.increment_attempts()
    
    assert retry_job.should_retry() == True
    assert retry_job.attempts == 1
    
    print("✓ Job state transitions test passed")


def test_dlq_basic():
    """Test basic DLQ functionality"""
    print("Testing DLQ basic functionality...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        storage = JobStorage(temp_dir)
        dlq = DeadLetterQueue(storage)
        
        # Add dead job
        job = Job.create("echo 'dead'", job_id="dead-job")
        job.update_state(JobState.DEAD)
        storage.add_job(job)
        
        # List dead jobs
        dead_jobs = dlq.list_dead_jobs()
        assert len(dead_jobs) == 1
        assert dead_jobs[0].id == "dead-job"
        
        # Retry job
        success = dlq.retry_job("dead-job")
        assert success == True
        
        # Verify job is pending again
        retrieved = storage.get_job("dead-job")
        assert retrieved is not None
        assert retrieved.state == JobState.PENDING
        
        print("✓ DLQ basic test passed")
        
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_config():
    """Test configuration"""
    print("Testing configuration...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        config = Config(temp_dir)
        
        # Test default values
        assert config.get('max_retries') == 3
        assert config.get('backoff_base') == 2.0
        
        # Test set
        assert config.set('max_retries', 5) == True
        assert config.get('max_retries') == 5
        
        # Test validation
        assert config.set('max_retries', -1) == False  # Invalid
        
        print("✓ Configuration test passed")
        
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_command_execution():
    """Test actual command execution"""
    print("Testing command execution...")
    
    try:
        # Simple echo command
        result = subprocess.run(
            "echo hello",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0
        assert "hello" in result.stdout
        
        print("✓ Command execution test passed")
        
    except Exception as e:
        print(f"✗ Command execution test failed: {e}")
        return False
    
    return True


def run_all_tests():
    """Run all validation tests"""
    print("Running QueueCTL validation tests...\n")
    
    tests = [
        test_job_creation,
        test_storage_operations,
        test_job_state_transitions,
        test_dlq_basic,
        test_config,
        test_command_execution
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__} failed: {e}")
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! QueueCTL is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)