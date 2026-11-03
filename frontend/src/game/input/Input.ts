import { clamp } from '../util/math';
import type { VehicleInput } from '../vehicle/VehicleSim';

/**
 * Keyboard + gamepad + touch input with analogue-like smoothing for keys (and touch buttons) so that
 * steering on a keyboard or a phone is progressive instead of on/off.
 */
export class InputManager {
  private keys = new Set<string>();
  private pressed = new Set<string>();
  private steerKey = 0;
  private throttleKey = 0;
  private brakeKey = 0;
  gamepadConnected = false;
  lastDevice: 'keyboard' | 'gamepad' = 'keyboard';
  private prevPadButtons: boolean[] = [];
  private padPressed = new Set<number>();
  /** set by the touch overlay (ui/hud/TouchControls.tsx): held buttons, driven like the keys */
  touch = { steer: 0, throttle: 0, brake: 0, handbrake: false, active: false };

  constructor(private target: Window = window) {
    target.addEventListener('keydown', this.onDown);
    target.addEventListener('keyup', this.onUp);
    target.addEventListener('blur', this.onBlur);
  }

  dispose() {
    this.target.removeEventListener('keydown', this.onDown);
    this.target.removeEventListener('keyup', this.onUp);
    this.target.removeEventListener('blur', this.onBlur);
  }

  private onDown = (e: KeyboardEvent) => {
    if (e.repeat) return;
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) e.preventDefault();
    this.keys.add(e.code);
    this.pressed.add(e.code);
    this.lastDevice = 'keyboard';
  };
  private onUp = (e: KeyboardEvent) => {
    this.keys.delete(e.code);
  };
  private onBlur = () => {
    this.keys.clear();
  };

  isDown(...codes: string[]) {
    return codes.some((c) => this.keys.has(c));
  }

  /** true once per key press (consumed) */
  consume(...codes: string[]) {
    let hit = false;
    for (const c of codes) {
      if (this.pressed.has(c)) {
        this.pressed.delete(c);
        hit = true;
      }
    }
    return hit;
  }

  /** A press from the touch overlay (shift, camera): handled like that key's press. */
  press(code: string) {
    this.pressed.add(code);
  }

  consumePad(button: number) {
    if (this.padPressed.has(button)) {
      this.padPressed.delete(button);
      return true;
    }
    return false;
  }

  /** Call once per frame. */
  poll(dt: number, out: VehicleInput) {
    const t = this.touch.active ? this.touch : null;
    const left = this.isDown('ArrowLeft', 'KeyA') || (t ? t.steer < -0.5 : false);
    const right = this.isDown('ArrowRight', 'KeyD') || (t ? t.steer > 0.5 : false);
    const up = this.isDown('ArrowUp', 'KeyW') || (t ? t.throttle > 0.5 : false);
    const down = this.isDown('ArrowDown', 'KeyS') || (t ? t.brake > 0.5 : false);
    const target = (right ? 1 : 0) - (left ? 1 : 0);
    // keys ramp the steering; releasing returns faster
    const rate = target === 0 ? 7 : Math.sign(target) !== Math.sign(this.steerKey) ? 10 : 4.6;
    this.steerKey = clamp(this.steerKey + clamp(target - this.steerKey, -rate * dt, rate * dt), -1, 1);
    this.throttleKey = clamp(this.throttleKey + (up ? 8 : -12) * dt, 0, 1);
    this.brakeKey = clamp(this.brakeKey + (down ? 10 : -14) * dt, 0, 1);

    out.steer = this.steerKey;
    out.throttle = this.throttleKey;
    out.brake = this.brakeKey;
    out.handbrake = this.isDown('Space') || !!t?.handbrake;
    out.shiftUp = this.consume('KeyE', 'ShiftRight');
    out.shiftDown = this.consume('KeyQ', 'ControlRight');

    // gamepad (standard mapping)
    const pads = typeof navigator !== 'undefined' && navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = Array.from(pads ?? []).find((p) => p && p.connected) ?? null;
    this.gamepadConnected = !!pad;
    if (pad) {
      const buttons = pad.buttons.map((b) => b.pressed);
      buttons.forEach((b, i) => {
        if (b && !this.prevPadButtons[i]) this.padPressed.add(i);
      });
      this.prevPadButtons = buttons;
      const sx = pad.axes[0] ?? 0;
      const dead = 0.12;
      const steer = Math.abs(sx) < dead ? 0 : Math.sign(sx) * ((Math.abs(sx) - dead) / (1 - dead)) ** 1.4;
      const rt = pad.buttons[7]?.value ?? 0, lt = pad.buttons[6]?.value ?? 0;
      const usingPad = Math.abs(steer) > 0.02 || rt > 0.05 || lt > 0.05 || buttons.some(Boolean);
      if (usingPad) this.lastDevice = 'gamepad';
      if (this.lastDevice === 'gamepad') {
        out.steer = steer;
        out.throttle = Math.max(rt, pad.buttons[0]?.pressed ? 1 : 0);
        out.brake = Math.max(lt, pad.buttons[2]?.pressed ? 1 : 0);
        out.handbrake = !!(pad.buttons[1]?.pressed || pad.buttons[5]?.pressed);
        out.shiftUp = out.shiftUp || this.consumePad(3);
        out.shiftDown = out.shiftDown || this.consumePad(4);
      }
    }
    return out;
  }

  /** Menu-style edge triggers shared by keyboard & pad. */
  menuPressed(action: 'pause' | 'reset' | 'camera' | 'confirm') {
    switch (action) {
      case 'pause':
        return this.consume('Escape', 'KeyP') || this.consumePad(9);
      case 'reset':
        return this.consume('KeyR') || this.consumePad(8);
      case 'camera':
        return this.consume('KeyC') || this.consumePad(12);
      case 'confirm':
        return this.consume('Enter') || this.consumePad(0);
    }
  }

  clearPressed() {
    this.pressed.clear();
    this.padPressed.clear();
  }
}
