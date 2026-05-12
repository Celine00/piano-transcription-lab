from pathlib import Path

from piano_transcription_lab.cli import build_parser, config_from_args


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
    assert config.model == "piano-transcription-inference"
    assert config.device == "cpu"
    assert config.checkpoint_path == Path("checkpoint.pth")
