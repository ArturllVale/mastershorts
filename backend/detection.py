import cv2
import threading
import os
import sys
import types
from ultralytics import YOLO

DETECT_MAX_WIDTH = 640
DETECT_LOCK = threading.RLock()
DETECT_STRIDE = max(int(os.environ.get("DETECT_STRIDE", "4")), 1)
YOLO_FALLBACK_STRIDE = DETECT_STRIDE * 2

_model = None
_face_detection = None


class _FallbackDetection:
    __slots__ = ("location_data",)
    def __init__(self, location_data):
        self.location_data = location_data


class _FallbackLocationData:
    __slots__ = ("relative_bounding_box",)
    def __init__(self, relative_bounding_box):
        self.relative_bounding_box = relative_bounding_box


class _FallbackBoundingBox:
    __slots__ = ("xmin", "ymin", "width", "height")
    def __init__(self, xmin, ymin, width, height):
        self.xmin = xmin
        self.ymin = ymin
        self.width = width
        self.height = height


class _FallbackResults:
    __slots__ = ("detections",)
    def __init__(self, detections):
        self.detections = detections


class _YoloFaceDetectorAdapter:
    """Fallback detector using YOLOv8 person detection when MediaPipe solutions is unavailable."""
    def __init__(self, *args, **kwargs):
        pass

    def process(self, rgb_frame):
        h, w = rgb_frame.shape[:2]
        if h <= 0 or w <= 0:
            return _FallbackResults([])

        small, scale = _detection_frame(rgb_frame)
        with DETECT_LOCK:
            yolo = _get_yolo_model()
            results = yolo(small, verbose=False, classes=[0])

        if not results:
            return _FallbackResults([])

        detections = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = [int(v * scale) for v in xyxy]
                bw = max(0, x2 - x1)
                bh = max(0, y2 - y1)
                if bw == 0 or bh == 0:
                    continue

                # Head/face region is the top ~40% of the detected person
                face_h = max(int(bh * 0.4), 1)
                rel_xmin = max(0.0, min(1.0, float(x1) / float(w)))
                rel_ymin = max(0.0, min(1.0, float(y1) / float(h)))
                rel_w = max(0.0, min(1.0 - rel_xmin, float(bw) / float(w)))
                rel_h = max(0.0, min(1.0 - rel_ymin, float(face_h) / float(h)))

                bbox = _FallbackBoundingBox(rel_xmin, rel_ymin, rel_w, rel_h)
                loc = _FallbackLocationData(bbox)
                detections.append(_FallbackDetection(loc))

        return _FallbackResults(detections)


# Register MediaPipe emulation in sys.modules so any import of mediapipe.solutions succeeds
try:
    import mediapipe as mp
except Exception:
    mp = types.ModuleType("mediapipe")
    sys.modules["mediapipe"] = mp

_solutions_mod = types.ModuleType("mediapipe.solutions")
_fd_submod = types.ModuleType("mediapipe.solutions.face_detection")
_fd_submod.FaceDetection = _YoloFaceDetectorAdapter
_solutions_mod.face_detection = _fd_submod

if not hasattr(mp, "solutions"):
    mp.solutions = _solutions_mod

for mod_name in [
    "mediapipe.solutions",
    "mediapipe.solutions.face_detection",
    "mediapipe.python.solutions",
    "mediapipe.python.solutions.face_detection",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = _fd_submod if "face_detection" in mod_name else _solutions_mod


def _get_face_detector():
    global _face_detection
    if _face_detection is None:
        try:
            from mediapipe.python.solutions import face_detection as mp_face_detection
            _face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        except Exception:
            try:
                import mediapipe.solutions.face_detection as mp_face_detection
                _face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
            except Exception:
                try:
                    if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
                        _face_detection = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
                    else:
                        _face_detection = _YoloFaceDetectorAdapter()
                except Exception as e:
                    print(f"⚠️ MediaPipe FaceDetection unavailable ({e}) — activating YOLOv8 adapter.", flush=True)
                    _face_detection = _YoloFaceDetectorAdapter()
    return _face_detection


def _get_yolo_model():
    global _model
    if _model is None:
        _model = YOLO(os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt"))
    return _model


def __getattr__(name):
    if name == "model":
        return _get_yolo_model()
    if name == "face_detection":
        return _get_face_detector()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def _detection_frame(frame):
    h, w = frame.shape[:2]
    if w <= DETECT_MAX_WIDTH:
        return frame, 1.0
    scale = w / DETECT_MAX_WIDTH
    small = cv2.resize(frame, (DETECT_MAX_WIDTH, max(int(h / scale), 2)),
                       interpolation=cv2.INTER_AREA)
    return small, scale


def detect_face_candidates(frame):
    height, width, _ = frame.shape
    small, _scale = _detection_frame(frame)
    rgb_frame = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    with DETECT_LOCK:
        detector = _get_face_detector()
        results = detector.process(rgb_frame)

    candidates = []
    if not results or not getattr(results, "detections", None):
        return []

    for detection in results.detections:
        bboxC = detection.location_data.relative_bounding_box
        x = int(bboxC.xmin * width)
        y = int(bboxC.ymin * height)
        w = int(bboxC.width * width)
        h = int(bboxC.height * height)

        candidates.append({
            'box': [x, y, w, h],
            'score': w * h
        })
    return candidates


def detect_person_yolo(frame):
    small, scale = _detection_frame(frame)
    with DETECT_LOCK:
        yolo = _get_yolo_model()
        results = yolo(small, verbose=False, classes=[0])

    if not results:
        return None

    best_box = None
    max_area = 0

    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            x1, y1, x2, y2 = [int(i * scale) for i in box.xyxy[0]]
            w = x2 - x1
            h = y2 - y1
            area = w * h

            if area > max_area:
                max_area = area
                face_h = int(h * 0.4)
                best_box = [x1, y1, w, face_h]

    return best_box
