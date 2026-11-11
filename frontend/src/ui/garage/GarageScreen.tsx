import { useEffect, useState } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { currentCourseId } from '../../store/settings';
import { CAR_SPECS, singleRatio, vehiclesFor, type CarId } from '../../game/vehicle/carSpecs';
import { loadCarBests } from '../../api/client';
import { MEDAL_LABEL, medalFor, nextTarget } from '../../game/race/medals';
import { formatTime } from '../format';
import { startRaceFromState } from '../screens/Menus';
import { VehiclePicker } from './VehiclePicker';

/** The player's best with this vehicle on the course, and the medal time to beat next. */
function CarRecord({ id }: { id: CarId }) {
  const course = currentCourseId();
  const best = loadCarBests(course)[id] ?? null;
  const medal = best !== null ? medalFor(course, id, best) : null;
  const next = nextTarget(course, id, best);
  return (
    <div className="car-record">
      <div>
        <small>PERSONAL BEST</small>
        <b>{best !== null ? formatTime(best) : '--:--.---'}</b>
        {medal && <span className={`medal-dot medal-${medal}`}>{MEDAL_LABEL[medal]}</span>}
      </div>
      <div>
        <small>NEXT TARGET</small>
        {next ? (
          <b className={`medal-${next.medal}`}>{MEDAL_LABEL[next.medal]} {formatTime(next.timeMs)}</b>
        ) : (
          <b className="medal-gold">COMPLETE</b>
        )}
      </div>
    </div>
  );
}

/** Single player: the car select between the conditions (or the ghost list) and AT / MT. */
export function GarageScreen() {
  const { go, set, carId, mode, carColor } = useApp();
  // the fighters only at Edwards
  const [list] = useState(() => vehiclesFor(currentCourseId()));
  useEffect(() => {
    void gameHolder.game?.audio?.playMusic('bgm_garage');
  }, []);
  const confirm = (id: CarId, color: string | null) => {
    set({ carId: id, carColor: color });
    // a train or the cockroach has a single ratio: no AT/MT choice
    if (!singleRatio(CAR_SPECS[id])) go('transmission');
    else if (mode === 'rival') go('rivals');
    else void startRaceFromState();
  };
  return (
    <VehiclePicker
      title="SELECT YOUR CAR ― 車両選択"
      vehicles={list}
      initial={carId}
      initialColor={carColor}
      confirmLabel="この車に決定"
      onBrowse={(id, color) => set({ carId: id, carColor: color })}
      onConfirm={confirm}
      onBack={() => go(mode === 'ghost' ? 'leaderboard' : 'conditions')}
      extra={(id) => <CarRecord id={id} />}
    />
  );
}
