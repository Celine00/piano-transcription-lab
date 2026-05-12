from pathlib import Path

from piano_transcription_lab.audio import build_ffmpeg_command


def test_build_ffmpeg_command_normalizes_to_wav():
    command = build_ffmpeg_command(
        input_path=Path("song.mp3"),
        output_path=Path("work/song.wav"),
        sample_rate=44100,
        channels=2,
    )

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "song.mp3",
        "-ar",
        "44100",
        "-ac",
        "2",
        "work/song.wav",
    ]

