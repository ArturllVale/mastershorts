import os
import json

# --- Transcript checkpoint (survive a redeploy without paying twice) ---------
# A job interrupted by a container restart is re-run from its resume manifest
# (app.py) with the SAME output directory. Transcription is the slow, paid part
# of the pipeline that ran before the interruption, so the finished transcript
# is left in the job directory and picked up by the re-run instead of
# transcribing again. Same shape and same validation as --transcript.
TRANSCRIPT_CHECKPOINT = ".transcript_checkpoint.json"


def _checkpoint_source_key(input_video, duration):
    """What ties a checkpoint to ONE source. Not the path: a resumed cloud job
    re-downloads to the same name, and the CLI may be pointed at a different
    file in a directory where an earlier run died. Name plus duration is what
    both the server and a careful CLI user keep stable across the two runs."""
    return {"name": os.path.basename(input_video), "duration": round(float(duration), 1)}


def save_transcript_checkpoint(output_dir, transcript, input_video, duration):
    """Best effort: a failure here must never fail the job."""
    try:
        payload = {"source": _checkpoint_source_key(input_video, duration),
                   "transcript": transcript}
        with open(os.path.join(output_dir, TRANSCRIPT_CHECKPOINT), "w") as f:
            json.dump(payload, f)
    except Exception as e:
        print(f"⚠️ Could not save transcript checkpoint: {e}")


def load_transcript_checkpoint(output_dir, input_video, duration):
    """The transcript an interrupted run left behind for THIS source, or None.

    A checkpoint for a different source (a CLI run that died, then a new video
    processed in the same directory) is ignored, not reused."""
    path = os.path.join(output_dir, TRANSCRIPT_CHECKPOINT)
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            payload = json.load(f)
        source = payload.get("source") or {}
        expected = _checkpoint_source_key(input_video, duration)
        if source.get("name") != expected["name"] \
                or abs(float(source.get("duration", -1)) - expected["duration"]) > 0.5:
            print("⏭️ Transcript checkpoint belongs to another source — ignoring it.")
            return None
        transcript = payload.get("transcript") or {}
        if not transcript.get("segments"):
            raise ValueError("checkpoint has no segments")
        return transcript
    except Exception as e:
        print(f"⚠️ Ignoring unusable transcript checkpoint ({e}).")
        return None


def clear_transcript_checkpoint(output_dir):
    try:
        os.remove(os.path.join(output_dir, TRANSCRIPT_CHECKPOINT))
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️ Could not remove transcript checkpoint: {e}")


