"""
Job model for QueueCTL system
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


class JobState(Enum):
    """Job state enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


@dataclass
class Job:
    """
    Job model representing a background task in the queue system.
    
    Attributes:
        id: Unique job identifier
        command: Shell command to execute
        state: Current job state
        attempts: Number of execution attempts
        max_retries: Maximum number of retry attempts
        created_at: Job creation timestamp
        updated_at: Last update timestamp
        output: Job execution output (stdout/stderr)
        error: Error message if job failed
        timeout: Job execution timeout in seconds
        priority: Job priority (higher number = higher priority)
    """
    id: str
    command: str
    state: JobState = JobState.PENDING
    attempts: int = 0
    max_retries: int = 3
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    timeout: Optional[int] = None
    priority: int = 0
    
    def __post_init__(self):
        """Initialize timestamps if not provided"""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    @classmethod
    def create(cls, command: str, job_id: Optional[str] = None, **kwargs) -> 'Job':
        """
        Create a new job with auto-generated ID if not provided.
        
        Args:
            command: Shell command to execute
            job_id: Optional job ID, auto-generated if None
            **kwargs: Additional job parameters
            
        Returns:
            New Job instance
        """
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        return cls(id=job_id, command=command, **kwargs)
    
    def update_state(self, new_state: JobState, error: Optional[str] = None, output: Optional[str] = None):
        """
        Update job state and timestamp.
        
        Args:
            new_state: New job state
            error: Error message if transitioning to failed state
            output: Job output if available
        """
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        
        if error is not None:
            self.error = error
        if output is not None:
            self.output = output
    
    def increment_attempts(self):
        """Increment the number of attempts and update timestamp"""
        self.attempts += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def should_retry(self) -> bool:
        """
        Check if job should be retried based on current attempts and max retries.
        
        Returns:
            True if job should be retried, False otherwise
        """
        return self.attempts < self.max_retries and self.state == JobState.FAILED
    
    def is_terminal_state(self) -> bool:
        """
        Check if job is in a terminal state (completed, dead).
        
        Returns:
            True if job is in terminal state, False otherwise
        """
        return self.state in [JobState.COMPLETED, JobState.DEAD]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert job to dictionary representation.
        
        Returns:
            Job as dictionary
        """
        data = asdict(self)
        data['state'] = self.state.value  # Convert enum to string
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """
        Create job from dictionary representation.
        
        Args:
            data: Job data as dictionary
            
        Returns:
            Job instance
        """
        # Convert state string to enum
        if 'state' in data and isinstance(data['state'], str):
            data['state'] = JobState(data['state'])
        
        return cls(**data)
    
    def to_json(self) -> str:
        """
        Convert job to JSON string.
        
        Returns:
            Job as JSON string
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Job':
        """
        Create job from JSON string.
        
        Args:
            json_str: Job data as JSON string
            
        Returns:
            Job instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_retry_delay(self, base_delay: float = 2.0) -> float:
        """
        Calculate retry delay using exponential backoff.
        
        Args:
            base_delay: Base delay in seconds
            
        Returns:
            Delay in seconds for next retry
        """
        return base_delay ** self.attempts
    
    def __str__(self) -> str:
        """String representation of the job"""
        return f"Job(id={self.id}, command='{self.command}', state={self.state.value}, attempts={self.attempts})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the job"""
        return (f"Job(id='{self.id}', command='{self.command}', state={self.state.value}, "
                f"attempts={self.attempts}, max_retries={self.max_retries}, "
                f"created_at='{self.created_at}', updated_at='{self.updated_at}')")


def validate_job_data(data: Dict[str, Any]) -> bool:
    """
    Validate job data dictionary.
    
    Args:
        data: Job data to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['command']  # Only command is required, ID can be auto-generated
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return False
    
    # Validate state if present
    if 'state' in data:
        try:
            JobState(data['state'])
        except ValueError:
            return False
    
    # Validate attempts and max_retries are non-negative integers
    for field in ['attempts', 'max_retries']:
        if field in data:
            if not isinstance(data[field], int) or data[field] < 0:
                return False
    
    return True