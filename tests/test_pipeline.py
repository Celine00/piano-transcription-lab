from pathlib import Path
import subprocess

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
    assert result.review == tmp_path / "out" / "song.review.json"
    assert result.render_source == "musicxml"


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


def test_pipeline_falls_back_to_rendering_pdf_from_midi_when_musicxml_render_fails(tmp_path):
    input_audio = tmp_path / "song.mp3"
    input_audio.write_bytes(b"audio")
    existing_midi = tmp_path / "fixture.mid"
    existing_midi.write_bytes(b"midi")

    calls = []

    def render_pdf(source, target, config):
        calls.append(("pdf", source, target))
        if source.suffix == ".musicxml":
            raise subprocess.CalledProcessError(returncode=40, cmd=["mscore"])
        target.write_bytes(b"pdf")

    def export_musicxml(source, target, config):
        calls.append(("musicxml", source, target))
        target.write_text("<xml />")
        target.with_suffix(".hands.mid").write_bytes(b"hands")

    runner = PipelineRunner(
        normalize_audio=lambda source, target, config: None,
        separate_audio=lambda source, work_dir, config: source,
        transcribe_audio=lambda source, target, config: None,
        clean_midi=lambda source, target, config: calls.append(("clean", source, target)) or target.write_bytes(b"clean"),
        export_musicxml=export_musicxml,
        render_pdf=render_pdf,
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
        ("pdf", tmp_path / "out" / "song.hands.mid", tmp_path / "out" / "song.pdf"),
    ]
    assert result.pdf == tmp_path / "out" / "song.pdf"
    assert result.pdf.read_bytes() == b"pdf"
    assert result.render_source == "midi_fallback"


def test_pipeline_writes_review_report_with_render_source(tmp_path):
    input_audio = tmp_path / "song.mp3"
    input_audio.write_bytes(b"audio")
    existing_midi = tmp_path / "fixture.mid"
    existing_midi.write_bytes(b"midi")

    def write_review(
        clean_midi,
        target,
        config,
        *,
        audio_duration_seconds,
        render_source,
        musicxml_path,
    ):
        target.write_text(f"{render_source}:{audio_duration_seconds}:{musicxml_path.name}")

    runner = PipelineRunner(
        normalize_audio=lambda source, target, config: None,
        separate_audio=lambda source, work_dir, config: source,
        transcribe_audio=lambda source, target, config: None,
        clean_midi=lambda source, target, config: target.write_bytes(b"clean"),
        export_musicxml=lambda source, target, config: target.write_text("<xml />"),
        render_pdf=lambda source, target, config: target.write_bytes(b"pdf"),
        review_score=write_review,
    )

    result = runner.run(
        input_audio,
        PipelineConfig(
            output_prefix=tmp_path / "out" / "song",
            work_dir=tmp_path / "work",
            existing_midi=existing_midi,
        ),
    )

    assert result.review == tmp_path / "out" / "song.review.json"
    assert result.review.read_text() == "musicxml:None:song.musicxml"
