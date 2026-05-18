from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import subprocess
import wave

from piano_transcription_lab.audio import normalize_audio
from piano_transcription_lab.midi_cleanup import CleanupConfig, clean_midi_file
from piano_transcription_lab.render import render_pdf
from piano_transcription_lab.review import write_review_report
from piano_transcription_lab.score_export import export_musicxml
from piano_transcription_lab.separation import separate_audio
from piano_transcription_lab.transcription import transcribe_audio


@dataclass(frozen=True)
class PipelineConfig:
    output_prefix: Path
    work_dir: Path
    existing_midi: Path | None = None
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    separate: bool = False
    sample_rate: int = 44100
    channels: int = 2
    ffmpeg: str = "ffmpeg"
    musescore: str = "mscore"
    model: str = "piano-transcription-inference"
    device: str = "cpu"
    checkpoint_path: Path | None = None
    transcriber_command: str | None = None
    hand_split_pitch: int | None = None


@dataclass(frozen=True)
class PipelineResult:
    raw_midi: Path | None
    clean_midi: Path
    musicxml: Path
    pdf: Path
    review: Path
    render_source: str
    normalized_audio: Path | None = None
    transcription_audio: Path | None = None


class PipelineRunner:
    def __init__(
        self,
        normalize_audio=normalize_audio,
        separate_audio=separate_audio,
        transcribe_audio=transcribe_audio,
        clean_midi=clean_midi_file,
        export_musicxml=export_musicxml,
        render_pdf=render_pdf,
        review_score=write_review_report,
    ) -> None:
        self.normalize_audio = normalize_audio
        self.separate_audio = separate_audio
        self.transcribe_audio = transcribe_audio
        self.clean_midi = clean_midi
        self.export_musicxml = export_musicxml
        self.render_pdf = render_pdf
        self.review_score = review_score

    def run(self, input_audio: Path, config: PipelineConfig) -> PipelineResult:
        config.work_dir.mkdir(parents=True, exist_ok=True)
        config.output_prefix.parent.mkdir(parents=True, exist_ok=True)

        raw_midi = config.output_prefix.with_suffix(".raw.mid")
        clean_midi = config.output_prefix.with_suffix(".clean.mid")
        musicxml = config.output_prefix.with_suffix(".musicxml")
        pdf = config.output_prefix.with_suffix(".pdf")
        review = config.output_prefix.with_suffix(".review.json")

        normalized_audio: Path | None = None
        transcription_audio: Path | None = None
        audio_duration_seconds: float | None = None

        if config.existing_midi:
            midi_source = config.existing_midi
            raw_midi = None
        else:
            normalized_audio = config.work_dir / f"{input_audio.stem}.wav"
            self.normalize_audio(input_audio, normalized_audio, config)
            transcription_audio = (
                self.separate_audio(normalized_audio, config.work_dir, config)
                if config.separate
                else normalized_audio
            )
            self.transcribe_audio(transcription_audio, raw_midi, config)
            midi_source = raw_midi
            audio_duration_seconds = _wav_duration_seconds(normalized_audio)

        cleanup = (
            replace(config.cleanup, max_end_seconds=audio_duration_seconds)
            if audio_duration_seconds is not None
            and config.cleanup.max_end_seconds is None
            else config.cleanup
        )
        self.clean_midi(midi_source, clean_midi, cleanup)
        self.export_musicxml(clean_midi, musicxml, config)
        try:
            self.render_pdf(musicxml, pdf, config)
            render_source = "musicxml"
        except subprocess.CalledProcessError:
            fallback_midi = musicxml.with_suffix(".hands.mid")
            self.render_pdf(fallback_midi if fallback_midi.exists() else clean_midi, pdf, config)
            render_source = "midi_fallback"

        self.review_score(
            clean_midi,
            review,
            config,
            audio_duration_seconds=audio_duration_seconds,
            render_source=render_source,
            musicxml_path=musicxml,
        )

        return PipelineResult(
            raw_midi=raw_midi,
            clean_midi=clean_midi,
            musicxml=musicxml,
            pdf=pdf,
            review=review,
            render_source=render_source,
            normalized_audio=normalized_audio,
            transcription_audio=transcription_audio,
        )


def _wav_duration_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()
    except (OSError, EOFError, wave.Error, ZeroDivisionError):
        return None
