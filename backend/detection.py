import cv2
import threading
import os
from ultralytics import YOLO
import mediapipe as mp

DETECT_MAX_WIDTH = 640
DETECT_LOCK = threading.Lock()
DETECT_STRIDE = max(int(os.environ.get("DETECT_STRIDE", "4")), 1)
YOLO_FALLBACK_STRIDE = DETECT_STRIDE * 2

_model = None
_face_detection = None


class _FallbackDetection:
    def __init__(self, location_data):
        self.location_data = location_data

class _FallbackLocationData:
    def __init__(self, relative_bounding_box):
        self.relative_bounding_box = relative_bounding_box

class _FallbackBoundingBox:
    def __init__(self, xmin, ymin, width, height):
        self.xmin = xmin
        self.ymin = ymin
        self.width = width
        self.height = height

class _FallbackResults:
    def __init__(self, detections):
        self.detections = detections

class _YoloFaceDetectorAdapter:
    """Fallback detector using YOLOv8 person detection when MediaPipe solutions is unavailable."""
    def process(self, rgb_frame):
        yolo_box = detect_person_yolo(rgb_frame)
        if not yolo_box:
            return _FallbackResults([])
        h, w = rgb_frame.shape[:2]
        x, y, bw, bh = yolo_box
        bbox = _FallbackBoundingBox(max(0.0, x / w), max(0.0, y / h), min(1.0, bw / w), min(1.0, bh / h))
        loc = _FallbackLocationData(bbox)
        return _FallbackResults([_FallbackDetection(loc)])


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
                    import mediapipe as mp
                    if hasattr(mp, "solutions"):
                        _face_detection = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
                    else:
                        raise AttributeError("no solutions attribute in mediapipe")
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
    if not results.detections:
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
        boxes = result.boxes
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
