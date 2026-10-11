import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def find_python():
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable

def main():
    env_file = ROOT / ".env"
    example_env = ROOT / ".env.example"
    if not env_file.exists() and example_env.exists():
        shutil.copy(example_env, env_file)

    python_bin = find_python()
    port = os.environ.get("BACKEND_PORT", "8000")

    print(f"Starting backend on http://localhost:{port}...")
    backend_proc = subprocess.Popen(
        [
            python_bin,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--port",
            port,
        ],
        cwd=str(ROOT),
    )

    npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
    frontend_dir = ROOT / "frontend"

    print("Starting frontend on http://localhost:5173...")
    frontend_proc = subprocess.Popen(
        [npm_bin, "run", "dev"],
        cwd=str(frontend_dir),
    )

    time.sleep(2)
    webbrowser.open("http://localhost:5173")
    print("\nSelf-Improving RAG is running!")
    print("Frontend: http://localhost:5173")
    print(f"Backend API: http://localhost:{port}")
    print("Press Ctrl+C to stop both servers.\n")

    try:
        while True:
            if backend_proc.poll() is not None:
                print(f"Backend stopped unexpectedly with exit code {backend_proc.returncode}")
                break
            if frontend_proc.poll() is not None:
                print(f"Frontend stopped unexpectedly with exit code {frontend_proc.returncode}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down servers...")
    finally:
        for proc in (frontend_proc, backend_proc):
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in (frontend_proc, backend_proc):
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("Done.")

if __name__ == "__main__":
    main()
