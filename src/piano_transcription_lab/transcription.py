from pathlib import Path
import shutil


def transcribe_audio(source: Path, target: Path, config) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if config.existing_midi:
        shutil.copyfile(config.existing_midi, target)
        return
    if config.transcriber_command:
        _run_template_command(config.transcriber_command, source, target)
        return
    raise RuntimeError(
        "No transcription backend configured. Install a model adapter or pass "
        "--transcriber-command with {audio} and {midi} placeholders."
    )


def _run_template_command(template: str, audio_path: Path, midi_path: Path) -> None:
    import shlex
    import subprocess

    command = template.format(audio=str(audio_path), midi=str(midi_path))
    subprocess.run(shlex.split(command), check=True)

