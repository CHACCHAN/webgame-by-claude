<?php

namespace Tests\Feature;

use App\Models\Player;
use App\Models\Run;
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
            ->assertJsonCount(5, 'tracks')
            ->assertJsonPath('tracks.3.id', 'autobahn')
            ->assertJsonPath('tracks.4.id', 'edwards')
            // 9 cars, 3 motorcycles, 3 fighters, 5 tanks, the 6 trains and the cockroach (joke entries)
            ->assertJsonCount(27, 'cars');
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
        $this->withToken($d)->postJson('/api/runs', $this->runPayload(152_000, ['car_id' => 'e5']))->assertCreated();
        $this->assertSame(['Delta'], array_column($this->getJson('/api/tracks/oboro-downhill/leaderboard?car_id=e5')->json('entries'), 'player_name'));
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

    public function test_autobahn_takes_runs_down_to_its_own_floor(): void
    {
        $token = $this->register();
        $autobahn = ['track_id' => 'autobahn', 'car_id' => 'roach'];

        // the cockroach near Mach 1 (its limit is ~27.5 s): faster than any mountain pass's floor allows elsewhere, fine here
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(28_000, $autobahn))->assertCreated();
        // an average beyond Mach 1 (8.6 km in 22 s: ~1400 km/h) is not
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(22_000, $autobahn))->assertUnprocessable();
        // a commuter train at 120 km/h takes over four minutes
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(259_000, ['track_id' => 'autobahn', 'car_id' => 'e231']))->assertCreated();
        $this->assertSame([28_000], array_column($this->getJson('/api/tracks/autobahn/leaderboard?car_id=roach')->json('entries'), 'time_ms'));
    }

    public function test_edwards_and_the_fighters_are_in_the_catalogue_but_closed_until_released(): void
    {
        $this->edwards(false);
        $token = $this->register();
        $this->assertArrayHasKey('edwards', config('game.catalog.tracks'));
        $this->assertSame(['edwards'], config('game.catalog.cars.f15j.courses'));
        $this->assertArrayNotHasKey('edwards', config('game.tracks'));
        $this->assertArrayNotHasKey('su47', config('game.cars'));
        // nothing can be recorded or looked up there yet
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(200_000, ['track_id' => 'edwards']))->assertUnprocessable();
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(200_000, ['car_id' => 'f15j']))->assertUnprocessable();
        $this->getJson('/api/tracks/edwards/leaderboard')->assertNotFound();
    }

    public function test_once_released_the_fighters_run_at_edwards_and_nowhere_else(): void
    {
        $this->edwards(true);
        $token = $this->register();
        $this->getJson('/api/content')->assertOk()->assertJsonPath('tracks.4.id', 'edwards')->assertJsonCount(27, 'cars');

        $edwards = ['track_id' => 'edwards', 'car_id' => 'f15j'];
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(188_000, $edwards))->assertCreated();
        // a car may race there too
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(128_000, ['track_id' => 'edwards', 'car_id' => 'u9']))->assertCreated();
        // 11.9 km in under 30 s is beyond Mach 1.2
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(29_000, $edwards))->assertUnprocessable();
        // a fighter on a mountain pass: refused
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(120_000, ['car_id' => 'su47']))
            ->assertUnprocessable()->assertJsonValidationErrors('car_id');
        $this->assertSame([188_000], array_column($this->getJson('/api/tracks/edwards/leaderboard?car_id=f15j')->json('entries'), 'time_ms'));
    }

    public function test_the_tanks_are_in_the_catalogue_but_closed_until_released(): void
    {
        $this->tanks(false);
        $token = $this->register();
        $this->assertArrayHasKey('type10', config('game.catalog.cars'));
        $this->assertArrayNotHasKey('type10', config('game.cars'));
        $this->assertNotContains('m1a2', array_column($this->getJson('/api/content')->json('cars'), 'id'));
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(200_000, ['car_id' => 'type10']))->assertUnprocessable();
        $this->withToken($token)->postJson('/api/rooms', ['track_id' => 'oboro-downhill', 'car_id' => 't14'])->assertUnprocessable();
    }

    public function test_once_released_a_tanks_run_counts_like_any_vehicles_on_every_course(): void
    {
        $this->tanks(true);
        $token = $this->register();
        $ids = array_column($this->getJson('/api/content')->json('cars'), 'id');
        foreach (['type10', 'type16', 'leopard2a5', 'm1a2', 't14'] as $tank) {
            $this->assertContains($tank, $ids);
        }
        foreach (array_keys(config('game.tracks')) as $track) {
            $this->withToken($token)->postJson('/api/runs', $this->runPayload(400_000, ['track_id' => $track, 'car_id' => 'type16']))->assertCreated();
        }
        $this->assertSame([400_000], array_column($this->getJson('/api/tracks/oboro-downhill/leaderboard?car_id=type16')->json('entries'), 'time_ms'));
        $this->withToken($token)->postJson('/api/rooms', ['track_id' => 'oboro-downhill', 'car_id' => 'leopard2a5'])->assertCreated();
    }

    /** A stored run (as an old one, or the seeded bots' on a course not open yet), with a ghost. */
    private function storedRun(Player $player, string $trackId, string $carId, int $timeMs): Run
    {
        $run = Run::create([
            'player_id' => $player->id, 'track_id' => $trackId, 'car_id' => $carId, 'mode' => 'time_attack',
            'time_ms' => $timeMs, 'sector_ms' => [1, 2, 3, $timeMs], 'client_version' => 'test',
        ]);
        $run->ghost()->create(['format' => 'v1', 'interval_ms' => 100, 'frame_count' => 1, 'data' => 'AAAA']);

        return $run;
    }

    public function test_a_course_not_open_yet_shows_none_of_its_runs(): void
    {
        $token = $this->register();
        $player = Player::where('name', 'Driver')->firstOrFail();
        $there = $this->storedRun($player, 'edwards', 'r34', 230_000);
        $this->storedRun($player, 'oboro-downhill', 'hayate', 90_000);

        $this->edwards(false);
        $this->getJson("/api/runs/{$there->id}/ghost")->assertNotFound();
        $me = $this->withToken($token)->getJson('/api/players/me')->assertOk();
        $this->assertSame(['oboro-downhill'], array_column($me->json('bests'), 'track_id'));
        $this->assertSame(['oboro-downhill'], array_column($me->json('best_runs'), 'track_id'));

        $this->edwards(true);
        $this->getJson("/api/runs/{$there->id}/ghost")->assertOk()->assertJsonPath('track_id', 'edwards');
        $this->assertContains('edwards', array_column($this->withToken($token)->getJson('/api/players/me')->json('bests'), 'track_id'));
    }

    public function test_a_vehicle_off_its_course_has_no_list_and_no_run_there(): void
    {
        $this->edwards(true);
        $token = $this->register();
        $player = Player::where('name', 'Driver')->firstOrFail();
        // (a fighter's run on a pass cannot be sent: one stored all the same is shown nowhere)
        $off = $this->storedRun($player, 'oboro-downhill', 'f15j', 80_000);
        $this->storedRun($player, 'oboro-downhill', 'hayate', 90_000);

        $this->getJson('/api/tracks/oboro-downhill/leaderboard?car_id=f15j')->assertUnprocessable()->assertJsonValidationErrors('car_id');
        $this->assertSame([90_000], array_column($this->getJson('/api/tracks/oboro-downhill/leaderboard')->json('entries'), 'time_ms'));
        $this->getJson("/api/runs/{$off->id}/ghost")->assertNotFound();
        $me = $this->withToken($token)->getJson('/api/players/me')->assertOk();
        $this->assertSame(['hayate'], array_column($me->json('bests'), 'car_id'));
        $this->assertSame(['hayate'], array_column($me->json('best_runs'), 'car_id'));
    }
}
