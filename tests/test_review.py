import json


def test_write_review_report_penalizes_midi_fallback_and_tail_overrun(tmp_path):
    mido = __import__("mido")
    from piano_transcription_lab.midi_cleanup import CleanupConfig
    from piano_transcription_lab.pipeline import PipelineConfig
    from piano_transcription_lab.review import write_review_report

    midi_path = tmp_path / "score.mid"
    report_path = tmp_path / "score.review.json"

    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    track.append(mido.Message("note_on", note=60, velocity=80, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=4800))
    mid.save(midi_path)

    write_review_report(
        midi_path,
        report_path,
        PipelineConfig(
            output_prefix=tmp_path / "score",
            work_dir=tmp_path,
            cleanup=CleanupConfig(),
        ),
        audio_duration_seconds=1.0,
        render_source="midi_fallback",
    )

    report = json.loads(report_path.read_text())
    assert report["decision"] == "reject"
    assert report["score_kind"] == "readability_without_reference"
    assert report["accuracy_reference"] is None
    assert report["render_source"] == "midi_fallback"
    assert report["metrics"]["tail_overrun_seconds"] == 4.0
    assert "musicxml_render_failed" in report["issues"]
    assert "midi_extends_beyond_audio" in report["issues"]


def test_write_review_report_rejects_unreadable_musicxml_density(tmp_path):
    mido = __import__("mido")
    from piano_transcription_lab.midi_cleanup import CleanupConfig
    from piano_transcription_lab.pipeline import PipelineConfig
    from piano_transcription_lab.review import write_review_report

    midi_path = tmp_path / "score.mid"
    musicxml_path = tmp_path / "score.musicxml"
    report_path = tmp_path / "score.review.json"

    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    track.append(mido.Message("note_on", note=60, velocity=80, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=480))
    mid.save(midi_path)

    notes = "\n".join(
        """
      <note>
        <chord />
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>120</duration>
        <tie type="start" />
        <voice>1</voice>
      </note>
      <note>
        <rest />
        <duration>120</duration>
        <voice>2</voice>
        <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
      </note>
        """.strip()
        for _ in range(20)
    )
    musicxml_path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name /></score-part></part-list>
  <part id="P1"><measure number="1">{notes}</measure></part>
</score-partwise>
"""
    )

    write_review_report(
        midi_path,
        report_path,
        PipelineConfig(
            output_prefix=tmp_path / "score",
            work_dir=tmp_path,
            cleanup=CleanupConfig(),
        ),
        audio_duration_seconds=1.0,
        render_source="musicxml",
        musicxml_path=musicxml_path,
    )

    report = json.loads(report_path.read_text())
    assert report["decision"] == "reject"
    assert report["score"] < 50
    assert "notation_density_too_high" in report["issues"]
    assert "notation_complexity_too_high" in report["issues"]
    assert report["metrics"]["musicxml"]["max_notes_per_measure"] == 40
