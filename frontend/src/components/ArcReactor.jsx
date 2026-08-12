import React, { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";

const CYAN = "#4ff3ff";
const BLUE = "#3a7bff";

/**
 * The rotating ring core. Gesture deltas are applied directly to the
 * mesh transforms each frame rather than through React state, so a
 * 30fps gesture stream never triggers a React re-render storm.
 */
function ReactorCore({ gestureRef, statusRef }) {
  const coreRef = useRef();
  const ring1 = useRef();
  const ring2 = useRef();
  const ring3 = useRef();
  const scaleTarget = useRef(1);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const g = gestureRef.current;
    const status = statusRef.current;

    // ambient rotation, speeds up while "thinking" or "speaking"
    const busy = status === "thinking" || status === "speaking";
    const speedMul = busy ? 2.4 : 1;
    if (ring1.current) ring1.current.rotation.z += delta * 0.25 * speedMul;
    if (ring2.current) ring2.current.rotation.z -= delta * 0.18 * speedMul;
    if (ring3.current) ring3.current.rotation.x += delta * 0.12 * speedMul;

    // pinch -> zoom (scale)
    if (g.pinchDistance != null) {
      scaleTarget.current = THREE.MathUtils.clamp(1.6 - g.pinchDistance * 0.7, 0.5, 2.2);
    }
    if (coreRef.current) {
      const s = THREE.MathUtils.lerp(coreRef.current.scale.x, scaleTarget.current, 0.15);
      coreRef.current.scale.set(s, s, s);
      coreRef.current.rotation.y += delta * 0.3;

      // palm rotate -> extra y-rotation impulse
      if (g.rotateImpulse) {
        coreRef.current.rotation.y += g.rotateImpulse;
        g.rotateImpulse = 0;
      }
      // two-hand tilt -> tilt on x axis, springs back toward 0
      const tiltTarget = g.tilt || 0;
      coreRef.current.rotation.x = THREE.MathUtils.lerp(coreRef.current.rotation.x, tiltTarget, 0.1);
    }

    // idle pulse
    const pulse = 1 + Math.sin(t * 2) * (busy ? 0.06 : 0.02);
    if (coreRef.current) coreRef.current.children[0]?.scale.setScalar(pulse);
  });

  return (
    <group ref={coreRef}>
      <mesh>
        <icosahedronGeometry args={[1, 1]} />
        <meshBasicMaterial color={CYAN} wireframe transparent opacity={0.85} />
      </mesh>
      <mesh ref={ring1} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.6, 0.02, 8, 100]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.7} />
      </mesh>
      <mesh ref={ring2} rotation={[Math.PI / 2.3, 0.3, 0]}>
        <torusGeometry args={[2.05, 0.015, 8, 100]} />
        <meshBasicMaterial color={BLUE} transparent opacity={0.5} />
      </mesh>
      <mesh ref={ring3}>
        <torusGeometry args={[2.5, 0.008, 8, 100]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.25} />
      </mesh>
      <pointLight color={CYAN} intensity={4} distance={6} />
    </group>
  );
}

function Particles({ count = 400 }) {
  const points = useRef();
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 3 + Math.random() * 4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
  }, [count]);

  useFrame((_, delta) => {
    if (points.current) points.current.rotation.y += delta * 0.02;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial color={BLUE} size={0.02} transparent opacity={0.5} />
    </points>
  );
}

/**
 * gestureRef: mutable ref updated by App.jsx from incoming WS gesture
 * events — { pinchDistance, rotateImpulse, tilt }. Kept outside React
 * state deliberately to avoid re-rendering the whole tree at gesture
 * frame rate.
 */
export default function ArcReactor({ gestureRef, statusRef }) {
  return (
    <Canvas camera={{ position: [0, 0, 6], fov: 50 }} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={0.2} />
      <ReactorCore gestureRef={gestureRef} statusRef={statusRef} />
      <Particles />
      <OrbitControls
        enablePan={false}
        enableZoom={true}
        minDistance={3}
        maxDistance={10}
        autoRotate={false}
      />
    </Canvas>
  );
}
