"""
Reads the webcam via OpenCV, runs MediaPipe Hands on each frame, and
classifies landmarks into the gesture vocabulary the HUD understands:

  pinch          -> {"type": "pinch", "distance": 0..1}            zoom
  palm_rotate    -> {"type": "palm_rotate", "angle_delta": degrees} rotate model
  two_hand_tilt  -> {"type": "two_hand_tilt", "spread_delta": 0..1} tilt
  fist           -> {"type": "fist"}                                grab/select
  swipe          -> {"type": "swipe", "direction": "left"|"right"}  dismiss/next

Each event is handed to `on_gesture(event: dict)`, which main.py wires
to the WebSocket broadcaster. If no webcam is found, `available` is
False and `track_forever()` is a no-op, so the HUD just falls back to
mouse-driven OrbitControls on the frontend.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import deque
from typing import Awaitable, Callable

logger = logging.getLogger("jarvis.gesture")

GestureCallback = Callable[[dict], Awaitable[None]]

# Landmark indices (MediaPipe Hands)
THUMB_TIP, INDEX_TIP, WRIST, MIDDLE_MCP = 4, 8, 0, 9


class GestureTracker:
    def __init__(self, on_gesture: GestureCallback, camera_index: int = 0, fps_target: int = 30):
        self.on_gesture = on_gesture
        self.camera_index = camera_index
        self.frame_interval = 1.0 / fps_target
        self.available = False
        self._cap = None
        self._hands = None
        self._prev_wrist_angle: float | None = None
        self._prev_two_hand_spread: float | None = None
        self._wrist_x_history: deque[float] = deque(maxlen=8)
        self._init_hardware()

    def _init_hardware(self) -> None:
        try:
            import cv2

            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                logger.warning("No webcam found at index %d. Gesture control disabled.", self.camera_index)
                return
            self._cap = cap

            import mediapipe as mp

            self._mp_hands = mp.solutions.hands
            self._hands = self._mp_hands.Hands(
                model_complexity=0,  # lightest model, favors latency
                max_num_hands=2,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            )
            self.available = True
            logger.info("Gesture tracker ready (camera %d).", self.camera_index)
        except Exception as exc:
            logger.warning("Gesture tracker init failed (%s). Disabled.", exc)

    async def track_forever(self) -> None:
        if not self.available:
            logger.info("Gesture tracking not available; skipping.")
            return

        loop = asyncio.get_event_loop()
        while True:
            start = time.monotonic()
            frame_result = await loop.run_in_executor(None, self._read_and_process_frame)
            if frame_result:
                for event in frame_result:
                    await self.on_gesture(event)
            elapsed = time.monotonic() - start
            await asyncio.sleep(max(0.0, self.frame_interval - elapsed))

    def _read_and_process_frame(self) -> list[dict]:
        import cv2

        ok, frame = self._cap.read()
        if not ok:
            return []

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        events: list[dict] = []
        if not results.multi_hand_landmarks:
            self._prev_wrist_angle = None
            self._prev_two_hand_spread = None
            return events

        hands_lm = results.multi_hand_landmarks

        if len(hands_lm) == 1:
            lm = hands_lm[0].landmark
            events.extend(self._classify_single_hand(lm))
        elif len(hands_lm) == 2:
            events.extend(self._classify_two_hands(hands_lm[0].landmark, hands_lm[1].landmark))

        return events

    # -- classification helpers ---------------------------------------------
    def _classify_single_hand(self, lm) -> list[dict]:
        events = []

        # Pinch: thumb tip <-> index tip distance, normalized by hand size.
        hand_size = _dist(lm[WRIST], lm[MIDDLE_MCP]) or 1e-6
        pinch_dist = _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / hand_size
        events.append({"type": "pinch", "distance": round(min(pinch_dist, 2.0), 3)})

        # Fist: all fingertips curled close to the palm.
        if self._is_fist(lm):
            events.append({"type": "fist"})

        # Palm rotate: angle of the wrist->middle-mcp vector, tracked as a delta.
        angle = math.degrees(math.atan2(lm[MIDDLE_MCP].y - lm[WRIST].y, lm[MIDDLE_MCP].x - lm[WRIST].x))
        if self._prev_wrist_angle is not None:
            delta = _angle_delta(self._prev_wrist_angle, angle)
            if abs(delta) > 1.0:
                events.append({"type": "palm_rotate", "angle_delta": round(delta, 2)})
        self._prev_wrist_angle = angle

        # Swipe: fast horizontal wrist movement over the last few frames.
        self._wrist_x_history.append(lm[WRIST].x)
        swipe = self._detect_swipe()
        if swipe:
            events.append({"type": "swipe", "direction": swipe})

        return events

    def _classify_two_hands(self, lm_a, lm_b) -> list[dict]:
        spread = _dist(lm_a[WRIST], lm_b[WRIST])
        events = []
        if self._prev_two_hand_spread is not None:
            delta = spread - self._prev_two_hand_spread
            if abs(delta) > 0.01:
                events.append({"type": "two_hand_tilt", "spread_delta": round(delta, 3)})
        self._prev_two_hand_spread = spread
        return events

    @staticmethod
    def _is_fist(lm) -> bool:
        tips = [8, 12, 16, 20]
        mcp = [5, 9, 13, 17]
        curled = sum(1 for t, m in zip(tips, mcp) if lm[t].y > lm[m].y)
        return curled >= 3

    def _detect_swipe(self) -> str | None:
        if len(self._wrist_x_history) < self._wrist_x_history.maxlen:
            return None
        delta = self._wrist_x_history[-1] - self._wrist_x_history[0]
        if abs(delta) > 0.35:
            self._wrist_x_history.clear()
            return "right" if delta > 0 else "left"
        return None


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _angle_delta(prev: float, curr: float) -> float:
    """Shortest signed angular difference, handling the -180/180 wraparound."""
    diff = curr - prev
    return (diff + 180) % 360 - 180
