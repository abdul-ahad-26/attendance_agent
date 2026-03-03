"""Register the attendance agent as a Windows Task Scheduler task.

This creates a scheduled task that runs the agent on user login,
so it starts automatically without manual intervention.

Usage:
    python scripts/install_task.py          # Install the task
    python scripts/install_task.py --remove # Remove the task
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


TASK_NAME = "TeamsAttendanceAgent"


def get_python_path() -> str:
    """Get the path to the current Python interpreter."""
    return sys.executable


def get_project_dir() -> str:
    """Get the project root directory."""
    return str(Path(__file__).resolve().parent.parent)


def install_task():
    """Create a Windows Task Scheduler task to run the agent on login."""
    python = get_python_path()
    project_dir = get_project_dir()

    # Build the schtasks command
    # /SC ONLOGON = run when user logs in
    # /RL HIGHEST = run with highest privileges (optional, helps with browser)
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{python}" -m src.main',
        "/SC", "ONLOGON",
        "/F",  # Force overwrite if exists
        "/RL", "HIGHEST",
    ]

    print(f"Creating scheduled task: {TASK_NAME}")
    print(f"  Python: {python}")
    print(f"  Working dir: {project_dir}")
    print()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME}' created successfully!")
            print("The agent will start automatically when you log in to Windows.")
            print()
            print("To verify: Open Task Scheduler and look for", TASK_NAME)
            print(f"To remove: python scripts/install_task.py --remove")
        else:
            print(f"Failed to create task. Error:\n{result.stderr}")
            if "Access is denied" in result.stderr:
                print("\nTry running this script as Administrator.")
    except FileNotFoundError:
        print("Error: 'schtasks' not found. This script only works on Windows.")
        sys.exit(1)


def remove_task():
    """Remove the scheduled task."""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME}' removed successfully.")
        else:
            print(f"Failed to remove task. Error:\n{result.stderr}")
    except FileNotFoundError:
        print("Error: 'schtasks' not found. This script only works on Windows.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Install/remove Windows Task Scheduler auto-start")
    parser.add_argument("--remove", action="store_true", help="Remove the scheduled task")
    args = parser.parse_args()

    if os.name != "nt":
        print("Warning: This script is designed for Windows. It may not work on this OS.")

    if args.remove:
        remove_task()
    else:
        install_task()


if __name__ == "__main__":
    main()
