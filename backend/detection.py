import cv2
import threading
import os
from ultralytics import YOLO
import mediapipe as mp

DETECT_MAX_WIDTH = 640
DETECT_LOCK = threading.Lock()
DETECT_STRIDE = max(int(os.environ.get("DETECT_STRIDE", "4")), 1)
YOLO_FALLBACK_STRIDE = DETECT_STRIDE * 2

model = YOLO(os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt"))

mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)

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
        results = face_detection.process(rgb_frame)

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
        results = model(small, verbose=False, classes=[0])

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
