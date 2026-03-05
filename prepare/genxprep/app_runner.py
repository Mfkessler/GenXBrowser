"""App Runner – Local development server launcher without Docker.

Provides functionality to:
- Validate that GenXPrep build outputs exist
- Set up backend Python virtual environment
- Set up frontend Node.js dependencies
- Generate local Vite configuration pointing to localhost
- Start both backend and frontend services in parallel
- Handle clean shutdown on Ctrl+C
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from genxprep.config import ProjectConfig
from genxprep.reporter import Reporter, ValidationResult


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _find_project_root() -> Path | None:
    """Find the GenXBrowser project root by searching for backend/frontend directories.
    
    Searches upward from the current working directory for a directory containing
    both 'backend' and 'frontend' subdirectories.
    
    Returns:
        Path to project root, or None if not found
    """
    # Start from current working directory
    current = Path.cwd().resolve()
    
    # Search upward through parent directories
    for path in [current] + list(current.parents):
        backend = path / "backend"
        frontend = path / "frontend"
        
        # Check if both backend and frontend exist
        if backend.is_dir() and frontend.is_dir():
            # Verify it looks like GenXBrowser by checking for key files
            if (backend / "run.py").exists() and (frontend / "vite.config.ts").exists():
                return path
    
    # Fallback: try relative to the installed package location
    # (for development with editable install)
    installed_path = Path(__file__).resolve().parent.parent.parent
    backend = installed_path / "backend"
    frontend = installed_path / "frontend"
    if backend.is_dir() and frontend.is_dir():
        return installed_path
    
    return None


def _get_project_root() -> Path:
    """Get the GenXBrowser project root directory.
    
    Raises:
        RuntimeError: If project root cannot be found
    """
    root = _find_project_root()
    if root is None:
        raise RuntimeError(
            "Could not find GenXBrowser project root. "
            "Please run this command from within the GenXBrowser directory or one of its subdirectories."
        )
    return root


def _get_backend_dir() -> Path:
    """Get the backend directory."""
    return _get_project_root() / "backend"


def _get_frontend_dir() -> Path:
    """Get the frontend directory."""
    return _get_project_root() / "frontend"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_build_outputs(config: ProjectConfig, reporter: Reporter) -> bool:
    """Validate that build outputs exist and are ready for the backend.
    
    Args:
        config: Loaded GenXPrep configuration
        reporter: Reporter instance for structured output
        
    Returns:
        True if validation passed, False otherwise
    """
    result = ValidationResult("Build Outputs")
    output_dir = config.output_dir
    
    if not output_dir.exists():
        result.error(
            f"Output directory does not exist: {output_dir}",
            suggestion="Run 'genxprep build config.yml' first"
        )
        reporter.add(result)
        reporter.print_summary()
        return False
    
    # Check for at least one H5AD file
    h5ad_files = list(output_dir.glob("*/*.h5ad"))
    if not h5ad_files:
        result.error(
            f"No H5AD files found in {output_dir}",
            suggestion="Run 'genxprep build config.yml' to generate data files"
        )
        reporter.add(result)
        reporter.print_summary()
        return False
    
    result.success(f"Found {len(h5ad_files)} H5AD file(s)")
    
    # Check for config file
    config_file = output_dir / "config" / "project_config.json"
    if config_file.exists():
        result.success(f"Found project configuration")
    else:
        result.warn(
            "Project config file missing (will be auto-generated on backend startup)",
            context=str(config_file)
        )
    
    reporter.add(result)
    return True


# ---------------------------------------------------------------------------
# Environment detection and creation
# ---------------------------------------------------------------------------

def _check_conda_available() -> bool:
    """Check if conda is available."""
    try:
        subprocess.run(
            ["conda", "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _create_conda_env(env_name: str, backend_dir: Path, python_version: str = "3.12") -> tuple[bool, str, Path]:
    """Create a conda environment for the backend.
    
    Returns:
        (success, error_message, python_path)
    """
    try:
        # Create conda environment
        subprocess.run(
            ["conda", "create", "-y", "-n", env_name, f"python={python_version}"],
            check=True,
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # Get conda environment path
        result = subprocess.run(
            ["conda", "info", "--envs"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        
        # Parse conda env list to find our environment's path
        for line in result.stdout.split('\n'):
            if env_name in line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    env_path = Path(parts[-1])
                    python_path = env_path / "bin" / "python"
                    if sys.platform == "win32":
                        python_path = env_path / "python.exe"
                    return True, "", python_path
        
        return False, f"Could not find conda environment path for '{env_name}'", None
        
    except subprocess.CalledProcessError as e:
        return False, f"conda environment creation failed: {e.stderr}", None
    except subprocess.TimeoutExpired:
        return False, "conda environment creation timed out", None


# ---------------------------------------------------------------------------
# Backend setup
# ---------------------------------------------------------------------------

def setup_backend(
    reporter: Reporter,
    skip_setup: bool = False,
    use_system: bool = False
) -> Path | None:
    """Set up backend Python virtual environment and install dependencies.
    
    Args:
        reporter: Reporter instance for structured output
        skip_setup: If True, skip venv creation and dependency installation
        use_system: If True, use system Python (not recommended)
        
    Returns:
        Path to Python executable in venv, or None on failure
    """
    result = ValidationResult("Backend Setup")
    
    try:
        backend_dir = _get_backend_dir()
    except RuntimeError as e:
        result.error(str(e))
        reporter.add(result)
        return None
    
    if not backend_dir.exists():
        result.error(
            f"Backend directory not found: {backend_dir}",
            suggestion="Ensure you're running this command from the GenXBrowser directory or a subdirectory"
        )
        reporter.add(result)
        return None
    
    # Handle system-wide installation (with warning)
    if use_system:
        result.warning(
            "Using system Python installation",
            suggestion="⚠️  Installing packages system-wide. Consider using a virtual environment instead."
        )
        python_executable = Path(sys.executable)
        
        if skip_setup:
            result.info("Skipping dependency installation (--skip-setup)")
            reporter.add(result)
            return python_executable
        
        # Install dependencies with system Python
        result.info(f"Installing dependencies with system Python: {python_executable}")
        requirements_file = backend_dir / "requirements.txt"
        
        if not requirements_file.exists():
            result.error(f"Requirements file not found: {requirements_file}")
            reporter.add(result)
            return None
        
        try:
            subprocess.run(
                [str(python_executable), "-m", "pip", "install", "-r", str(requirements_file)],
                check=True,
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            result.success("Dependencies installed successfully")
            reporter.add(result)
            return python_executable
        except subprocess.CalledProcessError as e:
            result.error(f"Failed to install dependencies: {e.stderr}")
            reporter.add(result)
            return None
        except subprocess.TimeoutExpired:
            result.error("Dependency installation timed out")
            reporter.add(result)
            return None
    
    # Conda environment setup (required for GenXBrowser)
    # Check if conda is available
    if not _check_conda_available():
        result.error(
            "Conda is not available",
            suggestion=(
                "GenXBrowser requires conda for environment management.\n"
                "Install conda from: https://docs.conda.io/en/latest/miniconda.html\n\n"
                "Or use the --system flag to install to system Python (not recommended)."
            )
        )
        reporter.add(result)
        return None
    
    # Conda environment name and python path
    env_name = "genxbrowser-backend"
    
    # Get conda environment path if it exists
    conda_python = None
    try:
        result_info = subprocess.run(
            ["conda", "info", "--envs"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        
        for line in result_info.stdout.split('\n'):
            if env_name in line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    env_path = Path(parts[-1])
                    conda_python = env_path / "bin" / "python"
                    if sys.platform == "win32":
                        conda_python = env_path / "python.exe"
                    break
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    
    if skip_setup:
        if conda_python is None or not conda_python.exists():
            result.error(
                f"Conda environment '{env_name}' does not exist",
                suggestion="Run without --skip-setup first to create the environment"
            )
            reporter.add(result)
            return None
        result.info("Skipping setup (--skip-setup)")
        reporter.add(result)
        return conda_python
    
    # Create conda environment if it doesn't exist
    if conda_python is None or not conda_python.exists():
        result.info(f"Creating conda environment '{env_name}'...")
        reporter.add(result)
        reporter.print_summary()
        
        success, error_msg, conda_python = _create_conda_env(env_name, backend_dir)
        if not success:
            result.error(
                "Failed to create conda environment",
                suggestion=f"{error_msg}\n\nAlternatively, use --system flag (not recommended)."
            )
            reporter.add(result)
            return None
        
        result.success(f"Conda environment '{env_name}' created successfully")
    else:
        result.info(f"Conda environment '{env_name}' already exists")
    
    # Install/update requirements
    requirements_file = backend_dir / "requirements.txt"
    if not requirements_file.exists():
        result.error(f"Requirements file not found: {requirements_file}")
        reporter.add(result)
        return None
    
    result.info("Installing backend dependencies...")
    reporter.add(result)
    reporter.print_summary()
    
    try:
        subprocess.run(
            [str(conda_python), "-m", "pip", "install", "-q", "-r", "requirements.txt"],
            check=True,
            cwd=backend_dir,
            capture_output=True,
            text=True
        )
        result.success("Backend dependencies installed")
    except subprocess.CalledProcessError as e:
        result.error(
            f"Failed to install dependencies: {e.stderr}",
            suggestion="Check requirements.txt for compatibility issues"
        )
        reporter.add(result)
        return None
    
    reporter.add(result)
    return conda_python


# ---------------------------------------------------------------------------
# Frontend setup
# ---------------------------------------------------------------------------

def setup_frontend(
    reporter: Reporter,
    backend_port: int = 5000,
    skip_setup: bool = False
) -> bool:
    """Set up frontend dependencies and create local Vite config.
    
    Args:
        reporter: Reporter instance for structured output
        backend_port: Port where backend will run
        skip_setup: If True, skip npm install
        
    Returns:
        True on success, False on failure
    """
    result = ValidationResult("Frontend Setup")
    
    try:
        frontend_dir = _get_frontend_dir()
    except RuntimeError as e:
        result.error(str(e))
        reporter.add(result)
        return False
    
    if not frontend_dir.exists():
        result.error(
            f"Frontend directory not found: {frontend_dir}",
            suggestion="Ensure you're running this command from the GenXBrowser directory or a subdirectory"
        )
        reporter.add(result)
        return False
    
    # Check package.json exists
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        result.error(f"package.json not found: {package_json}")
        reporter.add(result)
        return False
    
    # Install npm dependencies if needed
    node_modules = frontend_dir / "node_modules"
    
    if not skip_setup:
        if not node_modules.exists():
            result.info("Installing frontend dependencies (this may take a while)...")
        else:
            result.info("Updating frontend dependencies...")
        reporter.add(result)
        reporter.print_summary()
        
        try:
            subprocess.run(
                ["npm", "install"],
                check=True,
                cwd=frontend_dir,
                capture_output=True,
                text=True
            )
            result.success("Frontend dependencies installed")
        except subprocess.CalledProcessError as e:
            result.error(
                f"Failed to install npm dependencies: {e.stderr}",
                suggestion="Ensure Node.js and npm are installed"
            )
            reporter.add(result)
            return False
        except FileNotFoundError:
            result.error(
                "npm command not found",
                suggestion="Install Node.js and npm first"
            )
            reporter.add(result)
            return False
    else:
        if not node_modules.exists():
            result.error(
                "node_modules does not exist",
                suggestion="Run without --skip-setup first to install dependencies"
            )
            reporter.add(result)
            return False
        result.info("Skipping npm install (--skip-setup)")
    
    # Generate vite.config.local.ts
    result.info("Generating local Vite configuration...")
    
    vite_config_local = frontend_dir / "vite.config.local.ts"
    vite_config_content = _generate_vite_config_local(backend_port)
    
    try:
        vite_config_local.write_text(vite_config_content)
        result.success(f"Created vite.config.local.ts (backend: http://localhost:{backend_port})")
    except Exception as e:
        result.error(f"Failed to write vite.config.local.ts: {e}")
        reporter.add(result)
        return False
    
    # Generate .env.local for environment variables
    result.info("Generating .env.local for Vite...")
    
    env_local = frontend_dir / ".env.local"
    env_content = _generate_env_local()
    
    try:
        env_local.write_text(env_content)
        result.success(f"Created .env.local")
    except Exception as e:
        result.error(f"Failed to write .env.local: {e}")
        reporter.add(result)
        return False
    
    reporter.add(result)
    return True


def _generate_vite_config_local(backend_port: int) -> str:
    """Generate content for vite.config.local.ts with localhost backend target."""
    return f'''import {{ fileURLToPath, URL }} from "node:url";

import {{ defineConfig }} from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";
import tailwindcss from "@tailwindcss/vite";

// Local development configuration - generated by genxprep app
// Backend runs on localhost instead of Docker container
const apiBase = process.env.VITE_API_BASE_URL || "";
const backendTarget = "http://localhost:{backend_port}";

function buildProxy() {{
  const routes: Record<string, object> = {{
    "/api": {{ target: backendTarget, changeOrigin: true }},
    "/health": {{ target: backendTarget, changeOrigin: true }},
    "/gene_tree": {{ target: backendTarget, changeOrigin: true }},
  }};
  // When running behind a sub-path, add rewriting proxy entries
  if (apiBase && apiBase !== "/" && apiBase !== "") {{
    const prefix = apiBase.replace(/\\/$/, ""); // strip trailing slash
    routes[`${{prefix}}/api`] = {{
      target: backendTarget,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(new RegExp(`^${{prefix}}`), ""),
    }};
    routes[`${{prefix}}/health`] = {{
      target: backendTarget,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(new RegExp(`^${{prefix}}`), ""),
    }};
    routes[`${{prefix}}/gene_tree`] = {{
      target: backendTarget,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(new RegExp(`^${{prefix}}`), ""),
    }};
  }}
  return routes;
}}

// Parse allowed hosts from environment variable (comma-separated)
function getAllowedHosts(): string[] {{
  const defaultHosts = ["localhost", "127.0.0.1"];
  const envHosts = process.env.VITE_ALLOWED_HOSTS;
  
  if (envHosts) {{
    const additional = envHosts.split(",").map(h => h.trim()).filter(h => h);
    return [...defaultHosts, ...additional];
  }}
  
  return defaultHosts;
}}

// https://vite.dev/config/
export default defineConfig({{
  base: process.env.VITE_BASE_URL || "/",
  plugins: [vue(), vueDevTools(), tailwindcss()],
  server: {{ 
    host: "0.0.0.0",
    allowedHosts: getAllowedHosts(),
    // Proxy API requests to local backend
    proxy: buildProxy(),
    // HMR configuration
    watch: {{
      usePolling: false, // Disable polling for local dev
    }},
    hmr: {{
      overlay: true,
    }},
  }},
  resolve: {{
    alias: {{
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    }},
  }},
  build: {{
    outDir: "dist",
    sourcemap: false,
  }},
}});
''' 


def _generate_env_local() -> str:
    """Generate content for .env.local with development environment variables."""
    return '''# Local development environment variables - generated by genxprep app
# This file configures the frontend for local development without Docker

# API base URL - empty for local dev (uses Vite proxy)
VITE_API_BASE_URL=

# Base URL for the app
VITE_BASE_URL=/

# Data type (Genes or Transcripts)
VITE_DATA_TYPE=Genes
'''


# ---------------------------------------------------------------------------
# Service launcher
# ---------------------------------------------------------------------------

def start_services(
    config: ProjectConfig,
    reporter: Reporter,
    backend_python: Path,
    backend_port: int = 5000,
    frontend_port: int = 5173
) -> int:
    """Start backend and frontend services in parallel.
    
    Args:
        config: Loaded GenXPrep configuration
        reporter: Reporter instance for structured output
        backend_python: Path to Python executable in backend venv
        backend_port: Port for backend Flask server
        frontend_port: Port for frontend Vite dev server
        
    Returns:
        Exit code (0 for clean shutdown, 1 for errors)
    """
    try:
        backend_dir = _get_backend_dir()
        frontend_dir = _get_frontend_dir()
    except RuntimeError as e:
        result = ValidationResult("Service Startup")
        result.error(str(e))
        reporter.add(result)
        reporter.print_all()
        reporter.print_summary()
        return 1
    
    data_dir = config.output_dir.resolve()
    
    # Ensure config directory is writable (profiles, config saves, etc.)
    config_dir = data_dir / "config"
    if config_dir.exists() and not os.access(config_dir, os.W_OK):
        result = ValidationResult("Permissions Check")
        result.error(
            f"Config directory is not writable: {config_dir}",
            suggestion=f"Run: sudo chown -R $USER {config_dir}"
        )
        reporter.add(result)
        reporter.print_summary()
        return 1
    # Ensure profiles directory exists and is writable
    profiles_dir = config_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare backend environment
    backend_env = os.environ.copy()
    backend_env["H5AD_DATA_DIR"] = str(data_dir)
    backend_env["PROJECT_CONFIG_PATH"] = str(data_dir / "config" / "project_config.json")
    backend_env["FILTER_STORE_PATH"] = str(data_dir / "filters")
    backend_env["GO_OBO_PATH"] = str(data_dir / "go-basic.obo")
    backend_env["SEQUENCES_DIR"] = str(data_dir / "Metadata" / "fas")
    backend_env["GENE_TREES_PATH"] = str(data_dir / "Metadata" / "Resolved_Gene_Trees.txt")
    backend_env["FLASK_DEBUG"] = "true"
    backend_env["PORT"] = str(backend_port)
    backend_env["PYTHONUNBUFFERED"] = "1"  # For real-time output
    
    # Start backend
    result = ValidationResult("Service Startup")
    result.info(f"Starting backend on http://localhost:{backend_port}")
    
    try:
        backend_process = subprocess.Popen(
            [str(backend_python), "run.py"],
            cwd=backend_dir,
            env=backend_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
        )
    except Exception as e:
        result.error(f"Failed to start backend: {e}")
        reporter.add(result)
        reporter.print_all()
        reporter.print_summary()
        return 1
    
    # Give backend a moment to start
    time.sleep(2)
    
    # Check if backend is still running
    if backend_process.poll() is not None:
        result.error("Backend process terminated unexpectedly")
        # Print backend output
        if backend_process.stdout:
            output = backend_process.stdout.read()
            result.error(f"Backend output: {output}")
        reporter.add(result)
        reporter.print_all()
        reporter.print_summary()
        return 1
    
    result.success("Backend started")
    
    # Start frontend
    result.info(f"Starting frontend on http://localhost:{frontend_port}")
    
    try:
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--config", "vite.config.local.ts", "--port", str(frontend_port)],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
        )
    except Exception as e:
        result.error(f"Failed to start frontend: {e}")
        backend_process.terminate()
        backend_process.wait()
        reporter.add(result)
        reporter.print_all()
        reporter.print_summary()
        return 1
    
    # Give frontend a moment to start
    time.sleep(2)
    
    # Check if frontend is still running
    if frontend_process.poll() is not None:
        result.error("Frontend process terminated unexpectedly")
        # Print frontend output
        if frontend_process.stdout:
            output = frontend_process.stdout.read()
            result.error(f"Frontend output: {output}")
        backend_process.terminate()
        backend_process.wait()
        reporter.add(result)
        reporter.print_all()
        reporter.print_summary()
        return 1
    
    result.success("Frontend started")
    reporter.add(result)
    reporter.print_summary()
    
    # Print access information
    console = reporter.console
    console.print()
    console.print("=" * 70, style="bold green")
    console.print("  GenXBrowser is running locally!", style="bold green")
    console.print("=" * 70, style="bold green")
    console.print()
    console.print(f"  🌐 Frontend:  http://localhost:{frontend_port}", style="bold cyan")
    console.print(f"  ⚙️  Backend:   http://localhost:{backend_port}", style="bold cyan")
    console.print(f"  📁 Data:      {data_dir}", style="dim")
    console.print()
    console.print("  Press Ctrl+C to stop both services", style="yellow")
    console.print("=" * 70, style="bold green")
    console.print()
    
    # Set up signal handler for clean shutdown
    def signal_handler(signum: int, frame: Any) -> None:
        console.print()
        console.print("Shutting down services...", style="yellow")
        frontend_process.terminate()
        backend_process.terminate()
        
        # Wait for graceful shutdown with timeout
        try:
            frontend_process.wait(timeout=5)
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            console.print("Force killing services...", style="red")
            frontend_process.kill()
            backend_process.kill()
        
        console.print("Services stopped", style="green")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Monitor both processes and print their output
    try:
        while True:
            # Check if either process has died
            backend_status = backend_process.poll()
            frontend_status = frontend_process.poll()
            
            if backend_status is not None:
                console.print(f"\n❌ Backend process exited with code {backend_status}", style="bold red")
                frontend_process.terminate()
                frontend_process.wait()
                return 1
            
            if frontend_status is not None:
                console.print(f"\n❌ Frontend process exited with code {frontend_status}", style="bold red")
                backend_process.terminate()
                backend_process.wait()
                return 1
            
            # Read output from both processes (non-blocking)
            # In a production version, you might want to use select() or threads
            # for better output handling, but this simple approach works for now
            time.sleep(1)
            
    except KeyboardInterrupt:
        # This shouldn't be reached due to signal handler, but just in case
        signal_handler(signal.SIGINT, None)
    
    return 0
