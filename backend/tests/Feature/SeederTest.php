<?php

namespace Tests\Feature;

use App\Models\Player;
use App\Models\Run;
use Database\Seeders\BotRunSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SeederTest extends TestCase
{
    use RefreshDatabase;

    public function test_bot_runs_are_seeded_with_ghosts_and_seeding_is_idempotent(): void
    {
        $this->seed(BotRunSeeder::class);
        $runs = Run::count();
        $this->assertGreaterThanOrEqual(3, $runs);
        $this->assertSame($runs, Run::has('ghost')->count());
        $this->assertTrue(Player::where('is_bot', true)->exists());

        $this->seed(BotRunSeeder::class);
        $this->assertSame($runs, Run::count());

        $top = $this->getJson('/api/tracks/oboro-downhill/leaderboard')->json('entries.0');
        $ghost = $this->getJson("/api/runs/{$top['run_id']}/ghost")->assertOk()->json();
        $this->assertSame(1, $ghost['format']);
        $this->assertNotFalse(base64_decode($ghost['data'], true));
        // ~20 Hz samples over the whole run
        $this->assertEqualsWithDelta($top['time_ms'] / 50, $ghost['frame_count'], 5);
    }

    public function test_a_regenerated_bot_record_replaces_the_old_run(): void
    {
        $this->seed(BotRunSeeder::class);
        $runs = Run::count();
        // a run from an older bot_runs.json (before a physics or road grip change)
        $old = Run::first();
        $fresh = $old->time_ms;
        $old->update(['time_ms' => $fresh + 1234]);

        $this->seed(BotRunSeeder::class);
        $this->assertSame($runs, Run::count());
        $same = Run::where('player_id', $old->player_id)->where('track_id', $old->track_id)->where('car_id', $old->car_id);
        $this->assertSame([$fresh], $same->pluck('time_ms')->all());
        $this->assertSame($runs, Run::has('ghost')->count());
    }
}
