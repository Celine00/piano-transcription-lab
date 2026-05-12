from pathlib import Path
import subprocess


def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 44100,
    channels: int = 2,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
        str(output_path),
    ]


def normalize_audio(source: Path, target: Path, config) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_command(
        input_path=source,
        output_path=target,
        sample_rate=config.sample_rate,
        channels=config.channels,
        ffmpeg=config.ffmpeg,
    )
    subprocess.run(command, check=True)

