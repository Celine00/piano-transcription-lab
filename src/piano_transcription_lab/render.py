from pathlib import Path
import subprocess


def render_pdf(source: Path, target: Path, config) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [config.musescore, "-o", str(target), str(source)]
    subprocess.run(command, check=True)

