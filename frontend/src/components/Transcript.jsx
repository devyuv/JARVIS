import React, { useEffect, useRef } from "react";

export default function Transcript({ lines }) {
  const endRef = useRef();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines]);

  return (
    <div className="panel panel--transcript">
      <div className="panel__label">TRANSCRIPT</div>
      <div className="transcript__scroll">
        {lines.length === 0 && <div className="transcript__empty">Say "Hey Jarvis" to begin.</div>}
        {lines.map((line, i) => (
          <div key={i} className={`transcript__line transcript__line--${line.role}`}>
            <span className="transcript__role">{line.role === "user" ? "YOU" : "JARVIS"}</span>
            <span className="transcript__text">{line.text}</span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
