from pathlib import Path
import xml.etree.ElementTree as ET


def test_export_musicxml_prefers_musescore_when_available(tmp_path):
    mido = __import__("mido")
    from piano_transcription_lab.pipeline import PipelineConfig
    import piano_transcription_lab.score_export as score_export

    calls = []

    def run(command, check):
        calls.append((command, check))
        Path(command[2]).write_text("<score-partwise />")

    source = tmp_path / "score.mid"
    target = tmp_path / "score.musicxml"
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.Message("note_on", note=64, velocity=80, time=0))
    track.append(mido.Message("note_off", note=64, velocity=0, time=480))
    mid.save(source)

    score_export.export_musicxml(
        source,
        target,
        PipelineConfig(output_prefix=tmp_path / "score", work_dir=tmp_path, musescore="mscore"),
        run_command=run,
    )

    assert calls == [(["mscore", "-o", str(target), str(tmp_path / "score.hands.mid")], True)]
    assert target.read_text() == "<score-partwise />"


def test_export_musicxml_splits_midi_into_right_and_left_hand_tracks_before_musescore(tmp_path):
    mido = __import__("mido")
    from piano_transcription_lab.pipeline import PipelineConfig
    import piano_transcription_lab.score_export as score_export

    source = tmp_path / "score.mid"
    target = tmp_path / "score.musicxml"

    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    track.append(mido.Message("note_on", note=48, velocity=72, time=0))
    track.append(mido.Message("note_on", note=72, velocity=80, time=0))
    track.append(mido.Message("note_off", note=48, velocity=0, time=480))
    track.append(mido.Message("note_off", note=72, velocity=0, time=0))
    mid.save(source)

    calls = []

    def run(command, check):
        calls.append((command, check))
        Path(command[2]).write_text("<score-partwise />")

    score_export.export_musicxml(
        source,
        target,
        PipelineConfig(output_prefix=tmp_path / "score", work_dir=tmp_path, musescore="mscore"),
        run_command=run,
    )

    split_source = Path(calls[0][0][3])
    split = mido.MidiFile(split_source)

    assert split_source.name == "score.hands.mid"
    assert [track[0].name for track in split.tracks] == ["Right Hand", "Left Hand"]
    assert _track_notes(split.tracks[0]) == [72]
    assert _track_notes(split.tracks[1]) == [48]


def test_export_musicxml_adapts_hand_split_when_left_hand_would_be_sparse(tmp_path):
    mido = __import__("mido")
    from piano_transcription_lab.pipeline import PipelineConfig
    import piano_transcription_lab.score_export as score_export

    source = tmp_path / "score.mid"
    target = tmp_path / "score.musicxml"

    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    for note in [50, 62, 64, 67, 72, 76, 79]:
        track.append(mido.Message("note_on", note=note, velocity=80, time=0))
        track.append(mido.Message("note_off", note=note, velocity=0, time=120))
    mid.save(source)

    calls = []

    def run(command, check):
        calls.append((command, check))
        Path(command[2]).write_text("<score-partwise />")

    score_export.export_musicxml(
        source,
        target,
        PipelineConfig(output_prefix=tmp_path / "score", work_dir=tmp_path, musescore="mscore"),
        run_command=run,
    )

    split = mido.MidiFile(calls[0][0][3])

    assert _track_notes(split.tracks[0]) == [67, 72, 76, 79]
    assert _track_notes(split.tracks[1]) == [50, 62, 64]


def test_export_musicxml_normalizes_each_hand_to_one_staff(tmp_path):
    mido = __import__("mido")
    from piano_transcription_lab.pipeline import PipelineConfig
    import piano_transcription_lab.score_export as score_export

    source = tmp_path / "score.mid"
    target = tmp_path / "score.musicxml"

    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.Message("note_on", note=48, velocity=72, time=0))
    track.append(mido.Message("note_off", note=48, velocity=0, time=480))
    mid.save(source)

    def run(command, check):
        Path(command[2]).write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Piano, Right Hand</part-name></score-part>
    <score-part id="P2"><part-name>Piano, Left Hand</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes><staves>1</staves></attributes>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>1</duration><voice>1</voice><staff>1</staff></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <print>
        <staff-layout number="1"><staff-distance>68.79</staff-distance></staff-layout>
        <staff-layout number="2"><staff-distance>46.3</staff-distance></staff-layout>
      </print>
      <attributes>
        <staves>2</staves>
        <clef number="1"><sign>F</sign><line>4</line></clef>
        <clef number="2"><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration><voice>1</voice><staff>1</staff></note>
      <note><pitch><step>G</step><octave>3</octave></pitch><duration>1</duration><voice>5</voice><staff>2</staff></note>
    </measure>
  </part>
</score-partwise>
"""
        )

    score_export.export_musicxml(
        source,
        target,
        PipelineConfig(output_prefix=tmp_path / "score", work_dir=tmp_path, musescore="mscore"),
        run_command=run,
    )

    root = ET.parse(target).getroot()

    assert [part.findtext("part-name") for part in root.findall(".//score-part")] == [
        "Right Hand",
        "Left Hand",
    ]
    assert [staves.text for staves in root.findall(".//staves")] == ["1", "1"]
    assert [staff.text for staff in root.findall(".//staff")] == ["1", "1", "1"]
    assert [clef.attrib.get("number") for clef in root.findall(".//clef")] == ["1"]
    assert [layout.attrib.get("number") for layout in root.findall(".//staff-layout")] == ["1"]


def _track_notes(track):
    return [msg.note for msg in track if msg.type == "note_on" and msg.velocity > 0]
