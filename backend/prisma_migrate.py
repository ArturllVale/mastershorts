import os
import sys
import subprocess

def main():
    db_url = os.environ.get("DATABASE_URL", "")

    if db_url.startswith("postgres"):
        schema = "prisma/schema.prod.prisma"
        print("Using PostgreSQL schema.")
    else:
        schema = "prisma/schema.prisma"
        print("Using SQLite schema.")

    cmd = ["prisma", "migrate", "deploy", "--schema", schema]

    # If run with 'dev', do migrate dev
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        cmd = ["prisma", "migrate", "dev", "--schema", schema]
        if len(sys.argv) > 2:
            cmd.extend(sys.argv[2:])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
