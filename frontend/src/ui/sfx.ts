import { gameHolder } from './GameCanvas';

const audio = () => gameHolder.game?.audio ?? null;

/** UI sound effects (synthesised). */
export const sfx = {
  move: () => audio()?.beep(880, 0.05, 'triangle', 0.08),
  confirm: () => audio()?.chime([660, 990], 0.06),
  back: () => audio()?.beep(440, 0.08, 'triangle', 0.1),
};
