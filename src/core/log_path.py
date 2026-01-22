import os
from pathlib import Path

def resolve_log_file_path() -> str:
    """
    Dynamic log path resolver:
    - If LOG_FILE_PATH env exists -> use it
    - Else -> auto use <project_root>/logs/app.log
    Works for both Docker + local.
    """
    env_path = os.getenv("LOG_FILE_PATH")
    if env_path:
        return env_path

    # ✅ project root = folder containing src/
    current = Path(__file__).resolve()
    project_root = current

    while project_root.name != "src" and project_root.parent != project_root:
        project_root = project_root.parent

    # if found src folder, go 1 level up
    if project_root.name == "src":
        project_root = project_root.parent

    return str(project_root / "logs" / "app.log")
