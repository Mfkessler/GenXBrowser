# =============================================================================
# Gunicorn Configuration for H5AD Backend
# =============================================================================
# Optimized for H5AD file serving with in-memory caching
# 
# KEY INSIGHT: For small user counts (<10), use 1 worker with multiple threads.
# This ensures ALL threads share the SAME in-memory cache, so h5ad files are
# loaded only ONCE and reused across all requests.
#
# With multiple sync workers, each worker has its own Python process and cache,
# causing every worker to load all h5ad files independently = slow startup + 
# high memory usage!
# =============================================================================

import os
import multiprocessing

# =============================================================================
# Server Socket
# =============================================================================
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
backlog = 256  # Reduced for low-traffic use case

# =============================================================================
# Worker Processes
# =============================================================================
# SINGLE WORKER with MULTIPLE THREADS:
# - All threads share the same process memory = shared h5ad cache!
# - 8 threads can handle 5+ concurrent users easily
# - Much faster startup (load data once, not per-worker)
# - Lower memory footprint (~2GB instead of 4-8GB)
#
# For higher load (>20 users), consider using multiple workers with an
# external cache (Redis) or accept the memory tradeoff.
workers = int(os.getenv("GUNICORN_WORKERS", 1))  # Single worker!
worker_class = "gthread"  # Threaded worker - shares memory between threads
threads = int(os.getenv("GUNICORN_THREADS", 8))  # 8 threads for parallelism

# =============================================================================
# Worker Lifecycle
# =============================================================================
max_requests = 0  # Disable worker restart - keeps cache warm!
max_requests_jitter = 0
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))  # 2 minutes should be enough
graceful_timeout = 30
keepalive = 5

# =============================================================================
# Server Mechanics
# =============================================================================
# preload_app is not needed with single worker, but harmless
preload_app = False  # Disabled - single worker loads on first request
daemon = False
user = None
group = None
tmp_upload_dir = None

# =============================================================================
# Logging
# =============================================================================
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# =============================================================================
# Process Naming
# =============================================================================
proc_name = "h5ad-backend"

# =============================================================================
# Hooks
# =============================================================================
def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def worker_int(worker):
    """Called when a worker received SIGINT or SIGQUIT."""
    worker.log.info("Worker received SIGINT/SIGQUIT")

def worker_abort(worker):
    """Called when a worker received SIGABRT."""
    worker.log.info("Worker received SIGABRT")
