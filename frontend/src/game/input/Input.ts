import { clamp } from '../util/math';
import type { VehicleInput } from '../vehicle/VehicleSim';

/**
 * What the player's hands ask of a tank's gun in one frame (`pollGun`): the sight moved by `dx` to the right and
 * `dy` down (rad at the naked eye: the game divides by the sight's magnification), the gunner's sight, the trigger,
 * the turret back to the front, a step of magnification (+1 higher, −1 lower).
 */
export interface GunHands {
  dx: number;
  dy: number;
  scope: boolean;
  fire: boolean;
  recentre: boolean;
  zoom: number;
}

export const emptyHands = (): GunHands => ({ dx: 0, dy: 0, scope: false, fire: false, recentre: false, zoom: 0 });

/** radians of sight per count of mouse movement, per pixel of a finger's drag, and per second of a pad's stick held over */
const MOUSE_AIM = 0.0022;
const TOUCH_AIM = 0.005;
const PAD_AIM = 1.7;

/**
 * Keyboard + gamepad + touch input with analogue-like smoothing for keys (and touch buttons) so that
 * steering on a keyboard or a phone is progressive instead of on/off.
 *
 * A tank's gun (`gunMode`, set by the game while the player drives one): the mouse while the pointer is locked to
 * the page (movement = the sight, left button = fire, right button held = the gunner's sight, middle = turret to
 * the front, wheel = magnification); a pad's right stick, RT = fire, LT = sight, R3 = front, d-pad left / right =
 * magnification, and the pad then drives with the left stick alone (up = throttle, down = brake) or A / X, since
 * the triggers are the gun's; the touch overlay through `touchGun`.
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
  /** the player drives a tank: the pad's triggers and right stick are the gun's */
  gunMode = false;
  /** set by the touch overlay: a finger's drag since the last frame (px), the two buttons */
  touchGun = { dx: 0, dy: 0, scope: false, fire: false, shot: false };
  /** (`shot`, here and above: the trigger was pulled since the last frame, however briefly: a tap or a click
   * shorter than a frame fires too) */
  private mouse = { dx: 0, dy: 0, fire: false, shot: false, scope: false, recentre: false, wheel: 0 };

  constructor(private target: Window = window) {
    target.addEventListener('keydown', this.onDown);
    target.addEventListener('keyup', this.onUp);
    target.addEventListener('blur', this.onBlur);
    target.addEventListener('mousemove', this.onMouseMove);
    target.addEventListener('mousedown', this.onMouseDown);
    target.addEventListener('mouseup', this.onMouseUp);
    target.addEventListener('wheel', this.onWheel, { passive: true });
  }

  dispose() {
    this.target.removeEventListener('keydown', this.onDown);
    this.target.removeEventListener('keyup', this.onUp);
    this.target.removeEventListener('blur', this.onBlur);
    this.target.removeEventListener('mousemove', this.onMouseMove);
    this.target.removeEventListener('mousedown', this.onMouseDown);
    this.target.removeEventListener('mouseup', this.onMouseUp);
    this.target.removeEventListener('wheel', this.onWheel);
  }

  /** the mouse is the gun's only while the pointer is locked to the page (the HUD asks for it: ui/hud/GunSight.tsx) */
  private get locked() {
    return this.gunMode && typeof document !== 'undefined' && !!document.pointerLockElement;
  }
  private onMouseMove = (e: MouseEvent) => {
    if (!this.locked) return;
    this.mouse.dx += e.movementX;
    this.mouse.dy += e.movementY;
  };
  private onMouseDown = (e: MouseEvent) => {
    if (!this.locked) return;
    if (e.button === 0) this.mouse.fire = this.mouse.shot = true;
    else if (e.button === 2) this.mouse.scope = true;
    else if (e.button === 1) this.mouse.recentre = true;
  };
  private onMouseUp = (e: MouseEvent) => {
    if (e.button === 0) this.mouse.fire = false;
    else if (e.button === 2) this.mouse.scope = false;
  };
  private onWheel = (e: WheelEvent) => {
    if (this.locked && e.deltaY) this.mouse.wheel += e.deltaY < 0 ? 1 : -1;
  };

  /** Call once per frame while the player drives a tank: what its hands ask of the gun. */
  pollGun(dt: number, out: GunHands) {
    const m = this.mouse;
    if (!this.locked) m.fire = m.shot = m.scope = false;
    out.dx = m.dx * MOUSE_AIM;
    out.dy = m.dy * MOUSE_AIM;
    out.scope = m.scope;
    out.fire = m.fire || m.shot;
    out.recentre = m.recentre;
    out.zoom = Math.sign(m.wheel);
    m.dx = m.dy = m.wheel = 0;
    m.recentre = m.shot = false;
    const t = this.touchGun;
    out.dx += t.dx * TOUCH_AIM;
    out.dy += t.dy * TOUCH_AIM;
    t.dx = t.dy = 0;
    out.scope ||= t.scope;
    out.fire ||= t.fire || t.shot;
    t.shot = false;
    const pads = typeof navigator !== 'undefined' && navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = Array.from(pads ?? []).find((p) => p && p.connected) ?? null;
    if (pad && this.lastDevice === 'gamepad') {
      const stick = (v: number) => (Math.abs(v) < 0.15 ? 0 : Math.sign(v) * ((Math.abs(v) - 0.15) / 0.85) ** 1.6);
      out.dx += stick(pad.axes[2] ?? 0) * PAD_AIM * dt;
      out.dy += stick(pad.axes[3] ?? 0) * PAD_AIM * dt;
      out.scope ||= (pad.buttons[6]?.value ?? 0) > 0.3;
      out.fire ||= (pad.buttons[7]?.value ?? 0) > 0.5;
      out.recentre ||= this.consumePad(10);
      if (this.consumePad(15)) out.zoom = 1;
      if (this.consumePad(14)) out.zoom = -1;
    }
    return out;
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
        // (a tank: the triggers are the gun's; the left stick drives, up for the throttle and down for the brake)
        const sy = this.gunMode ? (pad.axes[1] ?? 0) : 0;
        const push = (v: number) => (v < dead ? 0 : (v - dead) / (1 - dead));
        out.throttle = Math.max(this.gunMode ? push(-sy) : rt, pad.buttons[0]?.pressed ? 1 : 0);
        out.brake = Math.max(this.gunMode ? push(sy) : lt, pad.buttons[2]?.pressed ? 1 : 0);
        out.handbrake = !!(pad.buttons[1]?.pressed || pad.buttons[5]?.pressed);
        out.shiftUp = out.shiftUp || this.consumePad(3);
        out.shiftDown = out.shiftDown || this.consumePad(4);
      }
    }
    return out;
  }

  /** Menu-style edge triggers shared by keyboard & pad. */
  menuPressed(action: 'pause' | 'reset' | 'camera' | 'confirm' | 'horn') {
    switch (action) {
      case 'pause':
        return this.consume('Escape', 'KeyP') || this.consumePad(9);
      case 'reset':
        return this.consume('KeyR') || this.consumePad(8);
      case 'camera':
        return this.consume('KeyC') || this.consumePad(12);
      case 'confirm':
        return this.consume('Enter') || this.consumePad(0);
      case 'horn':
        return this.consume('KeyH') || this.consumePad(11);
    }
  }

  clearPressed() {
    this.pressed.clear();
    this.padPressed.clear();
  }
}
