<?php

namespace App\Support;

/**
 * Which vehicle may be used where: the one place on the server that says so. A car entry of config/game.php with
 * 'courses' runs only on those (the fighters at their air base); every other vehicle runs everywhere. The client
 * offers the same (frontend vehicle/carSpecs.ts `vehiclesFor`; a vitest compares the two lists); this is the check
 * that holds when a request is made by hand. Rooms (made, joined, a member's change of vehicle, the host's change
 * of course) and runs all ask here.
 */
final class Vehicles
{
    /**
     * What may race on a course, in the game's order.
     *
     * @return list<string>
     */
    public static function on(string $trackId): array
    {
        return array_keys(array_filter(
            config('game.cars'),
            fn (array $car) => ! isset($car['courses']) || in_array($trackId, $car['courses'], true),
        ));
    }

    public static function allowedOn(string $carId, string $trackId): bool
    {
        return in_array($carId, self::on($trackId), true);
    }

    /** The vehicle a member is given when theirs does not run on a room's course: the course's first one. */
    public static function fallback(string $trackId): string
    {
        return self::on($trackId)[0] ?? (string) array_key_first(config('game.cars'));
    }
}
