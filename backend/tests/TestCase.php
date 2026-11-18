<?php

namespace Tests;

use Illuminate\Foundation\Testing\TestCase as BaseTestCase;

abstract class TestCase extends BaseTestCase
{
    /**
     * Edwards and its fighters open or closed, whatever config/game.php's switch says (`release`): the lists as that
     * file makes them from its catalogue.
     */
    protected function edwards(bool $open): void
    {
        $this->release('edwards', $open);
    }

    /** The tanks open or closed, likewise. */
    protected function tanks(bool $open): void
    {
        $this->release('tanks', $open);
    }

    private function release(string $name, bool $open): void
    {
        // (what waits behind another switch stays as it is)
        config(['game.release.'.$name => $open]);
        $keep = fn (array $list): array => array_filter(
            $list,
            fn (array $e): bool => ! isset($e['release']) || (bool) config('game.release.'.$e['release']),
        );
        config([
            'game.tracks' => $keep(config('game.catalog.tracks')),
            'game.cars' => $keep(config('game.catalog.cars')),
        ]);
    }
}
