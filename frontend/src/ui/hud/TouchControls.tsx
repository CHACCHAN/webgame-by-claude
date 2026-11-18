import { useEffect, useRef, useState, type PointerEvent } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useSettings } from '../../store/settings';
import { CAR_SPECS, singleRatio } from '../../game/vehicle/carSpecs';

type Held = { left: boolean; right: boolean; gas: boolean; brake: boolean; side: boolean };

/**
 * On-screen controls for phones and tablets during a race: a steering pad on the left (the half under the finger
 * steers; slide across to switch), accelerator, brake and handbrake on the right, shift buttons for MT, back on the
 * road, camera and pause at the top. Several fingers at once; the buttons feed `InputManager.touch`, ramped like the keys.
 */
export function TouchControls() {
  const autoShift = useSettings((s) => s.autoShift);
  const carId = gameHolder.game?.currentConfig?.carId;
  const shift = !autoShift && !!carId && !singleRatio(CAR_SPECS[carId]);
  // a tank: the right half of the screen aims its gun (a finger's drag), two buttons over the steering pad fire
  // it and take the gunner's sight up or down (a switch: a held button would cost the thumb that steers)
  const tank = !!carId && !!CAR_SPECS[carId].tank;
  const [scope, setScope] = useState(false);
  const [firing, setFiring] = useState(false);
  const aimFingers = useRef(new Map<number, { x: number; y: number }>());
  const held = useRef<Held>({ left: false, right: false, gas: false, brake: false, side: false });
  const [lit, setLit] = useState<Held>(held.current);
  const steerFingers = useRef(new Map<number, number>());

  const apply = () => {
    const input = gameHolder.game?.input;
    if (!input) return;
    const h = held.current;
    input.touch = { steer: (h.right ? 1 : 0) - (h.left ? 1 : 0), throttle: h.gas ? 1 : 0, brake: h.brake ? 1 : 0, handbrake: h.side, active: true };
    setLit({ ...h });
  };
  useEffect(() => {
    apply();
    return () => {
      const input = gameHolder.game?.input;
      if (input) input.touch = { steer: 0, throttle: 0, brake: 0, handbrake: false, active: false };
      if (input) input.touchGun = { dx: 0, dy: 0, scope: false, fire: false };
    };
  }, []);

  const aim = (e: PointerEvent<HTMLDivElement>, up = false) => {
    e.preventDefault();
    const fingers = aimFingers.current;
    if (up) {
      fingers.delete(e.pointerId);
      return;
    }
    const at = fingers.get(e.pointerId);
    if (e.type === 'pointerdown') e.currentTarget.setPointerCapture(e.pointerId);
    else if (at) {
      const gun = gameHolder.game?.input.touchGun;
      if (gun) {
        gun.dx += e.clientX - at.x;
        gun.dy += e.clientY - at.y;
      }
    }
    if (at || e.type === 'pointerdown') fingers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  };
  const fire = (on: boolean) => {
    const gun = gameHolder.game?.input.touchGun;
    if (gun) gun.fire = on;
    setFiring(on);
  };
  const sight = () => {
    const gun = gameHolder.game?.input.touchGun;
    if (!gun) return;
    gun.scope = !gun.scope;
    setScope(gun.scope);
  };

  // the steering pad: each finger on it steers to the side of the centre it is on
  const steer = (e: PointerEvent<HTMLDivElement>, up = false) => {
    e.preventDefault();
    if (up) steerFingers.current.delete(e.pointerId);
    else {
      if (e.type === 'pointerdown') e.currentTarget.setPointerCapture(e.pointerId);
      const r = e.currentTarget.getBoundingClientRect();
      steerFingers.current.set(e.pointerId, e.clientX - (r.left + r.width / 2));
    }
    const xs = [...steerFingers.current.values()];
    held.current.left = xs.some((x) => x < 0);
    held.current.right = xs.some((x) => x >= 0);
    apply();
  };
  const hold = (key: Exclude<keyof Held, 'left' | 'right'>) => ({
    onPointerDown: (e: PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      held.current[key] = true;
      apply();
    },
    onPointerUp: () => ((held.current[key] = false), apply()),
    onPointerCancel: () => ((held.current[key] = false), apply()),
    onLostPointerCapture: () => ((held.current[key] = false), apply()),
  });
  const tap = (fn: () => void) => ({
    onPointerDown: (e: PointerEvent<HTMLButtonElement>) => {
      e.preventDefault();
      fn();
    },
  });
  const pause = () => {
    const app = useApp.getState();
    if (app.paused) return;
    // an online race keeps running for everyone: only the menu opens
    if (app.mode !== 'online') gameHolder.game?.setPaused(true);
    app.set({ paused: true });
  };
  const press = (code: string) => gameHolder.game?.input.press(code);

  return (
    <div className="touch-controls" onContextMenu={(e) => e.preventDefault()}>
      {tank && (
        <div
          className="tc-aim"
          onPointerDown={(e) => aim(e)}
          onPointerMove={(e) => aimFingers.current.has(e.pointerId) && aim(e)}
          onPointerUp={(e) => aim(e, true)}
          onPointerCancel={(e) => aim(e, true)}
        />
      )}
      {tank && (
        <div className="tc-gun">
          <div className={scope ? 'tc-pedal sight on' : 'tc-pedal sight'} onPointerDown={(e) => (e.preventDefault(), sight())}>照準</div>
          <div
            className={firing ? 'tc-pedal fire on' : 'tc-pedal fire'}
            onPointerDown={(e) => (e.preventDefault(), e.currentTarget.setPointerCapture(e.pointerId), fire(true))}
            onPointerUp={() => fire(false)}
            onPointerCancel={() => fire(false)}
            onLostPointerCapture={() => fire(false)}
          >
            射撃
          </div>
        </div>
      )}
      <div className="tc-top">
        <button className="tc-btn" {...tap(() => press('KeyR'))} aria-label="back on the road">復帰</button>
        <button className="tc-btn" {...tap(() => press('KeyC'))} aria-label="camera">CAM</button>
        <button className="tc-btn" {...tap(pause)} aria-label="pause">II</button>
      </div>
      <div
        className="tc-steer"
        onPointerDown={(e) => steer(e)}
        onPointerMove={(e) => steerFingers.current.has(e.pointerId) && steer(e)}
        onPointerUp={(e) => steer(e, true)}
        onPointerCancel={(e) => steer(e, true)}
      >
        <div className={lit.left ? 'tc-half on' : 'tc-half'}>◀</div>
        <div className={lit.right ? 'tc-half on' : 'tc-half'}>▶</div>
      </div>
      <div className="tc-pedals">
        {shift && (
          <div className="tc-shift">
            <button className="tc-btn" {...tap(() => press('KeyE'))}>▲</button>
            <button className="tc-btn" {...tap(() => press('KeyQ'))}>▼</button>
          </div>
        )}
        <div className="tc-col">
          <div className={lit.side ? 'tc-pedal side on' : 'tc-pedal side'} {...hold('side')}>サイド</div>
          <div className={lit.brake ? 'tc-pedal brake on' : 'tc-pedal brake'} {...hold('brake')}>ブレーキ</div>
        </div>
        <div className={lit.gas ? 'tc-pedal gas on' : 'tc-pedal gas'} {...hold('gas')}>アクセル</div>
      </div>
    </div>
  );
}
