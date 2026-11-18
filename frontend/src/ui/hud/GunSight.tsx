import { useEffect, useRef } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';

/** the gun counts as laid when it is this close to its line (rad: a tenth of a degree) */
const LAID = 0.0018;

/**
 * A tank's gun on the HUD (`game.hud.gun`; the DOM is written every frame, no React state).
 *
 * Driving views: two marks in the scene. The cross is where the line of sight ends (what the mouse moves); the
 * ring is where the round would land (the gun, laid after the sight at its real rate): green on the cross with a
 * round in, amber while it still travels, and its rim fills as the next round is loaded. Under the cross the range
 * the fire control works with and the rounds left.
 * The gunner's sight (right button held, LT, the phone's 照準): the picture is the sight's, through a round field
 * stop, with a plain reticle: a centre dot in a broken cross and lead ticks; the same figures at its foot.
 *
 * The mouse is the gun's only while the pointer is locked to the page: a click in the race takes it (never in a
 * menu: this component is there only in a race), the pause menu and the end of the race give it back. A browser
 * keeps Esc for itself while the pointer is locked and only lets it go: that Esc is taken as the pause it meant.
 */
export function GunSight({ touch }: { touch: boolean }) {
  const paused = useApp((s) => s.paused);
  const refs = {
    root: useRef<HTMLDivElement>(null),
    cross: useRef<HTMLElement>(null),
    mark: useRef<HTMLDivElement>(null),
    load: useRef<SVGCircleElement>(null),
    read: useRef<HTMLDivElement>(null),
    range: useRef<HTMLElement>(null),
    ammo: useRef<HTMLElement>(null),
    state: useRef<HTMLSpanElement>(null),
    zoom: useRef<HTMLElement>(null),
    turret: useRef<SVGGElement>(null),
  };

  // ---- the pointer
  useEffect(() => {
    if (touch) return;
    const racing = () => {
      const app = useApp.getState();
      return app.screen === 'race' && !app.paused && (app.phase === 'countdown' || app.phase === 'racing');
    };
    const onDown = () => {
      if (!racing() || document.pointerLockElement) return;
      try {
        // (a promise in newer browsers: a refusal is no error to show)
        void (document.body.requestPointerLock() as unknown as Promise<void> | undefined)?.catch?.(() => undefined);
      } catch {
        // (no pointer lock here: the gun stays where it is)
      }
    };
    const onLock = () => {
      const locked = !!document.pointerLockElement;
      refs.root.current?.classList.toggle('free', !locked);
      // let go while the race runs: the browser's own Esc (it never reaches the page as a key)
      if (!locked && racing() && document.hasFocus()) {
        const app = useApp.getState();
        if (app.mode !== 'online') gameHolder.game?.setPaused(true);
        app.set({ paused: true });
      }
    };
    const onMenu = (e: Event) => e.preventDefault();
    window.addEventListener('mousedown', onDown);
    document.addEventListener('pointerlockchange', onLock);
    window.addEventListener('contextmenu', onMenu);
    refs.root.current?.classList.toggle('free', !document.pointerLockElement);
    return () => {
      window.removeEventListener('mousedown', onDown);
      document.removeEventListener('pointerlockchange', onLock);
      window.removeEventListener('contextmenu', onMenu);
      if (document.pointerLockElement) document.exitPointerLock();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [touch]);
  // (the pause menu needs the pointer)
  useEffect(() => {
    if (paused && document.pointerLockElement) document.exitPointerLock();
  }, [paused]);

  // ---- the figures, every frame
  useEffect(() => {
    let raf = 0;
    const last = { range: '', ammo: '', state: '', zoom: '' };
    const text = (el: HTMLElement | null, key: keyof typeof last, v: string) => {
      if (el && last[key] !== v) el.textContent = last[key] = v;
    };
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const g = gameHolder.game?.hud.gun, root = refs.root.current;
      if (!root) return;
      root.classList.toggle('none', !g);
      if (!g) return;
      const w = root.clientWidth, h = root.clientHeight;
      root.classList.toggle('scope', g.scope);
      const ready = g.loaded >= 1, laid = g.off < LAID;
      root.classList.toggle('ready', ready && laid);
      root.classList.toggle('empty', g.ammo <= 0);
      const cross = refs.cross.current, mark = refs.mark.current, read = refs.read.current;
      // (through the sight the line of sight is the middle of the picture)
      const sx = g.scope ? 0.5 : g.sight.x, sy = g.scope ? 0.5 : g.sight.y;
      if (cross) {
        cross.style.opacity = g.scope || !g.sight.on ? '0' : '1';
        cross.style.transform = `translate(${(sx * w).toFixed(1)}px, ${(sy * h).toFixed(1)}px)`;
      }
      if (mark) {
        mark.style.opacity = g.mark.on ? '1' : '0';
        mark.style.transform = `translate(${(g.mark.x * w).toFixed(1)}px, ${(g.mark.y * h).toFixed(1)}px)`;
      }
      if (read && !g.scope) read.style.transform = `translate(${(sx * w).toFixed(1)}px, ${(sy * h).toFixed(1)}px)`;
      else if (read) read.style.transform = '';
      refs.load.current?.setAttribute('stroke-dashoffset', (100 - 100 * Math.min(1, Math.max(0, g.loaded))).toFixed(1));
      text(refs.range.current, 'range', g.lased ? `${Math.round(g.range / 10) * 10}` : '----');
      text(refs.ammo.current, 'ammo', String(g.ammo));
      text(refs.state.current, 'state', ready ? (laid ? '発射可' : '照準中') : g.ammo <= 0 ? '弾切れ' : `装填 ${g.reload.toFixed(1)}`);
      text(refs.zoom.current, 'zoom', g.scope ? `×${g.zoom}` : '');
      refs.turret.current?.setAttribute('transform', `rotate(${((-g.bearing * 180) / Math.PI).toFixed(1)})`);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={touch ? 'gun-hud none' : 'gun-hud none free'} ref={refs.root}>
      <div className="gun-scope" aria-hidden>
        <svg viewBox="-100 -100 200 200" preserveAspectRatio="xMidYMid meet">
          <circle className="gs-dot" r="0.45" />
          <path className="gs-line" d="M-60 0H-6M6 0H60M0 6V60M0 -6V-18" />
          <path className="gs-tick" d="M-50 -1.6V1.6M-40 -2.4V2.4M-30 -1.6V1.6M-20 -2.4V2.4M-10 -1.6V1.6M10 -1.6V1.6M20 -2.4V2.4M30 -1.6V1.6M40 -2.4V2.4M50 -1.6V1.6M-2.4 20H2.4M-1.6 30H1.6M-2.4 40H2.4M-1.6 50H1.6" />
        </svg>
      </div>
      <i className="gun-cross" ref={refs.cross} />
      <div className="gun-mark" ref={refs.mark}>
        <svg viewBox="-20 -20 40 40">
          <circle className="gm-ring" r="13" />
          <circle className="gm-load" r="13" pathLength="100" strokeDasharray="100" strokeDashoffset="0" transform="rotate(-90)" ref={refs.load} />
        </svg>
      </div>
      <div className="gun-read" ref={refs.read}>
        <span className="gr-state" ref={refs.state} />
        <span className="gr-fig"><small>距離</small><b ref={refs.range}>----</b><small>m</small></span>
        <span className="gr-fig"><small>残弾</small><b ref={refs.ammo}>0</b></span>
        <b className="gr-zoom" ref={refs.zoom} />
        <svg className="gr-turret" viewBox="-12 -12 24 24" aria-hidden>
          <rect className="gt-hull" x="-5" y="-9" width="10" height="18" rx="1.5" />
          <g ref={refs.turret}>
            <circle className="gt-ring" r="3.4" />
            <path className="gt-gun" d="M0 -3.4V-11" />
          </g>
        </svg>
      </div>
      {!touch && <div className="gun-lock">クリックで砲を操作<small>左クリック 射撃 ／ 右クリック 照準器 ／ Esc ポーズ</small></div>}
    </div>
  );
}
