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
        $keep = fn (array $list): array => array_filter($list, fn (array $e): bool => $open || ($e['release'] ?? null) !== 'edwards');
        config([
            'game.release.edwards' => $open,
            'game.tracks' => $keep(config('game.catalog.tracks')),
            'game.cars' => $keep(config('game.catalog.cars')),
        ]);
    }
}
