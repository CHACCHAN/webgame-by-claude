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
}
