"""
AURA - Phase 2: Add actual controls.

Gestures (use ONE hand, the first one detected):
    Pointing (index only) ......... move the cursor
    Pinch (thumb + index touch) ... left click
    Peace (index + middle) ........ scroll: move your hand up / down
    Fist held for 1 second ........ EMERGENCY STOP (pauses everything)
    Open Palm held for 1.5 seconds  resume after a stop

By default this runs in DRY-RUN mode: it shows what it WOULD do on screen
but never touches your mouse. Add --live when you trust it:

    python aura_controls.py            # safe, no mouse control
    python aura_controls.py --live     # real control (starts paused)

Keys: p = pause / resume, q or ESC = quit.
Extra safety: slamming the real mouse into any screen corner also stops AURA.
"""

import argparse
import getpass
import os
import sys
import time

import cv2
from voice_control import VoiceListener, launch_application, load_openai_api_key

from main import (
    DETECTION_CONFIDENCE,
    INDEX_MCP,
    INDEX_TIP,
    MIDDLE_TIP,
    SMOOTHING_FRAMES,
    TRACKING_CONFIDENCE,
    GestureSmoother,
    classify,
    fingers_up,
    mp_draw,
    mp_hands,
    mp_styles,
)

try:
    import pyautogui

    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True
except Exception:  # no display / not installed: dry-run still works
    pyautogui = None

# ---------------------------------------------------------------- settings
MARGIN = 0.15              # ignore the outer 15% of the camera frame (easier to reach edges)
CURSOR_SMOOTHING = 0.35    # 0..1, lower = smoother but laggier
CLICK_COOLDOWN = 0.6       # seconds between clicks
SCROLL_SENSITIVITY = 42    # wheel notches per full camera-frame height
SCROLL_DEADZONE = 0.0025   # ignore tiny hand jitter
STOP_HOLD = 1.0            # seconds of Fist to trigger emergency stop
RESUME_HOLD = 1.5          # seconds of Open Palm to resume
CORNER_GUARD = 6           # keep the cursor this many px away from screen corners
PINCH_GESTURES = ("Pinch", "OK / Pinch")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------- controller
class Controller:
    """Turns recognised gestures into actions. Pure logic: easy to test."""

    def __init__(self, live, screen_w, screen_h):
        self.live = live
        self.sw, self.sh = screen_w, screen_h
        self.paused = live  # live mode starts paused: show open palm to begin
        self.cursor = None
        self.target = (0.5, 0.5)
        self.last_click = 0.0
        self.prev_gesture = None
        self.hold_gesture = None
        self.hold_start = 0.0
        self.hold_progress = 0.0
        self.prev_scroll_y = None
        self.scroll_remainder = 0.0
        self.message = "Show open palm 1.5s to start" if live else "Dry-run: nothing will be controlled"
        self.message_time = time.time()

    def note(self, text, now):
        self.message, self.message_time = text, now

    def lost_hand(self):
        self.prev_gesture = None
        self.hold_gesture = None
        self.hold_progress = 0.0
        self.prev_scroll_y = None
        self.scroll_remainder = 0.0

    def toggle_pause(self, now):
        self.paused = not self.paused
        self.cursor = None
        self.prev_scroll_y = None
        self.scroll_remainder = 0.0
        self.note("PAUSED" if self.paused else "RESUMED", now)

    # ---- main entry point, called once per frame with a hand in view
    def update(self, lm, gesture, now):
        if gesture != self.hold_gesture:
            self.hold_gesture, self.hold_start = gesture, now
        held = now - self.hold_start
        self.hold_progress = 0.0

        if self.paused:
            if gesture == "Open Palm":
                self.hold_progress = min(held / RESUME_HOLD, 1.0)
                if held >= RESUME_HOLD:
                    self.paused = False
                    self.note("RESUMED", now)
            self.prev_gesture = gesture
            return

        if gesture == "Fist":
            self.hold_progress = min(held / STOP_HOLD, 1.0)
            if held >= STOP_HOLD:
                self.paused = True
                self.cursor = None
                self.prev_scroll_y = None
                self.scroll_remainder = 0.0
                self.hold_progress = 0.0
                self.note("EMERGENCY STOP - open palm 1.5s to resume", now)
                self.prev_gesture = gesture
                return

        if gesture == "Pointing":
            self._move(lm)
            self._scroll_at(lm[INDEX_TIP].y, now)

        if gesture in PINCH_GESTURES and self.prev_gesture not in PINCH_GESTURES:
            self._click(now)

        if gesture == "Peace":
            self._scroll_at((lm[INDEX_TIP].y + lm[MIDDLE_TIP].y) / 2, now)
        elif gesture != "Pointing":
            self.prev_scroll_y = None
            self.scroll_remainder = 0.0

        self.prev_gesture = gesture

    # ---- actions
    def _move(self, lm):
        # The knuckle moves much less than the fingertip, so clicks don't shift the cursor
        nx = clamp((lm[INDEX_MCP].x - MARGIN) / (1 - 2 * MARGIN), 0.0, 1.0)
        ny = clamp((lm[INDEX_MCP].y - MARGIN) / (1 - 2 * MARGIN), 0.0, 1.0)
        tx = clamp(nx * (self.sw - 1), CORNER_GUARD, self.sw - 1 - CORNER_GUARD)
        ty = clamp(ny * (self.sh - 1), CORNER_GUARD, self.sh - 1 - CORNER_GUARD)

        if self.cursor is None:
            self.cursor = (tx, ty)
        else:
            cx, cy = self.cursor
            self.cursor = (cx + (tx - cx) * CURSOR_SMOOTHING, cy + (ty - cy) * CURSOR_SMOOTHING)

        self.target = (nx, ny)
        if self.live:
            pyautogui.moveTo(int(self.cursor[0]), int(self.cursor[1]))

    def _click(self, now):
        if now - self.last_click < CLICK_COOLDOWN:
            return
        self.last_click = now
        if self.live:
            pyautogui.click()
            self.note("CLICK", now)
        else:
            self.note("CLICK (dry-run)", now)

    def _scroll_at(self, y, now):
        if self.prev_scroll_y is not None:
            dy = y - self.prev_scroll_y
            if abs(dy) > SCROLL_DEADZONE:
                self.scroll_remainder += -dy * SCROLL_SENSITIVITY  # finger up -> scroll up
                amount = int(self.scroll_remainder)
                if amount:
                    self.scroll_remainder -= amount
                    if self.live:
                        pyautogui.scroll(amount)
                    self.note(f"SCROLL {'up' if amount > 0 else 'down'}"
                              + ("" if self.live else " (dry-run)"), now)
        self.prev_scroll_y = y


# ---------------------------------------------------------------- drawing
def draw_hud(frame, ctl, gesture, fps, now, voice_status="disabled"):
    h, w = frame.shape[:2]
    x0, y0 = int(MARGIN * w), int(MARGIN * h)
    x1, y1 = int((1 - MARGIN) * w), int((1 - MARGIN) * h)
    cv2.rectangle(frame, (x0, y0), (x1, y1), (255, 255, 255), 1)

    mode = "LIVE" if ctl.live else "DRY-RUN (mouse untouched)"
    cv2.putText(frame, f"AURA Phase 2 - {mode}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255) if ctl.live else (0, 255, 255), 2)
    cv2.putText(frame, f"FPS {fps:.0f}", (w - 100, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(frame, f"Gesture: {gesture or 'no hand'}", (10, 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    cv2.putText(frame, f"VOICE: {voice_status}"[:72], (10, 94),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 210, 0), 2)
    if ctl.paused:
        cv2.putText(frame, "PAUSED - open palm or say 'resume AURA'", (10, 128),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
    elif gesture == "Pointing":
        px = int(x0 + ctl.target[0] * (x1 - x0))
        py = int(y0 + ctl.target[1] * (y1 - y0))
        cv2.circle(frame, (px, py), 10, (0, 255, 0), 2)

    if ctl.hold_progress > 0:
        cv2.rectangle(frame, (10, 148), (210, 166), (255, 255, 255), 1)
        cv2.rectangle(frame, (10, 148), (10 + int(200 * ctl.hold_progress), 166), (0, 165, 255), -1)

    if now - ctl.message_time < 1.5:
        cv2.putText(frame, ctl.message, (10, h - 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)
    cv2.putText(frame, "1 finger: move + up/down scroll   Pinch: click   2 fingers: scroll   Fist: STOP",
                (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)


# ---------------------------------------------------------------- main loop
def run(args):
    if args.live and pyautogui is None:
        raise SystemExit("--live needs pyautogui and a display. Run: pip install pyautogui")
    api_key = None
    if args.openai and not args.no_voice:
        api_key = load_openai_api_key(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        if not api_key and sys.stdin.isatty():
            api_key = getpass.getpass("OpenAI API key (or save it in .env): ").strip()
        if not api_key:
            raise SystemExit("OpenAI API key not found. Add OPENAI_API_KEY=... to the project .env file or run in a terminal to enter it securely.")

    sw, sh = pyautogui.size() if pyautogui else (1920, 1080)
    ctl = Controller(args.live, sw, sh)
    smoother = GestureSmoother(SMOOTHING_FRAMES)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}. Try --camera 1")

    voice = None
    if not args.no_voice:
        voice = VoiceListener(args.voice_model, openai_api_key=api_key)
        voice.start()

    prev = time.time()
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=DETECTION_CONFIDENCE,
        min_tracking_confidence=TRACKING_CONFIDENCE,
    ) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera frame not received, stopping.")
                break

            frame = cv2.flip(frame, 1)
            result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            now = time.time()
            gesture = None

            if result.multi_hand_landmarks:
                hand_lms = result.multi_hand_landmarks[0]
                lm = hand_lms.landmark
                gesture = smoother.update("main", classify(lm, fingers_up(lm)))
                ctl.update(lm, gesture, now)
                mp_draw.draw_landmarks(
                    frame, hand_lms, mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )
            else:
                smoother.prune(set())
                ctl.lost_hand()

            if voice:
                for command in voice.get_commands():
                    now = time.time()
                    if command.action == "resume":
                        if ctl.paused:
                            ctl.toggle_pause(now)
                        ctl.note("VOICE: controls resumed", now)
                    elif command.action == "pause":
                        if not ctl.paused:
                            ctl.toggle_pause(now)
                        ctl.note("VOICE: controls paused", now)
                    elif command.action == "open_app":
                        if not args.live:
                            ctl.note(f"VOICE TEST: would open {command.target}", now)
                        elif ctl.paused:
                            ctl.note("VOICE: say 'resume AURA' before opening apps", now)
                        else:
                            _, message = launch_application(command.target)
                            ctl.note(f"VOICE: {message}", now)
                    elif command.action == "scroll":
                        if ctl.paused:
                            ctl.note("VOICE: say 'resume AURA' before scrolling", now)
                        elif not args.live:
                            ctl.note(f"VOICE TEST: would scroll {command.direction}", now)
                        else:
                            amount = command.amount if command.direction == "up" else -command.amount
                            pyautogui.scroll(amount)
                            ctl.note(f"VOICE: scroll {command.direction}", now)
                    else:
                        ctl.note(f"HEARD: {command.transcript[:48]}", now)
                    if command.error:
                        voice.status = command.error
                        ctl.note(f"VOICE: {command.error}"[:70], now)

            fps = 1.0 / max(now - prev, 1e-6)
            prev = now
            draw_hud(frame, ctl, gesture, fps, now,
                     voice.status if voice else "disabled")
            cv2.imshow("AURA - Phase 2", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("p"):
                ctl.toggle_pause(now)

    cap.release()
    cv2.destroyAllWindows()
    if voice:
        voice.stop()


def main():
    parser = argparse.ArgumentParser(description="AURA Phase 2: gesture controls")
    parser.add_argument("--live", action="store_true", help="actually control the mouse (default is dry-run)")
    parser.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    parser.add_argument("--no-voice", action="store_true", help="disable voice commands")
    parser.add_argument("--voice-model", default="vosk-model-small-en-in-0.4",
                        help="path to the offline Vosk English (India) model folder")
    parser.add_argument("--openai", action="store_true",
                        help="use OpenAI for cloud transcription and command interpretation (requires API key)")
    args = parser.parse_args()

    try:
        run(args)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        if pyautogui is not None and isinstance(e, pyautogui.FailSafeException):
            print("Failsafe triggered (mouse hit a screen corner). AURA stopped.")
        else:
            raise


if __name__ == "__main__":
    main()
