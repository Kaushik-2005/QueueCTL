# QueueCTL - CLI Background Job Queue System

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A production-quality CLI-based background job queue system that supports multiple workers, retry logic with exponential backoff, and dead letter queue management.

## 🚀 Features

- **Job Queue Management**: Enqueue, process, and monitor background jobs
- **Multi-Worker Support**: Run multiple worker processes concurrently
- **Retry Logic**: Exponential backoff for failed jobs with configurable retry limits
- **Dead Letter Queue (DLQ)**: Manage permanently failed jobs with retry and analysis capabilities
- **Persistent Storage**: JSON-based storage that survives system restarts
- **CLI Interface**: Rich command-line interface with colored output and tables
- **Configuration Management**: Configurable system parameters
- **Job Locking**: Prevents race conditions between workers
- **Graceful Shutdown**: Workers finish current jobs before stopping

## � Screenshots & Results

For visual demonstrations of QueueCTL in action, check out the `images/` folder which contains screenshots showing:

- Job listing and status displays
- Worker management commands
- Dead Letter Queue functionality
- System configuration and validation tests
- Complete CLI command examples

See [QueueCTL_Results.md](QueueCTL_Results.md) for a comprehensive overview with embedded screenshots.

## �📦 Installation & Setup

### Prerequisites

- Python 3.8 or higher
- Git (for cloning the repository)

### Step 1: Clone the Repository

```bash
git clone https://github.com/Kaushik-2005/QueueCTL.git
cd QueueCTL
```

### Step 2: Install the Package

```bash
# Install QueueCTL and its dependencies
pip install -e .
```

This will install QueueCTL as a package and make the `queuectl` command available globally.

### Step 3: Verify Installation

```bash
# Test the CLI interface
queuectl --help

# Run validation tests (recommended)
python tests/test_validation.py

# Run demo to see all features
python demo.py
```

**Expected output**: You should see the CLI help text and all tests should pass.

## 📝 Job File Templates

QueueCTL includes several JSON templates to get you started:

- **`simple_job.json`** - Basic job with just a command
- **`job_template.json`** - Full example with all options
- **`python_job.json`** - Example Python script execution
- **`test_job.json`** - Simple test example

**Template Structure:**
```json
{
  "id": "unique-job-id",           // Optional: Auto-generated if not provided
  "command": "echo Hello World",   // Required: Command to execute
  "max_retries": 3,               // Optional: Number of retry attempts (default: 3)
  "timeout": 30,                  // Optional: Execution timeout in seconds (default: 300)
  "priority": 5                   // Optional: Job priority, higher = processed first (default: 0)
}
```

## 🎯 Quick Start

### 1. Enqueue Your First Job

**Option 1: Using JSON Files (Recommended for Windows)**
```bash
# Create a simple job file
echo '{"command": "echo Hello World"}' > my_job.json

# Enqueue the job using the file
queuectl enqueue my_job.json
# or
queuectl enqueue --file my_job.json
# or
queuectl enqueue -f my_job.json
```

**Option 2: Direct JSON (Linux/Mac/WSL)**
```bash
# Simple job
queuectl enqueue '{"command": "echo Hello World"}'

# Job with custom settings
queuectl enqueue '{"id": "my-job-1", "command": "sleep 5", "max_retries": 5, "timeout": 30}'
```

**Option 3: PowerShell JSON (Advanced)**
```powershell
# For PowerShell users who prefer inline JSON (requires careful escaping)
queuectl enqueue "{`"command`": `"echo Hello World`"}"
```

### 2. Start Workers

```bash
# Start a single worker
queuectl worker start

# Start multiple workers
queuectl worker start --count 3
```

### 3. Monitor Status

```bash
# Overall system status
queuectl status

# List jobs
queuectl list

# List only pending jobs
queuectl list --state pending
```

### 4. Manage Dead Letter Queue

```bash
# List failed jobs
queuectl dlq list

# Retry a specific job
queuectl dlq retry job-id-here

# Retry all dead jobs
queuectl dlq retry
```

## 📖 Usage Guide

### Job Management

#### Enqueue Jobs

**Method 1: Using JSON Files (Recommended)**
```bash
# Create a job file (easiest method, avoids shell escaping issues)
echo '{"command": "python script.py"}' > job.json
queuectl enqueue job.json

# Using template files
queuectl enqueue job_template.json
queuectl enqueue --file my_job.json
queuectl enqueue -f custom_job.json

# Example job file contents:
# {
#   "id": "data-processing-job",
#   "command": "python process_data.py --input data.csv",
#   "max_retries": 3,
#   "timeout": 600,
#   "priority": 10
# }
```

**Method 2: Direct JSON String**
```bash
# Basic job (Linux/Mac/WSL)
queuectl enqueue '{"command": "python script.py"}'

# Validate job without enqueuing
queuectl enqueue --validate '{"command": "echo test"}'
```

**Method 3: PowerShell JSON (Windows)**
```powershell
# Use backtick escaping for JSON in PowerShell
queuectl enqueue "{`"command`": `"echo test`"}"
```

#### List and Monitor Jobs

```bash
# List all jobs
queuectl list

# Filter by state
queuectl list --state pending
queuectl list --state completed
queuectl list --state failed
# Limit results
queuectl list --limit 10

# Detailed view
queuectl list --verbose
```

### Worker Management

#### Start Workers

```bash
# Start single worker in background
queuectl worker start

# Start multiple workers
queuectl worker start --count 5

# Start worker in foreground (for debugging)
queuectl worker start --no-detach
```

#### Stop Workers

```bash
# Graceful shutdown (wait for current jobs)
queuectl worker stop

# Force stop
queuectl worker stop --force

# Custom timeout
queuectl worker stop --timeout 60
```

#### Monitor Workers

```bash
# Worker status
queuectl worker status

# Overall system status
queuectl status

# Force stop
queuectl worker stop --force

# Custom timeout
queuectl worker stop --timeout 60
```

### Dead Letter Queue (DLQ)

#### List Dead Jobs

```bash
# List all dead jobs
queuectl dlq list

# Detailed view with error analysis
queuectl dlq list --verbose

# Show statistics
queuectl dlq stats
```

#### Retry Failed Jobs

```bash
# Retry specific job
queuectl dlq retry job-id-here

# Retry all dead jobs
queuectl dlq retry

# Retry without resetting attempt count
queuectl dlq retry job-id-here --keep-attempts
```

#### Remove Dead Jobs

```bash
# Remove specific job
queuectl dlq remove job-id-here

# Remove all dead jobs (with confirmation)
queuectl dlq remove

# Skip confirmation
queuectl dlq remove --yes

```

### Configuration

#### View Configuration

```bash
# Show all settings
queuectl config show
```

#### Update Settings

```bash
# Set retry limit
queuectl config set max_retries 5

# Set backoff multiplier
queuectl config set backoff_base 3.0

# Set worker timeout
queuectl config set worker_timeout 600
```

#### Reset Configuration

```bash
# Reset to defaults
queuectl config reset --yes
```

## 🏗️ Architecture Overview

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Interface │    │  Job Storage    │    │   Worker Pool   │
│                 │    │                 │    │                 │
│ • Commands      │◄──►│ • JSON Files    │◄──►│ • Multiprocess  │
│ • Validation    │    │ • File Locking  │    │ • Job Execution │
│ • Display       │    │ • Atomic Ops    │    │ • Retry Logic   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Configuration  │
                    │                 │
                    │ • Settings      │
                    │ • Defaults      │
                    │ • Validation    │
                    └─────────────────┘
```

### Data Flow

1. **Job Submission**: Jobs are submitted via CLI and stored in JSON files
2. **Worker Polling**: Workers poll for pending jobs with priority ordering
3. **Job Execution**: Workers execute jobs with timeout and error handling
4. **Retry Logic**: Failed jobs are retried with exponential backoff
5. **DLQ Management**: Jobs exceeding retry limits move to Dead Letter Queue

### Storage Structure

```
~/.queuectl/
├── jobs.json          # All job data
├── locks.json         # Job locks for workers
├── config.json        # System configuration
└── workers.pid        # Running worker PIDs
```

### Job Lifecycle

```
┌─────────┐    ┌─────────────┐    ┌───────────┐    ┌─────────────┐
│ PENDING │───►│ PROCESSING  │───►│ COMPLETED │    │    DEAD     │
└─────────┘    └─────────────┘    └───────────┘    └─────────────┘
     ▲              │                                      ▲
     │              ▼                                      │
     │         ┌─────────┐                                 │
     └─────────│ FAILED  │─────────────────────────────────┘
               └─────────┘     (max retries exceeded)
```

## ⚙️ Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `max_retries` | 3 | Maximum retry attempts per job |
| `backoff_base` | 2.0 | Exponential backoff multiplier |
| `worker_timeout` | 300 | Job execution timeout (seconds) |
| `cleanup_completed_after_hours` | 24 | Auto-cleanup completed jobs |
| `job_lock_timeout` | 300 | Job lock expiration (seconds) |
| `max_workers` | 10 | Maximum concurrent workers |

## 🧪 Testing

### Prerequisites
Make sure you have completed the installation steps with `pip install -e .`.

### Run Validation Tests

```bash
# Run all validation tests (recommended first step)
python tests/test_validation.py

# Run comprehensive demo showing all features
python demo.py

# Run specific test modules
python tests/test_basic.py
python tests/test_dlq.py
```

### Manual Testing Scenarios

#### Test Basic Functionality

```bash
# Method 1: Using JSON files (recommended)
echo '{"command": "echo Testing QueueCTL"}' > test_job.json
queuectl enqueue test_job.json

# Method 2: Direct JSON (Linux/Mac)
queuectl enqueue '{"command": "echo Testing QueueCTL"}'

# 2. Start a worker
queuectl worker start

# 3. Check status
queuectl status

# 4. List completed jobs
queuectl list --state completed
```

#### Test Retry Logic

```bash
# 1. Enqueue a failing job
queuectl enqueue '{"command": "nonexistent-command", "max_retries": 2}'

# 2. Start worker
queuectl worker start

# 3. Watch job fail and retry
queuectl list --state failed

# 4. Check DLQ after max retries
queuectl dlq list
```

#### Test Multi-Worker

```bash
# 1. Enqueue multiple jobs
for i in {1..5}; do
  queuectl enqueue "{\"command\": \"sleep $i\"}"
done

# 2. Start multiple workers
queuectl worker start --count 3

# 3. Watch parallel processing
queuectl status
```

### Expected Test Results

- ✅ Jobs are created and stored successfully
- ✅ Workers can process jobs concurrently
- ✅ Failed jobs retry with exponential backoff
- ✅ Jobs exceeding retry limits move to DLQ
- ✅ Data persists across restarts
- ✅ Job locking prevents race conditions
- ✅ Graceful shutdown preserves running jobs

## 🐛 Troubleshooting

### Common Issues

#### Workers Not Starting

```bash
# Check if workers are already running
queuectl worker status

# Stop existing workers and restart
queuectl worker stop
queuectl worker start
```

#### Jobs Stuck in Processing

```bash
# Check for stale locks
queuectl status

# Restart workers to clear stale locks
queuectl worker stop
queuectl worker start
```

#### Storage Issues

```bash
# Check storage directory
ls -la ~/.queuectl/

# Reset storage (WARNING: deletes all jobs)
rm -rf ~/.queuectl/
```

#### Installation Issues

If you encounter import errors after installation:

1. **Ensure the package is properly installed:**
   ```bash
   pip list | grep queuectl
   # Should show: queuectl 1.0.0
   ```

2. **Reinstall if necessary:**
   ```bash
   pip uninstall queuectl
   pip install -e .
   ```

3. **Verify the command is available:**
   ```bash
   queuectl --help
   ```

### Debug Mode

```bash
# Enable verbose output
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
import sys
sys.path.insert(0, '.')
from cli.main import main
main()
" status
```

## 🚧 Design Decisions & Trade-offs

### Storage Choice: JSON vs Database

**Decision**: JSON files with file locking
**Reasoning**:
- ✅ Zero dependencies (no database setup)
- ✅ Human-readable storage
- ✅ Simple backup/restore
- ❌ Limited scalability vs. database
- ❌ File locking complexity

### Worker Architecture: Multiprocessing vs Threading

**Decision**: Multiprocessing
**Reasoning**:
- ✅ True parallelism for CPU-bound jobs
- ✅ Process isolation (crash safety)
- ✅ Better resource control
- ❌ Higher memory overhead
- ❌ IPC complexity

### CLI Framework: Typer vs Click vs Argparse

**Decision**: Typer with Rich
**Reasoning**:
- ✅ Modern API with type hints
- ✅ Rich output formatting
- ✅ Automatic help generation
- ❌ Additional dependency

## 🎛️ Advanced Usage

### Custom Job Processing

```python
# Custom job with Python code
queuectl enqueue '{
  "command": "python -c \"import time; print(\\\"Processing...\\\"); time.sleep(2); print(\\\"Done!\\\")\"",
  "timeout": 10
}'
```

### Batch Operations

```bash
# Enqueue multiple jobs from file
cat jobs.txt | while read cmd; do
  queuectl enqueue "{\"command\": \"$cmd\"}"
done

# Bulk retry all DLQ jobs
queuectl dlq retry
```

### Monitoring & Analytics

```bash
# Job statistics
queuectl dlq stats

# System overview
queuectl status

# Export job data
cat ~/.queuectl/jobs.json | jq '.[] | select(.state == "completed")'
```

## 🔮 Future Enhancements

### Planned Features

- [ ] Job scheduling (run_at timestamps)
- [ ] Job dependencies and workflows
- [ ] Web dashboard interface
- [ ] Metrics and monitoring
- [ ] Job output logging
- [ ] Priority queues
- [ ] Job templates
- [ ] Webhook notifications

### Performance Improvements

- [ ] SQLite storage backend option
- [ ] Worker pool optimization
- [ ] Batch job processing
- [ ] Memory usage optimization

## 🤝 Contributing

### Development Setup

```bash
# Clone and setup
git clone https://github.com/Kaushik-2005/QueueCTL.git
cd QueueCTL

# Install in development mode
pip install -e .

# Run tests
python tests/test_validation.py
```

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to functions
- Write tests for new features

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Kaushik-2005/QueueCTL/issues)
- **Documentation**: This README
- **Email**: queuectl@example.com

---

**QueueCTL** - Making background job processing simple and reliable! 🚀