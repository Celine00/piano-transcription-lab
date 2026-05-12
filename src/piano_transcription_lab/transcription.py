from __future__ import annotations

from pathlib import Path
import importlib
import shutil


def transcribe_audio(source: Path, target: Path, config) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if config.existing_midi:
        shutil.copyfile(config.existing_midi, target)
        return
    if config.transcriber_command:
        _run_template_command(config.transcriber_command, source, target)
        return
    if config.model == "piano-transcription-inference":
        PianoTranscriptionInferenceTranscriber(
            device=config.device,
            checkpoint_path=config.checkpoint_path,
        ).transcribe(source, target)
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


class PianoTranscriptionInferenceTranscriber:
    def __init__(self, device: str = "cpu", checkpoint_path: Path | None = None) -> None:
        self.device = device
        self.checkpoint_path = checkpoint_path

    def transcribe(self, audio_path: Path, midi_path: Path) -> None:
        package = self._load_package()
        sample_rate = package.sample_rate
        loaded_audio = self._load_audio(package, audio_path, sample_rate)
        audio = loaded_audio[0] if isinstance(loaded_audio, tuple) else loaded_audio
        checkpoint = str(self.checkpoint_path) if self.checkpoint_path else None
        transcriber = package.PianoTranscription(device=self.device, checkpoint_path=checkpoint)
        transcriber.transcribe(audio, str(midi_path))

    @staticmethod
    def _load_package():
        try:
            return importlib.import_module("piano_transcription_inference")
        except ImportError as exc:
            raise RuntimeError(
                "piano_transcription_inference is not installed, or one of its import-time "
                "dependencies is missing. Install it before using --model "
                "piano-transcription-inference, or pass --transcriber-command."
            ) from exc

    @staticmethod
    def _load_audio(package, audio_path: Path, sample_rate: int):
        if hasattr(package, "load_audio"):
            return package.load_audio(str(audio_path), sr=sample_rate, mono=True)

        try:
            librosa = importlib.import_module("librosa")
        except ImportError as exc:
            raise RuntimeError(
                "librosa is required to load audio for this piano_transcription_inference "
                "version. Install the piano runtime extras."
            ) from exc
        return librosa.load(str(audio_path), sr=sample_rate, mono=True)
