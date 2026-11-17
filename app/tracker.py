import os
import urllib.request

import cv2

MODEL_PATH = os.path.join("storage", "yunet_face.onnx")
MODEL_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")

MIN_INIT = 0.12
MIN_SIZE = 0.05
WINDOW = 0.25
MAX_SHIFT = 0.30
BIG_FACE = 0.22
SCORE_MIN = 0.70

_detector = None


def _ensure_model():
    if not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) < 100000:
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        print("Descarc detectorul de fete YuNet (~230 KB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def _get_detector():
    global _detector
    if _detector is None:
        _detector = cv2.FaceDetectorYN_create(
            _ensure_model(), "", (480, 270), SCORE_MIN, 0.3, 5
        )
    return _detector


def _merge_dets(dets):
    dets = sorted(dets, key=lambda d: d[2] * d[1], reverse=True)
    kept = []
    for cx, w, score in dets:
        if all(abs(cx - k[0]) > 0.06 for k in kept):
            kept.append((cx, w, score))
    return kept


def detect_face_samples(video_path, start, end, sample_fps=1.0):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], 0, 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width == 0 or height == 0:
        cap.release()
        return [], 0, 0

    detector = _get_detector()
    samples = []
    t = 0.0
    duration = end - start

    while t < duration:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((start + t) * fps))
        ret, frame = cap.read()
        if not ret:
            break
        h, w = frame.shape[:2]
        small_h = max(1, int(h * 480.0 / w))
        small = cv2.resize(frame, (480, small_h))
        detector.setInputSize((480, small_h))
        ok, faces = detector.detect(small)

        dets = []
        if ok and faces is not None:
            for face in faces:
                fx, fy, fw, fh = face[0], face[1], face[2], face[3]
                score = float(face[14])
                dets.append(((fx + fw / 2.0) / 480.0, fw / 480.0, score))

        samples.append((t, _merge_dets(dets)))
        t += 1.0 / sample_fps

    cap.release()
    return samples, width, height


def build_crop_x_expression(video_path, start, end, chunk=3.0):
    samples, width, height = detect_face_samples(video_path, start, end)
    if not samples or width == 0:
        return None

    crop_w = int(height * 9 / 16)
    if crop_w >= width:
        return None

    duration = end - start
    n_chunks = max(1, int(duration // chunk) + 1)

    locks = []
    prev = None
    for i in range(n_chunks):
        t0, t1 = i * chunk, (i + 1) * chunk
        cands = []
        for (t, dets) in samples:
            if t0 <= t < t1:
                for (cx, w, score) in dets:
                    if w >= MIN_SIZE:
                        cands.append((cx, w, score))

        pick = None
        if prev is None:
            pool = [c for c in cands if c[1] >= MIN_INIT]
            if pool:
                pick = max(pool, key=lambda c: c[2] * c[1])
        else:
            near = [c for c in cands if abs(c[0] - prev) <= WINDOW]
            if near:
                pick = max(near, key=lambda c: c[2] * c[1])
            else:
                big = [c for c in cands if c[1] >= BIG_FACE]
                if big:
                    pick = max(big, key=lambda c: c[2] * c[1])

        if pick is not None:
            x = pick[0]
            if prev is not None:
                x = min(max(x, prev - MAX_SHIFT), prev + MAX_SHIFT)
            prev = x
            locks.append(x)
        else:
            locks.append(prev)

    if all(v is None for v in locks):
        return None

    first_valid = next(v for v in locks if v is not None)
    locks = [v if v is not None else first_valid for v in locks]

    smoothed = []
    for i in range(len(locks)):
        win = locks[max(0, i - 1): i + 2]
        smoothed.append(sum(win) / len(win))

    consts = [int(v * width - crop_w / 2) for v in smoothed]

    inner = str(consts[-1])
    for i in range(n_chunks - 2, -1, -1):
        limit = (i + 1) * chunk
        inner = f"if(lt(t,{limit}),{consts[i]},{inner})"

    return f"clip({inner},0,iw-{crop_w})"