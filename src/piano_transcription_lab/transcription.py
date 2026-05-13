from __future__ import annotations

from pathlib import Path
import importlib
import os
import shutil
import urllib.request


DEFAULT_CHECKPOINT_FILENAME = "note_F1=0.9677_pedal_F1=0.9186.pth"
DEFAULT_CHECKPOINT_MIN_BYTES = 160_000_000
DEFAULT_CHECKPOINT_URL = (
    "https://zenodo.org/record/4034264/files/"
    "CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1"
)


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
        checkpoint = str(self._resolve_checkpoint_path())
        transcriber = package.PianoTranscription(device=self.device, checkpoint_path=checkpoint)
        transcriber.transcribe(audio, str(midi_path))

    def _resolve_checkpoint_path(self) -> Path:
        checkpoint_path = self.checkpoint_path or (
            Path.cwd() / ".cache" / "piano_transcription_inference" / DEFAULT_CHECKPOINT_FILENAME
        )
        self._ensure_checkpoint(checkpoint_path)
        return checkpoint_path

    def _ensure_checkpoint(self, checkpoint_path: Path) -> None:
        if checkpoint_path.exists() and checkpoint_path.stat().st_size >= DEFAULT_CHECKPOINT_MIN_BYTES:
            return

        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".part")
        print(f"Downloading piano transcription checkpoint to {checkpoint_path}")
        urllib.request.urlretrieve(DEFAULT_CHECKPOINT_URL, temp_path)
        temp_path.replace(checkpoint_path)

    @staticmethod
    def _load_package():
        ensure_runtime_caches()
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
            try:
                return package.load_audio(str(audio_path), sr=sample_rate, mono=True)
            except AttributeError as exc:
                if "librosa.core" not in str(exc):
                    raise

        return PianoTranscriptionInferenceTranscriber._load_audio_with_librosa(audio_path, sample_rate)

    @staticmethod
    def _load_audio_with_librosa(audio_path: Path, sample_rate: int):
        ensure_runtime_caches()
        try:
            librosa = importlib.import_module("librosa")
        except ImportError as exc:
            raise RuntimeError(
                "librosa is required to load audio for this piano_transcription_inference "
                "version. Install the piano runtime extras."
            ) from exc
        return librosa.load(str(audio_path), sr=sample_rate, mono=True)


def ensure_runtime_caches(cache_root: Path | None = None) -> None:
    resolved_cache_root = cache_root or Path.cwd() / ".cache"
    _ensure_env_cache_dir("MPLCONFIGDIR", resolved_cache_root / "matplotlib")
    _ensure_env_cache_dir("NUMBA_CACHE_DIR", resolved_cache_root / "numba")


def _ensure_env_cache_dir(env_name: str, cache_dir: Path) -> None:
    if os.environ.get(env_name):
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ[env_name] = str(cache_dir)
