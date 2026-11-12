import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { gameHolder } from '../GameCanvas';
import { CAR_SPECS, vehiclesFor, type CarId } from '../../game/vehicle/carSpecs';
import { chooseCar, useOnline } from '../../store/online';
import { COLORS, offeredPaint } from '../../game/vehicle/paints';
import { showRoomLineup } from '../../store/lobby';
import { sfx } from '../sfx';
import { VehiclePicker, VehicleThumb } from './VehiclePicker';
import { liveryName } from '../screens/Cars';

/** The vehicle next to (`d` = ±1) the entered one in the course's list: what ← → open the car select on. */
export function neighbourVehicle(course: string, id: CarId, d: number): CarId {
  const list = vehiclesFor(course);
  return list[(Math.max(0, list.indexOf(id)) + d + list.length) % list.length];
}

/**
 * The online entry's vehicle (lobby and room): a button showing what is entered, and the car select over the screen
 * to change it and its paint (the same picker as single player's; the paint is kept by the server with the car and
 * drawn on the others' screens, while the seat's colour stays the player's mark in tags, the HUD and lists). `picking` is the vehicle the select opens on (null: closed); the screen holds it, to keep its own
 * keys off meanwhile. Looking around in the select enters nothing: only the confirm button calls `chooseCar` (the
 * server takes a 準備完了 back on a change of car, not of paint alone), and leaving puts the entered vehicle back in
 * the garage. In a room
 * (`room`) the others see the vehicle being looked at in the player's seat (store/lobby.ts hears the garage), and
 * closing the select brings the room's line-up back.
 */
export function OnlineVehicle({ carId, course, disabled, picking, onPicking, room }: { carId: CarId; course: string; disabled?: boolean; picking: CarId | null; onPicking: (id: CarId | null) => void; room?: boolean }) {
  // the entered paint (none picked: the seat's colour in the room and the race, the vehicle's first in the garage)
  const color = offeredPaint(carId, useOnline((s) => s.carColor)) ?? null;
  // what stands behind the screen once the select is closed: the room's line-up, or the entered vehicle alone
  const restore = (keep = false) => (room ? showRoomLineup(keep) : gameHolder.game?.showGarage(carId, color ?? undefined));
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
        {color && <i className="ol-vehicle-paint" style={{ background: color }} title={liveryName(carId, color) ?? undefined} />}
        <em>変更 ▶</em>
      </button>
      {picking && !disabled && host && createPortal(
        <VehiclePicker
          overlay
          title="車両選択"
          titleEn="ONLINE ENTRY"
          vehicles={vehiclesFor(course)}
          initial={picking}
          initialColor={color}
          entered={carId}
          confirmLabel="この車でエントリー"
          onConfirm={(id, picked) => {
            onPicking(null);
            // the paint as it stood in the garage (no swatch touched: the vehicle's first)
            const paint = offeredPaint(id, picked) ?? COLORS[id][0];
            // (the same vehicle in the same paint is no change of entry: it only goes back on show)
            if (id !== carId || paint !== color) {
              chooseCar(id, paint);
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
