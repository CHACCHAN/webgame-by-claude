import { gameHolder } from './GameCanvas';

const audio = () => gameHolder.game?.audio ?? null;

/** UI sound effects (synthesised by the game's audio engine; silent until the first key or click starts it). */
export const sfx = {
  move: () => audio()?.beep(1320, 0.035, 'square', 0.035),
  confirm: () => {
    audio()?.beep(990, 0.07, 'triangle', 0.09);
    audio()?.sweep(1480, 1980, 0.11, 'triangle', 0.07);
  },
  back: () => audio()?.sweep(620, 330, 0.11, 'triangle', 0.1),
  /** a tab or an option stepped through */
  tab: () => audio()?.beep(1760, 0.03, 'square', 0.03),
  /** a screen wiped away */
  wipe: () => audio()?.hiss(2600, 700, 0.2, 0.05),
  /** a number counting up: one tick (called a few times a second while it runs) */
  tick: () => audio()?.beep(2100, 0.018, 'square', 0.02),
  /** the medal stamped on the results */
  stamp: () => {
    audio()?.sweep(220, 70, 0.22, 'square', 0.13);
    audio()?.hiss(900, 200, 0.16, 0.1);
  },
  /** a letter of the rival's transmission */
  type: () => audio()?.beep(1560 + Math.random() * 240, 0.014, 'square', 0.014),
  /** the HUD powering on at the grid */
  boot: () => audio()?.sweep(240, 1320, 0.32, 'sawtooth', 0.035),
  /** something that cannot be done now (a start without everyone ready) */
  deny: () => audio()?.sweep(300, 180, 0.16, 'square', 0.06),
};
