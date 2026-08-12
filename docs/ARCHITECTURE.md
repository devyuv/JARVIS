# Architecture

## Process model

Two separate processes, connected by one local WebSocket:

1. **Backend (`backend/main.py`)** — a single Python asyncio event loop running:
   - `wake_word.py` — mic → openWakeWord → `on_wake()` callback
   - `stt.py` — mic → faster-whisper (or Google) → text
   - `llm_brain.py` — text → Claude/OpenAI tool-calling loop → reply text
   - `tts.py` — reply text → speaker audio
   - `gesture_tracker.py` — webcam → MediaPipe Hands → classified gesture events
   - `websocket_server.py` — broadcasts gesture/status/transcript events to any connected HUD

2. **Frontend (`frontend/`)** — a React + Vite app rendering the Three.js HUD, connected to the backend's WebSocket as a client.

They're separate processes deliberately: the HUD should stay responsive (60fps render loop) even while the backend is busy waiting on an LLM API call or transcribing audio, and either half can be restarted independently during development.

## Data flow: a conversation turn

```
mic audio → wake_word.py (openWakeWord)
              │ detects "hey jarvis"
              ▼
        hud.status("listening")  ──────────────▶ HUD shows LISTENING pill
              │
        stt.transcribe_from_mic() (Whisper)
              │ text
              ▼
        hud.transcript("user", text) ──────────▶ HUD appends to transcript panel
              │
        hud.status("thinking")  ───────────────▶ HUD shows PROCESSING pill, core spins faster
              │
        llm_brain.think(text)
              │  Claude decides to call a tool, e.g. get_weather(city="Austin")
              │  skills/weather_skill.py executes it, returns a string
              │  Claude incorporates the result into a final reply
              ▼ reply text
        hud.transcript("assistant", reply)
              │
        tts.speak(reply)
              │ on_speaking_change(True) ──────▶ hud.status("speaking"), waveform animates
              │ ... audio plays ...
              │ on_speaking_change(False) ─────▶ hud.status("idle")
```

## Data flow: gesture stream

```
webcam frame (≈30fps)
     │
     ▼
gesture_tracker.py: MediaPipe Hands → landmarks
     │
     ▼
classify into { pinch | palm_rotate | two_hand_tilt | fist | swipe }
     │
     ▼
hud.gesture(event) → WebSocket broadcast → frontend useWebSocket hook
     │
     ▼
gestureRef.current mutated (no React re-render)
     │
     ▼
ArcReactor.jsx useFrame() reads gestureRef every render frame, applies to mesh transforms
```

Gesture data intentionally bypasses React state and lands in a plain mutable ref that the Three.js render loop reads directly. Routing 30 events/sec through `setState` would re-render the whole HUD tree (including the transcript and status panels) on every frame; reading a ref inside `useFrame` costs nothing extra since R3F is already re-rendering the canvas every frame regardless.

## Why a plugin system for skills

`llm_brain.py` never imports a specific skill by name. `discover_skills()` walks `backend/skills/`, imports every module, and instantiates any `BaseSkill` subclass it finds. Each skill's `to_tool_schema()` produces the JSON schema Claude/OpenAI need for function calling. Adding a capability is: write a class, drop the file in the folder, restart. Removing one is: delete the file.

## Extending the gesture vocabulary

Gestures are classified per-frame in `gesture_tracker.py`'s `_classify_single_hand` / `_classify_two_hands`. To add a new gesture:

1. Compute whatever landmark geometry you need (MediaPipe gives you 21 3D landmarks per hand).
2. Append a `{"type": "your_gesture", ...}` dict to the returned events list.
3. Handle `g.type === "your_gesture"` in `App.jsx`'s `handleGesture`, updating `gestureRef.current`.
4. Read that ref field inside `ArcReactor.jsx`'s `useFrame` to drive a transform.
