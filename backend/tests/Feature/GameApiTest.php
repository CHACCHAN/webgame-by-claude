<?php

namespace Tests\Feature;

use App\Models\Player;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GameApiTest extends TestCase
{
    use RefreshDatabase;

    private function register(string $name = 'Driver'): string
    {
        return $this->postJson('/api/players', ['name' => $name])
            ->assertCreated()
            ->json('token');
    }

    private function runPayload(int $timeMs, array $overrides = []): array
    {
        $q = intdiv($timeMs, 4);

        return array_merge([
            'track_id' => 'oboro-downhill',
            'car_id' => 'hayate',
            'mode' => 'time_attack',
            'time_ms' => $timeMs,
            'sector_ms' => [$q, $q * 2, $q * 3, $timeMs],
            'client_version' => '1.0.0',
        ], $overrides);
    }

    public function test_health_and_content(): void
    {
        $this->getJson('/api/health')->assertOk()->assertJson(['status' => 'ok', 'database' => 'ok']);
        $this->getJson('/api/content')->assertOk()
            ->assertJsonPath('tracks.0.id', 'oboro-downhill')
            ->assertJsonCount(3, 'tracks')
            // 6 cars, the 4 trains and the cockroach (joke entries)
            ->assertJsonCount(11, 'cars');
    }

    public function test_player_registration_and_profile(): void
    {
        $token = $this->register('峠の走り屋');
        $this->assertSame(1, Player::count());
        $this->assertNotSame($token, Player::first()->token_hash);

        $this->withToken($token)->getJson('/api/players/me')->assertOk()->assertJsonPath('name', '峠の走り屋');
        $this->withToken($token)->patchJson('/api/players/me', ['name' => 'Renamed'])->assertOk();
        $this->withToken('bogus')->getJson('/api/players/me')->assertUnauthorized();
    }

    public function test_rejects_invalid_names(): void
    {
        $this->postJson('/api/players', ['name' => ''])->assertUnprocessable();
        $this->postJson('/api/players', ['name' => str_repeat('a', 17)])->assertUnprocessable();
        $this->postJson('/api/players', ['name' => '<script>'])->assertUnprocessable();
    }

    public function test_submit_run_with_ghost_and_fetch_it(): void
    {
        $token = $this->register();
        $ghost = ['format' => 1, 'interval_ms' => 50, 'frame_count' => 2400, 'data' => base64_encode('frames')];

        $res = $this->withToken($token)->postJson('/api/runs', $this->runPayload(120_000, ['ghost' => $ghost]))
            ->assertCreated()
            ->assertJson(['is_personal_best' => true, 'rank' => 1, 'previous_best_ms' => null]);

        $this->getJson('/api/runs/'.$res->json('run_id').'/ghost')
            ->assertOk()
            ->assertJson(['time_ms' => 120_000, 'frame_count' => 2400, 'data' => base64_encode('frames')]);
    }

    public function test_personal_best_tracking(): void
    {
        $token = $this->register();
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(130_000))->assertCreated();
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(140_000))
            ->assertJson(['is_personal_best' => false, 'previous_best_ms' => 130_000]);
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(125_000))
            ->assertJson(['is_personal_best' => true, 'previous_best_ms' => 130_000]);
    }

    public function test_leaderboard_lists_each_players_best_in_order(): void
    {
        $a = $this->register('Alpha');
        $b = $this->register('Bravo');
        $c = $this->register('Charlie');

        $this->withToken($a)->postJson('/api/runs', $this->runPayload(150_000));
        $this->withToken($a)->postJson('/api/runs', $this->runPayload(128_000));
        $this->withToken($b)->postJson('/api/runs', $this->runPayload(126_000, ['car_id' => 'raijin']));
        $this->withToken($c)->postJson('/api/runs', $this->runPayload(170_000));

        $entries = $this->getJson('/api/tracks/oboro-downhill/leaderboard')->assertOk()->json('entries');
        $this->assertSame(['Bravo', 'Alpha', 'Charlie'], array_column($entries, 'player_name'));
        $this->assertSame([126_000, 128_000, 170_000], array_column($entries, 'time_ms'));
        $this->assertSame([1, 2, 3], array_column($entries, 'rank'));

        $raijin = $this->getJson('/api/tracks/oboro-downhill/leaderboard?car_id=raijin')->json('entries');
        $this->assertCount(1, $raijin);

        // the trains (joke entries) are vehicles like the cars
        $d = $this->register('Delta');
        $this->withToken($d)->postJson('/api/runs', $this->runPayload(152_000, ['car_id' => 'n700']))->assertCreated();
        $this->assertSame(['Delta'], array_column($this->getJson('/api/tracks/oboro-downhill/leaderboard?car_id=n700')->json('entries'), 'player_name'));
        // and the cockroach, whose times go below the cars' (55 s on 朧峠: the AI's lap is ~76 s)
        $e = $this->register('Echo');
        $this->withToken($e)->postJson('/api/runs', $this->runPayload(55_000, ['car_id' => 'roach']))->assertCreated();

        $this->getJson('/api/tracks/nowhere/leaderboard')->assertNotFound();
        // leaderboards are per course
        $this->assertSame([], $this->getJson('/api/tracks/tenrou-skyline/leaderboard')->json('entries'));
    }

    public function test_runs_in_retired_vehicles_are_left_out(): void
    {
        $a = $this->register('Alpha');
        $b = $this->register('Bravo');
        $this->withToken($a)->postJson('/api/runs', $this->runPayload(120_000, ['car_id' => 'roach']))->assertCreated();
        $this->withToken($b)->postJson('/api/runs', $this->runPayload(130_000))->assertCreated();

        // the cockroach leaves the game: its runs stay stored but no list shows them
        config(['game.cars' => array_diff_key(config('game.cars'), ['roach' => 0])]);
        $this->assertSame(['Bravo'], array_column($this->getJson('/api/tracks/oboro-downhill/leaderboard')->json('entries'), 'player_name'));
        $this->assertSame([], $this->withToken($a)->getJson('/api/players/me')->assertOk()->json('bests'));
        $this->assertDatabaseHas('runs', ['car_id' => 'roach']);
    }

    public function test_rank_reflects_other_players(): void
    {
        $a = $this->register('Alpha');
        $b = $this->register('Bravo');
        $this->withToken($a)->postJson('/api/runs', $this->runPayload(120_000));
        $this->withToken($b)->postJson('/api/runs', $this->runPayload(130_000))->assertJson(['rank' => 2, 'total_players' => 2]);
    }

    public function test_rejects_implausible_runs(): void
    {
        $token = $this->register();

        // faster than the physical minimum
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(30_000))->assertUnprocessable();
        // wrong sector count
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(120_000, ['sector_ms' => [60_000, 120_000]]))
            ->assertUnprocessable();
        // final split mismatch
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(120_000, ['sector_ms' => [1, 2, 3, 4]]))
            ->assertUnprocessable();
        // ghost length inconsistent with the time
        $ghost = ['format' => 1, 'interval_ms' => 50, 'frame_count' => 100, 'data' => base64_encode('x')];
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(120_000, ['ghost' => $ghost]))
            ->assertUnprocessable();
        // unknown car
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(120_000, ['car_id' => 'delorean']))
            ->assertUnprocessable();
        // unauthenticated
        $this->withoutToken()->postJson('/api/runs', $this->runPayload(120_000))->assertUnauthorized();
    }
}
