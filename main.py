"""
AURA - Phase 1: Make recognition work.

Detects hands, works out which fingers are up, classifies the gesture and
shows it on screen. It does NOT control the laptop in any way.

Controls: press 'q' or ESC to quit.
"""

import math
import time
from collections import Counter, deque

import cv2
import mediapipe as mp

# ---------------------------------------------------------------- settings
CAMERA_INDEX = 0
MAX_HANDS = 2
DETECTION_CONFIDENCE = 0.7
TRACKING_CONFIDENCE = 0.6
SMOOTHING_FRAMES = 7          # majority vote over the last N frames (kills flicker)
PINCH_THRESHOLD = 0.25        # thumb-index distance / hand size

# MediaPipe landmark indices
WRIST = 0
THUMB_IP, THUMB_TIP = 3, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_PIP, MIDDLE_TIP = 10, 12
RING_PIP, RING_TIP = 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20
MIDDLE_MCP = 9

FINGER_NAMES = ["Thumb", "Index", "Middle", "Ring", "Pinky"]

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles


# ---------------------------------------------------------------- geometry
def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def hand_size(lm):
    """Wrist to middle-finger knuckle: a stable measure of how big the hand is."""
    return dist(lm[WRIST], lm[MIDDLE_MCP]) or 1e-6


# ---------------------------------------------------------------- fingers
def fingers_up(lm):
    """
    Returns [thumb, index, middle, ring, pinky] as booleans.

    Uses distances from the wrist instead of raw y-values, so it still works
    when your hand is tilted or rotated. The thumb is handled separately and
    does not depend on left/right hand labels.
    """
    # Thumb: extended if the tip is farther from the pinky base than the joint is
    thumb = dist(lm[THUMB_TIP], lm[PINKY_MCP]) > dist(lm[THUMB_IP], lm[PINKY_MCP]) * 1.1

    def extended(tip, pip):
        return dist(lm[WRIST], lm[tip]) > dist(lm[WRIST], lm[pip]) * 1.05

    return [
        thumb,
        extended(INDEX_TIP, INDEX_PIP),
        extended(MIDDLE_TIP, MIDDLE_PIP),
        extended(RING_TIP, RING_PIP),
        extended(PINKY_TIP, PINKY_PIP),
    ]


# ---------------------------------------------------------------- gestures
def classify(lm, up):
    thumb, index, middle, ring, pinky = up
    count = sum(up)

    # Pinch: thumb tip touching index tip (checked first, it overrides finger state)
    pinch_ratio = dist(lm[THUMB_TIP], lm[INDEX_TIP]) / hand_size(lm)
    if pinch_ratio < PINCH_THRESHOLD and (middle or ring or pinky):
        return "OK / Pinch"
    if pinch_ratio < PINCH_THRESHOLD and count <= 2:
        return "Pinch"

    if count == 0:
        return "Fist"
    if count == 5:
        return "Open Palm"
    if up == [False, True, False, False, False]:
        return "Pointing"
    if up == [False, True, True, False, False]:
        return "Peace"
    if up == [False, True, True, True, False]:
        return "Three"
    if up == [False, True, True, True, True]:
        return "Four"
    if up == [False, True, False, False, True]:
        return "Rock"
    if up == [True, True, False, False, True]:
        return "Spider-Man"
    if up == [True, False, False, False, False]:
        # Thumb tip above the wrist = up, below = down
        return "Thumbs Up" if lm[THUMB_TIP].y < lm[WRIST].y else "Thumbs Down"
    if up == [False, False, False, False, True]:
        return "Pinky"
    return "Unknown"


# ---------------------------------------------------------------- smoothing
class GestureSmoother:
    """Keeps a short history per hand and returns the most common gesture."""

    def __init__(self, size):
        self.size = size
        self.history = {}

    def update(self, hand_id, gesture):
        h = self.history.setdefault(hand_id, deque(maxlen=self.size))
        h.append(gesture)
        return Counter(h).most_common(1)[0][0]

    def prune(self, active_ids):
        for k in list(self.history):
            if k not in active_ids:
                del self.history[k]


# ---------------------------------------------------------------- drawing
def draw_hud(frame, hands_info, fps):
    h, w = frame.shape[:2]
    cv2.putText(frame, f"FPS: {fps:.0f}", (w - 130, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(frame, "AURA - Phase 1 (recognition only)", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    if not hands_info:
        cv2.putText(frame, "No hand detected", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return

    y = 70
    for info in hands_info:
        label, gesture, up = info["label"], info["gesture"], info["up"]
        cv2.putText(frame, f"{label} hand: {gesture}", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
        y += 35
        states = "  ".join(
            f"{n[0]}:{'UP' if u else '--'}" for n, u in zip(FINGER_NAMES, up)
        )
        cv2.putText(frame, f"{states}  ({sum(up)} up)", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
        y += 40


# ---------------------------------------------------------------- main loop
def main():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera {CAMERA_INDEX}. Try changing CAMERA_INDEX to 1."
        )

    smoother = GestureSmoother(SMOOTHING_FRAMES)
    prev_time = time.time()

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=MAX_HANDS,
        min_detection_confidence=DETECTION_CONFIDENCE,
        min_tracking_confidence=TRACKING_CONFIDENCE,
    ) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera frame not received, stopping.")
                break

            frame = cv2.flip(frame, 1)  # mirror view so it feels natural
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            hands_info = []
            active_ids = set()

            if result.multi_hand_landmarks:
                for i, (hand_lms, handedness) in enumerate(
                    zip(result.multi_hand_landmarks, result.multi_handedness)
                ):
                    lm = hand_lms.landmark
                    label = handedness.classification[0].label  # "Left" / "Right"
                    hand_id = f"{label}-{i}"
                    active_ids.add(hand_id)

                    up = fingers_up(lm)
                    raw = classify(lm, up)
                    gesture = smoother.update(hand_id, raw)

                    hands_info.append({"label": label, "gesture": gesture, "up": up})

                    mp_draw.draw_landmarks(
                        frame,
                        hand_lms,
                        mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style(),
                    )

            smoother.prune(active_ids)

            now = time.time()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now

            draw_hud(frame, hands_info, fps)
            cv2.imshow("AURA - Phase 1", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()