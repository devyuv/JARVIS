import React, { useCallback, useRef, useState } from "react";
import ArcReactor from "./components/ArcReactor.jsx";
import Waveform from "./components/Waveform.jsx";
import Transcript from "./components/Transcript.jsx";
import { StatusPanel, GestureLegendPanel } from "./components/HUDPanels.jsx";
import { useWebSocket } from "./hooks/useWebSocket.js";

export default function App() {
  const [status, setStatus] = useState("idle");
  const [hardware, setHardware] = useState({ mic: false, camera: false });
  const [lines, setLines] = useState([]);

  // Gesture data lives in a ref, not state — ArcReactor reads it every
  // animation frame directly, so 30fps gesture events never cause a
  // React re-render of the whole HUD.
  const gestureRef = useRef({ pinchDistance: null, rotateImpulse: 0, tilt: 0 });
  const statusRef = useRef("idle");

  const handleGesture = useCallback((g) => {
    const state = gestureRef.current;
    if (g.type === "pinch") state.pinchDistance = g.distance;
    if (g.type === "palm_rotate") state.rotateImpulse += (g.angle_delta * Math.PI) / 180;
    if (g.type === "two_hand_tilt") {
      state.tilt = Math.max(-0.6, Math.min(0.6, state.tilt + g.spread_delta * 2));
    }
    // "fist" and "swipe" are momentary — surfaced via a CSS pulse on the core
    // in a future pass; the event still arrives here for that hook-up.
  }, []);

  const handleStatus = useCallback((d) => {
    statusRef.current = d.state;
    setStatus(d.state);
  }, []);

  const handleTranscript = useCallback((d) => {
    setLines((prev) => [...prev, d]);
  }, []);

  const handleHardware = useCallback((d) => setHardware(d), []);

  const { connected } = useWebSocket({
    gesture: handleGesture,
    status: handleStatus,
    transcript_final: handleTranscript,
    hardware: handleHardware,
  });

  const active = status === "listening" || status === "speaking";

  return (
    <div className="hud">
      <div className="hud__scanline" />
      <header className="hud__header">
        <span className="hud__title">J.A.R.V.I.S.</span>
        <span className="hud__subtitle">DESKTOP INTERFACE — v0.1</span>
      </header>

      <div className="hud__core">
        <ArcReactor gestureRef={gestureRef} statusRef={statusRef} />
      </div>

      <aside className="hud__left">
        <StatusPanel status={status} connected={connected} hardware={hardware} />
        <GestureLegendPanel />
      </aside>

      <aside className="hud__right">
        <Transcript lines={lines} />
      </aside>

      <footer className="hud__footer">
        <Waveform active={active} />
      </footer>

      <div className="hud__bracket hud__bracket--tl" />
      <div className="hud__bracket hud__bracket--tr" />
      <div className="hud__bracket hud__bracket--bl" />
      <div className="hud__bracket hud__bracket--br" />
    </div>
  );
}
