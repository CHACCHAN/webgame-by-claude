<?php

namespace App\Support;

/**
 * Which vehicle may be used where: a car entry of config/game.php with 'tracks' runs only on those courses (the
 * fighters at Edwards). The client offers the same (frontend vehicle/carSpecs.ts `vehiclesFor`); this is the check
 * that holds when a request is made by hand.
 */
final class Vehicles
{
    public static function allowedOn(string $carId, string $trackId): bool
    {
        $only = config("game.cars.$carId.tracks");

        return $only === null || in_array($trackId, $only, true);
    }

    /** The vehicle a member is given when theirs does not run on a room's new course: the first that does. */
    public static function fallback(string $trackId): string
    {
        foreach (array_keys(config('game.cars')) as $id) {
            if (self::allowedOn($id, $trackId)) {
                return $id;
            }
        }

        return (string) array_key_first(config('game.cars'));
    }
}
