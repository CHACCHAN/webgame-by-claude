import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { gameHolder } from '../GameCanvas';
import { CAR_SPECS, vehiclesFor, type CarId } from '../../game/vehicle/carSpecs';
import { chooseCar } from '../../store/online';
import { showRoomLineup } from '../../store/lobby';
import { sfx } from '../sfx';
import { VehiclePicker, VehicleThumb } from './VehiclePicker';

/** The vehicle next to (`d` = ±1) the entered one in the course's list: what ← → open the car select on. */
export function neighbourVehicle(course: string, id: CarId, d: number): CarId {
  const list = vehiclesFor(course);
  return list[(Math.max(0, list.indexOf(id)) + d + list.length) % list.length];
}

/**
 * The online entry's vehicle (lobby and room): a button showing what is entered, and the car select over the screen
 * to change it. `picking` is the vehicle the select opens on (null: closed); the screen holds it, to keep its own
 * keys off meanwhile. Looking around in the select enters nothing: only the confirm button calls `chooseCar` (the
 * server takes a 準備完了 back on a change of car), and leaving puts the entered vehicle back in the garage. In a room
 * (`room`) the others see the vehicle being looked at in the player's seat (store/lobby.ts hears the garage), and
 * closing the select brings the room's line-up back.
 */
export function OnlineVehicle({ carId, course, disabled, picking, onPicking, room }: { carId: CarId; course: string; disabled?: boolean; picking: CarId | null; onPicking: (id: CarId | null) => void; room?: boolean }) {
  // what stands behind the screen once the select is closed: the room's line-up, or the entered vehicle alone
  const restore = (keep = false) => (room ? showRoomLineup(keep) : gameHolder.game?.showGarage(carId));
  // the race started (or the room closed) with the select open
  useEffect(() => {
    if (disabled && picking) onPicking(null);
  }, [disabled, picking, onPicking]);
  const host = document.querySelector('.overlay');
  return (
    <>
      <button
        className="ol-vehicle"
        disabled={disabled}
        onClick={() => {
          sfx.confirm();
          onPicking(carId);
        }}
      >
        <VehicleThumb id={carId} />
        <span className="ol-vehicle-name">
          <small>車両</small>
          <b>{CAR_SPECS[carId].name}</b>
        </span>
        <em>変更 ▶</em>
      </button>
      {picking && !disabled && host && createPortal(
        <VehiclePicker
          overlay
          title="車両選択"
          titleEn="ONLINE ENTRY"
          vehicles={vehiclesFor(course)}
          initial={picking}
          colors={false}
          entered={carId}
          confirmLabel="この車でエントリー"
          onConfirm={(id) => {
            onPicking(null);
            // (the same vehicle again is no change of entry: it only goes back on show)
            if (id !== carId) {
              chooseCar(id);
              if (room) restore(true);
            } else restore();
          }}
          onBack={() => {
            onPicking(null);
            restore();
          }}
        />,
        host,
      )}
    </>
  );
}
