from __future__ import annotations

import argparse
import json
from pathlib import Path

from piano_transcription_lab.midi_cleanup import CleanupConfig
from piano_transcription_lab.pipeline import PipelineConfig, PipelineRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="piano-transcribe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe = subparsers.add_parser("transcribe", help="Transcribe one piano-focused audio file.")
    transcribe.add_argument("input_audio", type=Path)
    transcribe.add_argument("--out", type=Path)
    transcribe.add_argument("--work-dir", type=Path)
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
    transcribe.add_argument(
        "--difficulty",
        choices=["full", "easy", "beginner"],
        default="full",
        help="Apply score simplification presets.",
    )
    transcribe.add_argument(
        "--reduction-mode",
        choices=["full", "melody", "piano-reduction"],
        default="full",
        help="Reduce note density before score export.",
    )
    transcribe.add_argument(
        "--max-notes-per-onset",
        type=int,
        default=4,
        help="Maximum notes to keep per onset in piano-reduction mode.",
    )
    transcribe.add_argument(
        "--auto-key",
        action="store_true",
        help="Transpose the cleaned MIDI to a beginner-friendly nearby key.",
    )
    transcribe.add_argument(
        "--hand-split-pitch",
        type=int,
        help="Fixed MIDI pitch where right hand starts. Defaults to adaptive C4-C5 splitting.",
    )

    return parser


def config_from_args(args: argparse.Namespace) -> tuple[Path, PipelineConfig]:
    output_prefix = args.out or Path("output") / args.input_audio.stem / "score"
    work_dir = args.work_dir or Path("work") / args.input_audio.stem
    reduction_mode = args.reduction_mode
    max_notes_per_onset = args.max_notes_per_onset
    auto_key = args.auto_key
    notation_mode = "full"
    quantize_seconds = args.quantize_ms / 1000 if args.quantize_ms else None
    min_duration_seconds = args.min_duration_ms / 1000
    merge_gap_seconds = args.merge_gap_ms / 1000
    if args.difficulty == "beginner":
        reduction_mode = "piano-reduction"
        max_notes_per_onset = 2
        auto_key = True
        notation_mode = "beginner"
        quantize_seconds = 0.25
        min_duration_seconds = 0.12
        merge_gap_seconds = 0.08
    elif args.difficulty == "easy":
        reduction_mode = "piano-reduction"
        max_notes_per_onset = 3
        auto_key = True
        notation_mode = "beginner"
        quantize_seconds = 0.125
        min_duration_seconds = max(min_duration_seconds, 0.08)
        merge_gap_seconds = max(merge_gap_seconds, 0.05)

    cleanup = CleanupConfig(
        min_duration_seconds=min_duration_seconds,
        min_velocity=args.min_velocity,
        quantize_seconds=quantize_seconds,
        merge_gap_seconds=merge_gap_seconds,
        reduction_mode=reduction_mode,
        max_notes_per_onset=max_notes_per_onset,
        auto_key=auto_key,
        notation_mode=notation_mode,
    )
    return args.input_audio, PipelineConfig(
        output_prefix=output_prefix,
        work_dir=work_dir,
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
        hand_split_pitch=args.hand_split_pitch,
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
        print(f"review={result.review}")
        _print_review_summary(result.review)
        print(f"render_source={result.render_source}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _print_review_summary(review_path: Path) -> None:
    try:
        report = json.loads(review_path.read_text())
    except (OSError, json.JSONDecodeError):
        return

    if "score" in report:
        print(f"score={report['score']}")
    if "decision" in report:
        print(f"decision={report['decision']}")
    issues = report.get("issues")
    if issues:
        print(f"issues={','.join(issues)}")
