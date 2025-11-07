"""
Simple test to debug the serialization issue
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from queuectl.job import Job, JobState
import json

# Test job creation and serialization
job = Job.create("echo test", job_id="test")
print(f"Initial job state: {job.state}")
print(f"State type: {type(job.state)}")

# Test to_dict
job_dict = job.to_dict()
print(f"Job dict state: {job_dict['state']}")
print(f"Dict state type: {type(job_dict['state'])}")

# Test JSON serialization
try:
    job_json = json.dumps(job_dict)
    print("✓ JSON serialization successful")
except Exception as e:
    print(f"✗ JSON serialization failed: {e}")

# Test state update
job.update_state(JobState.PROCESSING)
print(f"Updated state: {job.state}")

job_dict2 = job.to_dict()
print(f"Updated dict state: {job_dict2['state']}")

try:
    job_json2 = json.dumps(job_dict2)
    print("✓ Updated JSON serialization successful")
except Exception as e:
    print(f"✗ Updated JSON serialization failed: {e}")