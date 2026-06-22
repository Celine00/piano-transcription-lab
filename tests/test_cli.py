from pathlib import Path
import json

from piano_transcription_lab.cli import build_parser, config_from_args, main


def test_cli_builds_pipeline_config_from_transcribe_args():
    parser = build_parser()

    args = parser.parse_args(
        [
            "transcribe",
            "samples/input/song.mp3",
            "--out",
            "output/song",
            "--work-dir",
            "work/song",
            "--existing-midi",
            "samples/expected/song.mid",
            "--min-duration-ms",
            "80",
            "--min-velocity",
            "12",
            "--quantize-ms",
            "125",
            "--reduction-mode",
            "piano-reduction",
            "--max-notes-per-onset",
            "3",
            "--auto-key",
            "--hand-split-pitch",
            "72",
            "--model",
            "piano-transcription-inference",
            "--device",
            "cpu",
            "--checkpoint-path",
            "checkpoint.pth",
        ]
    )

    input_path, config = config_from_args(args)

    assert input_path == Path("samples/input/song.mp3")
    assert config.output_prefix == Path("output/song")
    assert config.work_dir == Path("work/song")
    assert config.existing_midi == Path("samples/expected/song.mid")
    assert config.cleanup.min_duration_seconds == 0.08
    assert config.cleanup.min_velocity == 12
    assert config.cleanup.quantize_seconds == 0.125
    assert config.cleanup.reduction_mode == "piano-reduction"
    assert config.cleanup.max_notes_per_onset == 3
    assert config.cleanup.auto_key is True
    assert config.hand_split_pitch == 72
    assert config.model == "piano-transcription-inference"
    assert config.device == "cpu"
    assert config.checkpoint_path == Path("checkpoint.pth")


def test_cli_defaults_output_and_work_dirs_to_song_name_folder():
    parser = build_parser()

    args = parser.parse_args(["transcribe", "samples/input/万物生灵片头曲.MP3"])

    input_path, config = config_from_args(args)

    assert input_path == Path("samples/input/万物生灵片头曲.MP3")
    assert config.output_prefix == Path("output/万物生灵片头曲/score")
    assert config.work_dir == Path("work/万物生灵片头曲")


def test_cli_beginner_difficulty_enables_simple_key_and_reduces_note_density():
    parser = build_parser()

    args = parser.parse_args(["transcribe", "samples/input/song.mp3", "--difficulty", "beginner"])

    _input_path, config = config_from_args(args)

    assert config.cleanup.auto_key is True
    assert config.cleanup.reduction_mode == "piano-reduction"
    assert config.cleanup.max_notes_per_onset == 2
    assert config.cleanup.notation_mode == "beginner"
    assert config.cleanup.quantize_seconds == 0.25
    assert config.cleanup.min_duration_seconds == 0.12
    assert config.cleanup.merge_gap_seconds == 0.08


def test_cli_prints_review_and_render_source(monkeypatch, capsys, tmp_path):
    from piano_transcription_lab.pipeline import PipelineResult
    import piano_transcription_lab.cli as cli

    class StubRunner:
        def run(self, input_audio, config):
            return PipelineResult(
                raw_midi=None,
                clean_midi=tmp_path / "song.clean.mid",
                musicxml=tmp_path / "song.musicxml",
                pdf=tmp_path / "song.pdf",
                review=tmp_path / "song.review.json",
                render_source="midi_fallback",
            )

    monkeypatch.setattr(cli, "PipelineRunner", StubRunner)

    assert main(["transcribe", "samples/input/song.mp3", "--out", str(tmp_path / "song")]) == 0

    output = capsys.readouterr().out
    assert f"review={tmp_path / 'song.review.json'}" in output
    assert "render_source=midi_fallback" in output


def test_cli_prints_review_score_decision_and_issues(monkeypatch, capsys, tmp_path):
    from piano_transcription_lab.pipeline import PipelineResult
    import piano_transcription_lab.cli as cli

    review = tmp_path / "song.review.json"
    review.write_text(
        json.dumps(
            {
                "score": 45,
                "decision": "reject",
                "issues": ["notation_density_too_high", "notation_complexity_too_high"],
            }
        )
    )

    class StubRunner:
        def run(self, input_audio, config):
            return PipelineResult(
                raw_midi=None,
                clean_midi=tmp_path / "song.clean.mid",
                musicxml=tmp_path / "song.musicxml",
                pdf=tmp_path / "song.pdf",
                review=review,
                render_source="musicxml",
            )

    monkeypatch.setattr(cli, "PipelineRunner", StubRunner)

    assert main(["transcribe", "samples/input/song.mp3", "--out", str(tmp_path / "song")]) == 0

    output = capsys.readouterr().out
    assert "score=45" in output
    assert "decision=reject" in output
    assert "issues=notation_density_too_high,notation_complexity_too_high" in output
