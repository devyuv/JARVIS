import React from "react";

const STATUS_LABELS = {
  idle: "STANDBY",
  listening: "LISTENING",
  thinking: "PROCESSING",
  speaking: "RESPONDING",
};

export function StatusPanel({ status, connected, hardware }) {
  return (
    <div className="panel panel--status">
      <div className="panel__label">STATUS</div>
      <div className={`status__pill status__pill--${status}`}>{STATUS_LABELS[status] ?? "—"}</div>
      <div className="status__row">
        <span>LINK</span>
        <span className={connected ? "status__ok" : "status__warn"}>
          {connected ? "ONLINE" : "RECONNECTING"}
        </span>
      </div>
      <div className="status__row">
        <span>MIC</span>
        <span className={hardware.mic ? "status__ok" : "status__warn"}>
          {hardware.mic ? "READY" : "OFFLINE"}
        </span>
      </div>
      <div className="status__row">
        <span>CAM</span>
        <span className={hardware.camera ? "status__ok" : "status__warn"}>
          {hardware.camera ? "READY" : "OFFLINE"}
        </span>
      </div>
    </div>
  );
}

export function GestureLegendPanel() {
  const rows = [
    ["PINCH", "ZOOM"],
    ["ROTATE WRIST", "ROTATE MODEL"],
    ["TWO-HAND SPREAD", "TILT"],
    ["FIST", "GRAB / SELECT"],
    ["SWIPE", "DISMISS / NEXT"],
  ];
  return (
    <div className="panel panel--legend">
      <div className="panel__label">GESTURES</div>
      {rows.map(([gesture, action]) => (
        <div className="legend__row" key={gesture}>
          <span className="legend__gesture">{gesture}</span>
          <span className="legend__action">{action}</span>
        </div>
      ))}
    </div>
  );
}
