import os
import sys
import subprocess
import shutil
from pathlib import Path

def find_prisma_bin():
    # 1. Prefer current python's Scripts / bin directory (respects active venv or interpreter)
    py_dir = Path(sys.executable).parent
    candidate = py_dir / ("prisma.exe" if sys.platform == "win32" else "prisma")
    if candidate.exists():
        return str(candidate)

    # 2. Check project root venv/.venv folders
    root_dir = Path(__file__).resolve().parent.parent
    for venv_name in ["venv", ".venv"]:
        scripts_dir = root_dir / venv_name / ("Scripts" if sys.platform == "win32" else "bin")
        candidate = scripts_dir / ("prisma.exe" if sys.platform == "win32" else "prisma")
        if candidate.exists():
            return str(candidate)

    # 3. Fall back to system PATH
    prisma_bin = shutil.which("prisma")
    if prisma_bin:
        return prisma_bin

    return None

def main():
    # Try loading .env from current directory or root directory
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=Path(__file__).parent / ".env")
        load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
    except ImportError:
        pass

    # Default to SQLite dev.db if DATABASE_URL is not set
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "file:./dev.db"
        print("DATABASE_URL not set; defaulting to SQLite (file:./dev.db).")

    db_url = os.environ.get("DATABASE_URL", "")

    if db_url.startswith("postgres"):
        schema = "prisma/schema.prod.prisma"
        print("Using PostgreSQL schema.")
    else:
        schema = "prisma/schema.prisma"
        print("Using SQLite schema.")

    # Locate prisma executable
    prisma_bin = find_prisma_bin()
    if not prisma_bin:
        print(
            "Error: Prisma CLI executable not found.\n"
            "Please ensure you installed dependencies with:\n"
            "  pip install prisma\n"
            "Or activate your virtual environment (e.g. .\\venv\\Scripts\\Activate.ps1).",
            file=sys.stderr
        )
        sys.exit(1)

    # Ensure the directory of the found prisma executable is in PATH so
    # Prisma CLI can locate generator binaries like 'prisma-client-py'
    bin_dir = str(Path(prisma_bin).parent)
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

    cmd = [prisma_bin, "migrate", "deploy", "--schema", schema]

    # If run with 'dev', do migrate dev
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        cmd = [prisma_bin, "migrate", "dev", "--schema", schema]
        if len(sys.argv) > 2:
            cmd.extend(sys.argv[2:])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=os.environ)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()

