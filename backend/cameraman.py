import os
import math

ASPECT_RATIO = 9 / 16
JUMP_CONFIRM_FRAMES = max(int(os.environ.get("JUMP_CONFIRM_FRAMES", "3")), 1)
SCENE_CUT_RESET = os.environ.get("SCENE_CUT_RESET", "1") != "0"

class SmoothedCameraman:
    """
    Handles smooth camera movement.
    Simplified Logic: "Heavy Tripod"
    Only moves if the subject leaves the center safe zone.
    Moves slowly and linearly.
    """
    def __init__(self, output_width, output_height, video_width, video_height, aspect_ratio=ASPECT_RATIO):
        self.output_width = output_width
        self.output_height = output_height
        self.video_width = video_width
        self.video_height = video_height
        self.aspect_ratio = aspect_ratio

        # Initial State
        self.current_center_x = video_width / 2
        self.target_center_x = video_width / 2

        # Calculate crop dimensions once
        self.crop_height = video_height
        self.crop_width = int(self.crop_height * aspect_ratio)
        if self.crop_width > video_width:
             self.crop_width = video_width
             self.crop_height = int(self.crop_width / aspect_ratio)

        # Safe Zone: 20% of the video width
        # As long as the target is within this zone relative to current center, DO NOT MOVE.
        self.safe_zone_radius = self.crop_width * 0.25

        self.jump_confirm_frames = JUMP_CONFIRM_FRAMES
        self._pending_target = None
        self._pending_count = 0
        self._snap_pending = False

    def begin_scene(self):
        """Forget the previous shot's subject at a scene cut."""
        self._pending_target = None
        self._pending_count = 0
        self._snap_pending = True

    def update_target(self, face_box):
        """Update the target centre from a detection, ignoring lone big jumps."""
        if not face_box:
            return
        x, y, w, h = face_box
        new_center = x + w / 2

        if self._snap_pending:
            self._snap_pending = False
            self._pending_target = None
            self._pending_count = 0
            self.target_center_x = new_center
            self.current_center_x = new_center
            return

        if abs(new_center - self.target_center_x) > self.safe_zone_radius:
            if (self._pending_target is not None
                    and abs(new_center - self._pending_target) <= self.safe_zone_radius):
                self._pending_count += 1
            else:
                self._pending_target = new_center
                self._pending_count = 1
            if self._pending_count < self.jump_confirm_frames:
                return  # not convinced yet — hold the frame

        self.target_center_x = new_center
        self._pending_target = None
        self._pending_count = 0

    def get_crop_box(self, force_snap=False):
        """Calculate the crop coordinates, moving smoothly towards the target."""
        if force_snap:
            self.current_center_x = self.target_center_x
        else:
            speed = 0.05
            self.current_center_x += (self.target_center_x - self.current_center_x) * speed

        left = max(0, int(self.current_center_x - self.crop_width / 2))
        top = 0
        right = min(self.video_width, left + self.crop_width)
        bottom = self.crop_height

        if left == 0:
             right = min(self.video_width, self.crop_width)
        if right == self.video_width:
             left = max(0, self.video_width - self.crop_width)

        return (left, top, right, bottom)


class SpeakerTracker:
    """
    Tracks speakers over time to prevent rapid switching and handle temporary obstructions.
    """
    def __init__(self, stabilization_frames=15, cooldown_frames=30):
        self.active_speaker_id = None
        self.speaker_scores = {}
        self.last_seen = {}
        self.locked_counter = 0

        self.stabilization_threshold = stabilization_frames
        self.switch_cooldown = cooldown_frames
        self.last_switch_frame = -1000

        self.next_id = 0
        self.known_faces = []

    def reset(self):
        """Forget every speaker at a scene cut."""
        self.active_speaker_id = None
        self.speaker_scores = {}
        self.last_seen = {}
        self.locked_counter = 0
        self.last_switch_frame = -1000
        self.known_faces = []

    def get_target(self, face_candidates, frame_number, width):
        """
        Decides which face to focus on.
        """
        current_candidates = []

        for face in face_candidates:
            x, y, w, h = face['box']
            center_x = x + w / 2

            best_match_id = -1
            min_dist = width * 0.15

            for kf in self.known_faces:
                if frame_number - kf['last_frame'] > 30:
                    continue

                dist = abs(center_x - kf['center'])
                if dist < min_dist:
                    min_dist = dist
                    best_match_id = kf['id']

            if best_match_id == -1:
                best_match_id = self.next_id
                self.next_id += 1

            self.known_faces = [kf for kf in self.known_faces if kf['id'] != best_match_id]
            self.known_faces.append({'id': best_match_id, 'center': center_x, 'last_frame': frame_number})

            current_candidates.append({
                'id': best_match_id,
                'box': face['box'],
                'score': face['score']
            })

        for pid in list(self.speaker_scores.keys()):
             self.speaker_scores[pid] *= 0.85
             if self.speaker_scores[pid] < 0.1:
                 del self.speaker_scores[pid]

        for cand in current_candidates:
            pid = cand['id']
            raw_score = cand['score'] / (width * width * 0.05)
            self.speaker_scores[pid] = self.speaker_scores.get(pid, 0) + raw_score

        if not current_candidates:
            return None

        best_candidate = None
        max_score = -1

        for cand in current_candidates:
            pid = cand['id']
            total_score = self.speaker_scores.get(pid, 0)

            if pid == self.active_speaker_id:
                total_score *= 3.0

            if total_score > max_score:
                max_score = total_score
                best_candidate = cand

        if best_candidate:
            target_id = best_candidate['id']

            if target_id == self.active_speaker_id:
                self.locked_counter += 1
                return best_candidate['box']

            if frame_number - self.last_switch_frame < self.switch_cooldown:
                old_cand = next((c for c in current_candidates if c['id'] == self.active_speaker_id), None)
                return old_cand['box'] if old_cand else None

            self.active_speaker_id = target_id
            self.last_switch_frame = frame_number
            self.locked_counter = 0
            return best_candidate['box']

        return None
