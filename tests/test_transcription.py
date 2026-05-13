from pathlib import Path
import os
import sys
import types

import pytest

import piano_transcription_lab.transcription as transcription_module
from piano_transcription_lab.pipeline import PipelineConfig
from piano_transcription_lab.transcription import (
    DEFAULT_CHECKPOINT_FILENAME,
    PianoTranscriptionInferenceTranscriber,
    ensure_runtime_caches,
    transcribe_audio,
)


def test_ensure_runtime_caches_sets_repo_local_caches_when_unset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)
    monkeypatch.delenv("NUMBA_CACHE_DIR", raising=False)

    ensure_runtime_caches()

    assert os.environ["MPLCONFIGDIR"] == str(tmp_path / ".cache" / "matplotlib")
    assert os.environ["NUMBA_CACHE_DIR"] == str(tmp_path / ".cache" / "numba")
    assert (tmp_path / ".cache" / "matplotlib").is_dir()
    assert (tmp_path / ".cache" / "numba").is_dir()


def test_ensure_runtime_caches_keep_existing_env(tmp_path, monkeypatch):
    custom_cache = tmp_path / "custom-mpl"
    custom_numba_cache = tmp_path / "custom-numba"
    monkeypatch.setenv("MPLCONFIGDIR", str(custom_cache))
    monkeypatch.setenv("NUMBA_CACHE_DIR", str(custom_numba_cache))

    ensure_runtime_caches()

    assert os.environ["MPLCONFIGDIR"] == str(custom_cache)
    assert os.environ["NUMBA_CACHE_DIR"] == str(custom_numba_cache)
    assert not custom_cache.exists()
    assert not custom_numba_cache.exists()


def test_transcribe_audio_uses_piano_transcription_inference_backend(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(PianoTranscriptionInferenceTranscriber, "_ensure_checkpoint", lambda self, path: None)

    class FakePianoTranscription:
        def __init__(self, device, checkpoint_path):
            calls.append(("init", device, checkpoint_path))

        def transcribe(self, audio, midi_path):
            calls.append(("transcribe", audio, midi_path))
            Path(midi_path).write_bytes(b"midi")
            return {"notes": []}

    def fake_load_audio(path, sr, mono):
        calls.append(("load", path, sr, mono))
        return "audio", sr

    fake_package = types.SimpleNamespace(
        sample_rate=16000,
        load_audio=fake_load_audio,
        PianoTranscription=FakePianoTranscription,
    )
    monkeypatch.setitem(sys.modules, "piano_transcription_inference", fake_package)

    source = tmp_path / "song.wav"
    source.write_bytes(b"wav")
    target = tmp_path / "song.mid"

    transcribe_audio(
        source,
        target,
        PipelineConfig(
            output_prefix=tmp_path / "out" / "song",
            work_dir=tmp_path / "work",
            model="piano-transcription-inference",
            device="cpu",
            checkpoint_path=Path("checkpoint.pth"),
        ),
    )

    assert calls == [
        ("load", str(source), 16000, True),
        ("init", "cpu", "checkpoint.pth"),
        ("transcribe", "audio", str(target)),
    ]
    assert target.read_bytes() == b"midi"


def test_transcribe_audio_reports_missing_piano_transcription_dependency(tmp_path, monkeypatch):
    real_import_module = transcription_module.importlib.import_module

    def fake_import_module(name):
        if name == "piano_transcription_inference":
            raise ImportError(name)
        return real_import_module(name)

    monkeypatch.setattr(transcription_module.importlib, "import_module", fake_import_module)

    source = tmp_path / "song.wav"
    source.write_bytes(b"wav")

    with pytest.raises(RuntimeError, match="piano_transcription_inference is not installed"):
        transcribe_audio(
            source,
            tmp_path / "song.mid",
            PipelineConfig(
                output_prefix=tmp_path / "out" / "song",
                work_dir=tmp_path / "work",
                model="piano-transcription-inference",
            ),
        )


def test_piano_transcription_adapter_falls_back_to_librosa_load(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(PianoTranscriptionInferenceTranscriber, "_ensure_checkpoint", lambda self, path: None)

    class FakePianoTranscription:
        def __init__(self, device, checkpoint_path):
            calls.append(("init", device, checkpoint_path))

        def transcribe(self, audio, midi_path):
            calls.append(("transcribe", audio, midi_path))
            Path(midi_path).write_bytes(b"midi")

    fake_package = types.SimpleNamespace(
        sample_rate=16000,
        PianoTranscription=FakePianoTranscription,
    )
    fake_librosa = types.SimpleNamespace(
        load=lambda path, sr, mono: calls.append(("librosa", path, sr, mono)) or ("audio", sr)
    )
    monkeypatch.setitem(sys.modules, "piano_transcription_inference", fake_package)
    monkeypatch.setitem(sys.modules, "librosa", fake_librosa)

    source = tmp_path / "song.wav"
    source.write_bytes(b"wav")
    target = tmp_path / "song.mid"

    transcribe_audio(
        source,
        target,
        PipelineConfig(
            output_prefix=tmp_path / "out" / "song",
            work_dir=tmp_path / "work",
            model="piano-transcription-inference",
        ),
    )

    assert calls == [
        ("librosa", str(source), 16000, True),
        ("init", "cpu", str(Path.cwd() / ".cache" / "piano_transcription_inference" / DEFAULT_CHECKPOINT_FILENAME)),
        ("transcribe", "audio", str(target)),
    ]


def test_piano_transcription_adapter_falls_back_when_package_loader_uses_old_librosa_api(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(PianoTranscriptionInferenceTranscriber, "_ensure_checkpoint", lambda self, path: None)

    class FakePianoTranscription:
        def __init__(self, device, checkpoint_path):
            calls.append(("init", device, checkpoint_path))

        def transcribe(self, audio, midi_path):
            calls.append(("transcribe", audio, midi_path))
            Path(midi_path).write_bytes(b"midi")

    def broken_load_audio(path, sr, mono):
        calls.append(("package-load", path, sr, mono))
        raise AttributeError("No librosa.core attribute audio")

    fake_package = types.SimpleNamespace(
        sample_rate=16000,
        load_audio=broken_load_audio,
        PianoTranscription=FakePianoTranscription,
    )
    fake_librosa = types.SimpleNamespace(
        load=lambda path, sr, mono: calls.append(("librosa", path, sr, mono)) or ("audio", sr)
    )
    monkeypatch.setitem(sys.modules, "piano_transcription_inference", fake_package)
    monkeypatch.setitem(sys.modules, "librosa", fake_librosa)

    source = tmp_path / "song.wav"
    source.write_bytes(b"wav")
    target = tmp_path / "song.mid"

    transcribe_audio(
        source,
        target,
        PipelineConfig(
            output_prefix=tmp_path / "out" / "song",
            work_dir=tmp_path / "work",
            model="piano-transcription-inference",
        ),
    )

    assert calls == [
        ("package-load", str(source), 16000, True),
        ("librosa", str(source), 16000, True),
        ("init", "cpu", str(Path.cwd() / ".cache" / "piano_transcription_inference" / DEFAULT_CHECKPOINT_FILENAME)),
        ("transcribe", "audio", str(target)),
    ]


def test_default_checkpoint_path_uses_repo_local_cache(monkeypatch, tmp_path):
    checked_paths = []
    monkeypatch.chdir(tmp_path)

    def fake_ensure_checkpoint(self, path):
        checked_paths.append(path)

    monkeypatch.setattr(PianoTranscriptionInferenceTranscriber, "_ensure_checkpoint", fake_ensure_checkpoint)

    checkpoint_path = PianoTranscriptionInferenceTranscriber()._resolve_checkpoint_path()

    expected = tmp_path / ".cache" / "piano_transcription_inference" / DEFAULT_CHECKPOINT_FILENAME
    assert checkpoint_path == expected
    assert checked_paths == [expected]
