"""Use the existing capture adapter with the isolated container's PG18 client."""

from pathlib import Path
import subprocess
import sys
from uuid import uuid4


def main():
    args = sys.argv[1:]
    paths = [arg.split("=", 1)[1] for arg in args if arg.startswith("--file=")]
    assert len(paths) == 1
    destination = Path(paths[0]).resolve()
    assert destination.is_relative_to(Path("/srv/bonira/recovery/bundles"))
    assert destination.name == "database.dump" and not destination.exists()
    assert destination.parent.is_dir()
    assert set(arg for arg in args if not arg.startswith("--file=")) == {
        "--format=custom", "--no-password", "--dbname=service=bonira_shared"}
    scratch = "/tmp/bonira-capture-" + uuid4().hex + ".dump"
    mapped = ["--file=" + scratch if arg.startswith("--file=") else arg for arg in args]
    try:
        result = subprocess.run([
            "docker", "exec", "-e", "PGSERVICEFILE=/tmp/bonira-service.conf", "bonira-db",
            "sh", "-c", 'umask 077; exec pg_dump "$@"', "capture", *mapped,
        ], check=False)
        if result.returncode:
            return result.returncode
        return subprocess.run(["docker", "cp", "bonira-db:" + scratch, str(destination)], check=False).returncode
    finally:
        # Only the uniquely named scratch file created above, never a tree.
        subprocess.run(["docker", "exec", "bonira-db", "rm", "-f", scratch], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
