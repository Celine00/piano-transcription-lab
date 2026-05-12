from pathlib import Path

from piano_transcription_lab.pipeline import PipelineConfig, PipelineRunner


def test_pipeline_uses_existing_midi_and_runs_downstream_stages(tmp_path):
    input_audio = tmp_path / "song.mp3"
    input_audio.write_bytes(b"audio")
    existing_midi = tmp_path / "fixture.mid"
    existing_midi.write_bytes(b"midi")

    calls = []

    runner = PipelineRunner(
        normalize_audio=lambda source, target, config: calls.append(("normalize", source, target)),
        separate_audio=lambda source, work_dir, config: calls.append(("separate", source, work_dir)) or source,
        transcribe_audio=lambda source, target, config: calls.append(("transcribe", source, target)),
        clean_midi=lambda source, target, config: calls.append(("clean", source, target)) or target.write_bytes(b"clean"),
        export_musicxml=lambda source, target, config: calls.append(("musicxml", source, target)) or target.write_text("<xml />"),
        render_pdf=lambda source, target, config: calls.append(("pdf", source, target)) or target.write_bytes(b"pdf"),
    )

    result = runner.run(
        input_audio,
        PipelineConfig(
            output_prefix=tmp_path / "out" / "song",
            work_dir=tmp_path / "work",
            existing_midi=existing_midi,
        ),
    )

    assert calls == [
        ("clean", existing_midi, tmp_path / "out" / "song.clean.mid"),
        ("musicxml", tmp_path / "out" / "song.clean.mid", tmp_path / "out" / "song.musicxml"),
        ("pdf", tmp_path / "out" / "song.musicxml", tmp_path / "out" / "song.pdf"),
    ]
    assert result.clean_midi == tmp_path / "out" / "song.clean.mid"
    assert result.musicxml == tmp_path / "out" / "song.musicxml"
    assert result.pdf == tmp_path / "out" / "song.pdf"


def test_pipeline_normalizes_and_transcribes_when_no_existing_midi(tmp_path):
    input_audio = tmp_path / "song.mp3"
    input_audio.write_bytes(b"audio")

    calls = []

    runner = PipelineRunner(
        normalize_audio=lambda source, target, config: calls.append(("normalize", source, target)) or target.write_bytes(b"wav"),
        separate_audio=lambda source, work_dir, config: calls.append(("separate", source, work_dir)) or source,
        transcribe_audio=lambda source, target, config: calls.append(("transcribe", source, target)) or target.write_bytes(b"raw"),
        clean_midi=lambda source, target, config: calls.append(("clean", source, target)) or target.write_bytes(b"clean"),
        export_musicxml=lambda source, target, config: calls.append(("musicxml", source, target)) or target.write_text("<xml />"),
        render_pdf=lambda source, target, config: calls.append(("pdf", source, target)) or target.write_bytes(b"pdf"),
    )

    runner.run(
        input_audio,
        PipelineConfig(output_prefix=tmp_path / "out" / "song", work_dir=tmp_path / "work"),
    )

    assert calls == [
        ("normalize", input_audio, tmp_path / "work" / "song.wav"),
        ("transcribe", tmp_path / "work" / "song.wav", tmp_path / "out" / "song.raw.mid"),
        ("clean", tmp_path / "out" / "song.raw.mid", tmp_path / "out" / "song.clean.mid"),
        ("musicxml", tmp_path / "out" / "song.clean.mid", tmp_path / "out" / "song.musicxml"),
        ("pdf", tmp_path / "out" / "song.musicxml", tmp_path / "out" / "song.pdf"),
    ]

