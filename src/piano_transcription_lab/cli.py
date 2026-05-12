from __future__ import annotations

import argparse
from pathlib import Path

from piano_transcription_lab.midi_cleanup import CleanupConfig
from piano_transcription_lab.pipeline import PipelineConfig, PipelineRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="piano-transcribe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe = subparsers.add_parser("transcribe", help="Transcribe one piano-focused audio file.")
    transcribe.add_argument("input_audio", type=Path)
    transcribe.add_argument("--out", type=Path, default=Path("output/transcription"))
    transcribe.add_argument("--work-dir", type=Path, default=Path("work"))
    transcribe.add_argument("--existing-midi", type=Path)
    transcribe.add_argument("--separate", action="store_true")
    transcribe.add_argument("--sample-rate", type=int, default=44100)
    transcribe.add_argument("--channels", type=int, default=2)
    transcribe.add_argument("--ffmpeg", default="ffmpeg")
    transcribe.add_argument("--musescore", default="mscore")
    transcribe.add_argument(
        "--transcriber-command",
        help="Command template for audio-to-MIDI. Use {audio} and {midi} placeholders.",
    )
    transcribe.add_argument(
        "--model",
        choices=["piano-transcription-inference", "command"],
        default="piano-transcription-inference",
        help="Audio-to-MIDI backend to use.",
    )
    transcribe.add_argument("--device", default="cpu", help="Device for model inference, usually cpu or cuda.")
    transcribe.add_argument("--checkpoint-path", type=Path, help="Optional model checkpoint path.")
    transcribe.add_argument("--min-duration-ms", type=float, default=60)
    transcribe.add_argument("--min-velocity", type=int, default=10)
    transcribe.add_argument("--quantize-ms", type=float, default=125)
    transcribe.add_argument("--merge-gap-ms", type=float, default=25)

    return parser


def config_from_args(args: argparse.Namespace) -> tuple[Path, PipelineConfig]:
    cleanup = CleanupConfig(
        min_duration_seconds=args.min_duration_ms / 1000,
        min_velocity=args.min_velocity,
        quantize_seconds=args.quantize_ms / 1000 if args.quantize_ms else None,
        merge_gap_seconds=args.merge_gap_ms / 1000,
    )
    return args.input_audio, PipelineConfig(
        output_prefix=args.out,
        work_dir=args.work_dir,
        existing_midi=args.existing_midi,
        cleanup=cleanup,
        separate=args.separate,
        sample_rate=args.sample_rate,
        channels=args.channels,
        ffmpeg=args.ffmpeg,
        musescore=args.musescore,
        model=args.model,
        device=args.device,
        checkpoint_path=args.checkpoint_path,
        transcriber_command=args.transcriber_command,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "transcribe":
        input_path, config = config_from_args(args)
        result = PipelineRunner().run(input_path, config)
        print(f"clean_midi={result.clean_midi}")
        print(f"musicxml={result.musicxml}")
        print(f"pdf={result.pdf}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
