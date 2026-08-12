import React, { useEffect, useRef } from "react";

const BAR_COUNT = 28;

/**
 * Purely decorative animated waveform tied to `active` (true while the
 * assistant is listening or speaking). Doesn't need real audio-level
 * data from the backend — a randomized bar animation reads as "voice
 * activity" at a glance, which is all the HUD needs to communicate.
 */
export default function Waveform({ active }) {
  const barsRef = useRef([]);

  useEffect(() => {
    let raf;
    const animate = () => {
      barsRef.current.forEach((bar) => {
        if (!bar) return;
        const target = active ? 0.15 + Math.random() * 0.85 : 0.05 + Math.random() * 0.05;
        bar.style.transform = `scaleY(${target})`;
      });
      raf = requestAnimationFrame(() => setTimeout(animate, 80));
    };
    animate();
    return () => cancelAnimationFrame(raf);
  }, [active]);

  return (
    <div className={`waveform ${active ? "waveform--active" : ""}`}>
      {Array.from({ length: BAR_COUNT }).map((_, i) => (
        <span key={i} ref={(el) => (barsRef.current[i] = el)} className="waveform__bar" />
      ))}
    </div>
  );
}
