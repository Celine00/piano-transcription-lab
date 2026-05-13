from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess

from piano_transcription_lab.audio import normalize_audio
from piano_transcription_lab.midi_cleanup import CleanupConfig, clean_midi_file
from piano_transcription_lab.render import render_pdf
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


@dataclass(frozen=True)
class PipelineResult:
    raw_midi: Path | None
    clean_midi: Path
    musicxml: Path
    pdf: Path
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
    ) -> None:
        self.normalize_audio = normalize_audio
        self.separate_audio = separate_audio
        self.transcribe_audio = transcribe_audio
        self.clean_midi = clean_midi
        self.export_musicxml = export_musicxml
        self.render_pdf = render_pdf

    def run(self, input_audio: Path, config: PipelineConfig) -> PipelineResult:
        config.work_dir.mkdir(parents=True, exist_ok=True)
        config.output_prefix.parent.mkdir(parents=True, exist_ok=True)

        raw_midi = config.output_prefix.with_suffix(".raw.mid")
        clean_midi = config.output_prefix.with_suffix(".clean.mid")
        musicxml = config.output_prefix.with_suffix(".musicxml")
        pdf = config.output_prefix.with_suffix(".pdf")

        normalized_audio: Path | None = None
        transcription_audio: Path | None = None

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

        self.clean_midi(midi_source, clean_midi, config.cleanup)
        self.export_musicxml(clean_midi, musicxml, config)
        try:
            self.render_pdf(musicxml, pdf, config)
        except subprocess.CalledProcessError:
            self.render_pdf(clean_midi, pdf, config)

        return PipelineResult(
            raw_midi=raw_midi,
            clean_midi=clean_midi,
            musicxml=musicxml,
            pdf=pdf,
            normalized_audio=normalized_audio,
            transcription_audio=transcription_audio,
        )
