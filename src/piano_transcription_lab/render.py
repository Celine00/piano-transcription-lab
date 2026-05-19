from pathlib import Path
import subprocess


def render_pdf(source: Path, target: Path, config, run_command=subprocess.run) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [config.musescore, "-o", str(target), str(source)]
    try:
        run_command(command, check=True)
    except subprocess.CalledProcessError:
        if _looks_like_pdf(target):
            return
        raise


def _looks_like_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            return file.read(5) == b"%PDF-"
    except OSError:
        return False
