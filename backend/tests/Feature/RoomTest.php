<?php

namespace Tests\Feature;

use App\Events\RoomUpdated;
use App\Models\Player;
use App\Models\Room;
use App\Support\Vehicles;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class RoomTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{0: Player, 1: array<string, string>} */
    private function player(string $name): array
    {
        [$player, $token] = Player::registerGuest($name);

        return [$player, ['Authorization' => "Bearer {$token}"]];
    }

    private function createRoom(array $headers): string
    {
        return $this->postJson('/api/rooms', ['track_id' => 'kirifuri-lakeside', 'car_id' => 'raijin'], $headers)
            ->assertCreated()
            ->assertJsonPath('status', 'waiting')
            ->assertJsonCount(1, 'players')
            ->json('code');
    }

    public function test_up_to_five_players_join_and_the_sixth_is_refused(): void
    {
        Event::fake([RoomUpdated::class]);
        [$host, $h] = $this->player('HOST');
        $code = $this->createRoom($h);
        $this->assertMatchesRegularExpression('/^[A-Z2-9]{4}$/', $code);
        $this->getJson("/api/rooms/{$code}", $h)->assertOk()->assertJsonPath('max_players', 5);

        [, $b] = $this->player('B');
        [, $c] = $this->player('C');
        [, $d] = $this->player('D');
        [, $e] = $this->player('E');
        [, $f] = $this->player('F');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)->assertOk()->assertJsonCount(2, 'players');
        $this->postJson('/api/rooms/'.strtolower($code).'/join', ['car_id' => 'shiden'], $c)
            ->assertOk()
            ->assertJsonCount(3, 'players')
            ->assertJsonPath('players.2.slot', 2)
            ->assertJsonPath('host_id', $host->id);
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'e231'], $d)->assertOk()->assertJsonCount(4, 'players');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'roach'], $e)
            ->assertOk()
            ->assertJsonCount(5, 'players')
            ->assertJsonPath('players.4.slot', 4)
            ->assertJsonPath('players.4.car_id', 'roach');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $f)
            ->assertStatus(409)
            ->assertJsonPath('message', 'このルームは満員です（最大5人）');
        // joining twice is harmless
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)->assertOk()->assertJsonCount(5, 'players');
        // a seat that frees up is taken again (the lowest free slot)
        $this->postJson("/api/rooms/{$code}/leave", [], $c)->assertOk();
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $f)
            ->assertOk()
            ->assertJsonCount(5, 'players')
            ->assertJsonPath('players.2.slot', 2)
            ->assertJsonPath('players.2.name', 'F');
        Event::assertDispatched(RoomUpdated::class, fn ($e) => $e->broadcastOn()->name === "presence-room.{$code}");
    }

    public function test_five_players_race_once_all_are_loaded_and_the_four_guests_ready(): void
    {
        [, $h] = $this->player('HOST');
        $code = $this->createRoom($h);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $h)->assertOk();
        $guests = [];
        foreach (['B', 'C', 'D', 'E'] as $name) {
            [, $g] = $this->player($name);
            $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $g)->assertOk();
            $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $g)->assertOk();
            $guests[] = $g;
        }
        $this->postJson("/api/rooms/{$code}/start", [], $h)
            ->assertStatus(409)
            ->assertJsonPath('message', 'まだ準備完了になっていないプレイヤーがいます（あと4人）');
        foreach ($guests as $k => $g) {
            $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $g)->assertOk()->assertJsonPath('players.'.($k + 1).'.ready', true);
            if ($k < 3) {
                $this->postJson("/api/rooms/{$code}/start", [], $h)
                    ->assertStatus(409)
                    ->assertJsonPath('message', 'まだ準備完了になっていないプレイヤーがいます（あと'.(3 - $k).'人）');
            }
        }
        $start = $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk()->assertJsonPath('status', 'racing')->assertJsonCount(5, 'players');
        // the room is finished only when all five are in
        foreach ([$h, ...$guests] as $k => $p) {
            $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $start->json('race_no'), 'time_ms' => 84_500 + $k * 700], $p)
                ->assertOk()
                ->assertJsonPath('status', $k < 4 ? 'racing' : 'finished')
                ->assertJsonPath("players.{$k}.finish_ms", 84_500 + $k * 700);
        }
    }

    public function test_race_lifecycle_start_finish_results_and_rematch(): void
    {
        [, $h] = $this->player('HOST');
        [, $b] = $this->player('B');
        $code = $this->createRoom($h);

        // the host alone cannot start, guests cannot start at all
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertStatus(409);
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)
            ->assertOk()->assertJsonPath('players.1.loaded', false)->assertJsonPath('players.1.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $b)->assertForbidden();
        // not before every game has loaded the course
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $h)
            ->assertOk()->assertJsonPath('players.0.loaded', true)->assertJsonPath('players.0.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $h)
            ->assertStatus(409)->assertJsonPath('status', null)->assertJsonPath('message', 'B がコースを読み込んでいます');
        // nobody is ready before their game has loaded
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $b)->assertStatus(409);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => false, 'ready' => true], $b)->assertStatus(409);
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('players.1.ready', false);
        // loaded is not ready: the guest has to press the button (the host's start button is the host's)
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $b)
            ->assertOk()->assertJsonPath('players.1.loaded', true)->assertJsonPath('players.1.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $h)
            ->assertStatus(409)->assertJsonPath('message', 'まだ準備完了になっていないプレイヤーがいます（あと1人）');
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $b)->assertOk()->assertJsonPath('players.1.ready', true);
        // rejoining after a reload means loading again, and pressing again
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)
            ->assertOk()->assertJsonPath('players.1.loaded', false)->assertJsonPath('players.1.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertStatus(409);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $b)
            ->assertOk()->assertJsonPath('players.1.car_id', 'hayate')->assertJsonPath('players.1.ready', true);
        $start = $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk()->assertJsonPath('status', 'racing');
        $this->assertGreaterThan($start->json('server_time_ms'), $start->json('start_at_ms'));
        $raceNo = $start->json('race_no');
        // the race uses the readies up, and nobody gets ready for the next one before it is over
        $start->assertJsonPath('players.1.ready', false)->assertJsonPath('players.1.loaded', true);
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $b)->assertStatus(409);

        // no late joiners, no impossible times, no results for another race
        [, $late] = $this->player('LATE');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $late)->assertStatus(409);
        $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $raceNo, 'time_ms' => 1_000], $h)->assertStatus(422);
        $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $raceNo + 1, 'time_ms' => 84_500], $h)->assertStatus(409);

        $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $raceNo, 'time_ms' => 84_500], $h)
            ->assertOk()->assertJsonPath('status', 'racing')->assertJsonPath('players.0.finish_ms', 84_500);
        $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $raceNo, 'time_ms' => 86_100], $b)
            ->assertOk()->assertJsonPath('status', 'finished')->assertJsonPath('players.1.finish_ms', 86_100);

        $this->postJson("/api/rooms/{$code}/rematch", [], $b)->assertForbidden();
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $b)->assertStatus(409);
        $this->postJson("/api/rooms/{$code}/rematch", [], $h)
            ->assertOk()->assertJsonPath('status', 'waiting')->assertJsonPath('players.0.finish_ms', null)
            // back in the lobby: the course is still loaded, the ready has to be given again
            ->assertJsonPath('players.1.loaded', true)->assertJsonPath('players.1.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertStatus(409);
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $b)->assertOk();
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk()->assertJsonPath('race_no', $raceNo + 1);
    }

    public function test_ready_is_a_toggle_and_a_change_of_car_course_or_conditions_takes_it_back(): void
    {
        [, $h] = $this->player('HOST');
        [, $b] = $this->player('B');
        [, $c] = $this->player('C');
        $code = $this->createRoom($h);
        foreach ([$h, $b, $c] as $k => $p) {
            if ($k > 0) {
                $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $p)->assertOk();
            }
            $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $p)->assertOk();
        }
        $ready = fn (array $p) => $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $p)->assertOk();

        // the button toggles
        $ready($b)->assertJsonPath('players.1.ready', true);
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => false], $b)->assertOk()->assertJsonPath('players.1.ready', false);
        $ready($b);
        $ready($c)->assertJsonPath('players.1.ready', true)->assertJsonPath('players.2.ready', true);

        // another car: that player's ready only (the same car again changes nothing), the course stays loaded
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'hayate'], $b)->assertOk()->assertJsonPath('players.1.ready', true);
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'shiden'], $b)
            ->assertOk()
            ->assertJsonPath('players.1.car_id', 'shiden')
            ->assertJsonPath('players.1.ready', false)
            ->assertJsonPath('players.1.loaded', true)
            ->assertJsonPath('players.2.ready', true);
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertStatus(409);
        // the car and the ready in one request: ready with that car
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'supra', 'ready' => true], $b)
            ->assertOk()->assertJsonPath('players.1.car_id', 'supra')->assertJsonPath('players.1.ready', true);
        // a game that is loading again is not ready
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => false], $c)
            ->assertOk()->assertJsonPath('players.2.loaded', false)->assertJsonPath('players.2.ready', false);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $c)->assertOk()->assertJsonPath('players.2.ready', true);

        // other conditions: everybody's ready, the course stays loaded
        $room = Room::where('code', $code)->firstOrFail();
        $room->update(['time_of_day' => 'rain']);
        $this->getJson("/api/rooms/{$code}", $h)
            ->assertJsonPath('time_of_day', 'rain')
            ->assertJsonPath('players.1.ready', false)->assertJsonPath('players.2.ready', false)
            ->assertJsonPath('players.0.loaded', true)->assertJsonPath('players.1.loaded', true)->assertJsonPath('players.2.loaded', true);
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertStatus(409);

        // another course: every game has to load it, and nobody is ready
        $ready($b);
        $ready($c);
        $room->update(['track_id' => 'oboro-downhill']);
        $this->getJson("/api/rooms/{$code}", $h)
            ->assertJsonPath('track_id', 'oboro-downhill')
            ->assertJsonPath('players.0.loaded', false)->assertJsonPath('players.1.loaded', false)->assertJsonPath('players.2.loaded', false)
            ->assertJsonPath('players.1.ready', false)->assertJsonPath('players.2.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $h)
            ->assertStatus(409)->assertJsonPath('message', 'HOST、B、C がコースを読み込んでいます');
        // any other change of the room (a touch, the status) leaves them alone
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $b)->assertOk();
        $room->touch();
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('players.1.loaded', true)->assertJsonPath('players.1.ready', true);
    }

    public function test_the_paint_is_kept_with_the_car_and_garbage_is_refused(): void
    {
        [, $h] = $this->player('HOST');
        [, $b] = $this->player('B');
        $code = $this->postJson('/api/rooms', ['track_id' => 'kirifuri-lakeside', 'car_id' => 'raijin', 'color' => '#1D4FA8'], $h)
            ->assertCreated()->assertJsonPath('players.0.color', '#1d4fa8')->json('code');
        // none picked: null (the seat's colour)
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)->assertOk()->assertJsonPath('players.1.color', null);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $b)->assertOk();

        // a paint alone: kept, and the ready stays (it changes nothing of the race)
        $this->patchJson("/api/rooms/{$code}/me", ['color' => '#b3121c'], $b)
            ->assertOk()->assertJsonPath('players.1.color', '#b3121c')->assertJsonPath('players.1.car_id', 'hayate')->assertJsonPath('players.1.ready', true);
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('players.1.color', '#b3121c');
        // the car with its paint
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'e231', 'color' => '#f0a020'], $b)
            ->assertOk()->assertJsonPath('players.1.car_id', 'e231')->assertJsonPath('players.1.color', '#f0a020')->assertJsonPath('players.1.ready', false);
        // another car without one: the old paint was the old vehicle's
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'supra'], $b)->assertOk()->assertJsonPath('players.1.color', null);
        // null takes a paint back
        $this->patchJson("/api/rooms/{$code}/me", ['color' => null], $h)->assertOk()->assertJsonPath('players.0.color', null);

        foreach (['red', '#12345', '#1234567', '#gggggg', 'url(x)', 12, ['#ffffff']] as $bad) {
            $this->patchJson("/api/rooms/{$code}/me", ['color' => $bad], $b)->assertStatus(422);
            $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate', 'color' => $bad], $b)->assertStatus(422);
        }
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('players.1.color', null);
        // a request that changes nothing
        $this->patchJson("/api/rooms/{$code}/me", [], $b)->assertStatus(422);

        // not during a race
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $b)->assertOk();
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $h)->assertOk();
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk();
        $this->patchJson("/api/rooms/{$code}/me", ['color' => '#ffffff'], $b)->assertStatus(409);
    }

    public function test_the_host_needs_no_ready_and_a_new_host_inherits_the_start_button(): void
    {
        [, $h] = $this->player('HOST');
        [$guest, $b] = $this->player('B');
        [, $c] = $this->player('C');
        $code = $this->createRoom($h);
        foreach ([$h, $b, $c] as $k => $p) {
            if ($k > 0) {
                $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $p)->assertOk();
            }
            $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $p)->assertOk();
        }
        // only C is ready; the host never pressed anything
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $c)->assertOk()->assertJsonPath('players.0.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $h)
            ->assertStatus(409)->assertJsonPath('message', 'まだ準備完了になっていないプレイヤーがいます（あと1人）');
        // the host leaves: B (not ready) is the host now and may start, C being ready
        $this->postJson("/api/rooms/{$code}/leave", [], $h)->assertOk();
        $this->getJson("/api/rooms/{$code}", $b)->assertJsonPath('host_id', $guest->id);
        $this->postJson("/api/rooms/{$code}/start", [], $c)->assertForbidden();
        $this->postJson("/api/rooms/{$code}/start", [], $b)->assertOk()->assertJsonPath('status', 'racing');
    }

    public function test_leaving_hands_the_room_over_and_the_last_one_out_closes_it(): void
    {
        [$host, $h] = $this->player('HOST');
        [$guest, $b] = $this->player('B');
        $code = $this->createRoom($h);
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)->assertOk();
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'shiden'], $b)->assertOk()->assertJsonPath('players.1.car_id', 'shiden');

        $this->postJson("/api/rooms/{$code}/leave", [], $h)->assertOk();
        $this->getJson("/api/rooms/{$code}", $b)->assertOk()->assertJsonPath('host_id', $guest->id)->assertJsonCount(1, 'players');
        $this->postJson("/api/rooms/{$code}/leave", [], $b)->assertOk();
        $this->getJson("/api/rooms/{$code}", $b)->assertNotFound();
        $this->assertDatabaseMissing('room_players', ['player_id' => $host->id]);
    }

    public function test_the_room_keeps_the_hosts_time_of_day_for_everyone(): void
    {
        [, $h] = $this->player('HOST');
        [, $b] = $this->player('B');
        $code = $this->postJson('/api/rooms', ['track_id' => 'oboro-downhill', 'time_of_day' => 'rain', 'car_id' => 'hayate'], $h)
            ->assertCreated()->assertJsonPath('time_of_day', 'rain')->json('code');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'shiden'], $b)->assertOk()->assertJsonPath('time_of_day', 'rain');
        $this->postJson('/api/rooms', ['track_id' => 'oboro-downhill', 'time_of_day' => 'noon', 'car_id' => 'hayate'], $h)->assertStatus(422);
        // older clients send no conditions: night
        $this->assertSame('night', $this->postJson('/api/rooms', ['track_id' => 'oboro-downhill', 'car_id' => 'hayate'], $b)->json('time_of_day'));
    }

    /** A room of three, everyone loaded, the two guests ready. @return array{0: string, 1: array, 2: array, 3: array} */
    private function readyRoom(): array
    {
        [, $h] = $this->player('HOST');
        [, $b] = $this->player('B');
        [, $c] = $this->player('C');
        $code = $this->createRoom($h);
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate', 'color' => '#c8102e'], $b)->assertOk();
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayabusa', 'color' => '#101010'], $c)->assertOk();
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $h)->assertOk();
        foreach ([$b, $c] as $g) {
            $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $g)->assertOk();
        }

        return [$code, $h, $b, $c];
    }

    public function test_the_host_changes_the_course_and_the_conditions_of_a_waiting_room(): void
    {
        Event::fake([RoomUpdated::class]);
        [$code, $h, $b, $c] = $this->readyRoom();

        // the conditions alone: the readies go back, the course stays loaded
        $this->patchJson("/api/rooms/{$code}", ['time_of_day' => 'dawn'], $h)
            ->assertOk()
            ->assertJsonPath('track_id', 'kirifuri-lakeside')->assertJsonPath('time_of_day', 'dawn')
            ->assertJsonPath('players.0.loaded', true)->assertJsonPath('players.1.loaded', true)->assertJsonPath('players.2.loaded', true)
            ->assertJsonPath('players.1.ready', false)->assertJsonPath('players.2.ready', false);
        // the same again changes nothing: a ready given meanwhile stays
        $this->patchJson("/api/rooms/{$code}/me", ['ready' => true], $b)->assertOk();
        $this->patchJson("/api/rooms/{$code}", ['time_of_day' => 'dawn', 'track_id' => 'kirifuri-lakeside'], $h)
            ->assertOk()->assertJsonPath('players.1.ready', true)->assertJsonPath('players.1.loaded', true);

        // another course: every game loads again and nobody is ready; the conditions stay, vehicles and paints too
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'autobahn'], $h)
            ->assertOk()
            ->assertJsonPath('track_id', 'autobahn')->assertJsonPath('time_of_day', 'dawn')
            ->assertJsonPath('players.0.loaded', false)->assertJsonPath('players.1.loaded', false)->assertJsonPath('players.2.loaded', false)
            ->assertJsonPath('players.1.ready', false)
            ->assertJsonPath('players.1.car_id', 'hayate')->assertJsonPath('players.1.color', '#c8102e')
            ->assertJsonPath('players.2.car_id', 'hayabusa');
        $this->postJson("/api/rooms/{$code}/start", [], $h)
            ->assertStatus(409)->assertJsonPath('message', 'HOST、B、C がコースを読み込んでいます');
        // a game that reports the course it left behind is still loading; the room's course counts
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'track_id' => 'kirifuri-lakeside'], $b)
            ->assertOk()->assertJsonPath('players.1.loaded', false);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true, 'track_id' => 'kirifuri-lakeside'], $b)->assertStatus(409);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'track_id' => 'autobahn'], $b)
            ->assertOk()->assertJsonPath('players.1.loaded', true);
        // both at once
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'tenrou-skyline', 'time_of_day' => 'rain'], $h)
            ->assertOk()->assertJsonPath('track_id', 'tenrou-skyline')->assertJsonPath('time_of_day', 'rain')->assertJsonPath('players.1.loaded', false);
        Event::assertDispatched(RoomUpdated::class, fn ($e) => $e->room['track_id'] === 'tenrou-skyline' && $e->room['time_of_day'] === 'rain');

        // what is not a course or a condition, and a request with neither
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'nurburgring'], $h)->assertStatus(422);
        $this->patchJson("/api/rooms/{$code}", ['time_of_day' => 'noon'], $h)->assertStatus(422);
        $this->patchJson("/api/rooms/{$code}", [], $h)->assertStatus(422);
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('track_id', 'tenrou-skyline')->assertJsonPath('time_of_day', 'rain');
    }

    public function test_only_the_host_changes_the_room_and_only_while_it_waits(): void
    {
        [$code, $h, $b, $c] = $this->readyRoom();
        [, $stranger] = $this->player('X');

        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'autobahn'], $b)
            ->assertForbidden()->assertJsonPath('message', 'コースと天候を変更できるのはホストだけです');
        $this->patchJson("/api/rooms/{$code}", ['time_of_day' => 'rain'], $c)->assertForbidden();
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'autobahn'], $stranger)->assertForbidden();
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'autobahn'])->assertUnauthorized();
        $this->getJson("/api/rooms/{$code}", $h)
            ->assertJsonPath('track_id', 'kirifuri-lakeside')->assertJsonPath('time_of_day', 'night')->assertJsonPath('players.1.ready', true);

        // not in a race, not on the results
        $raceNo = $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk()->json('race_no');
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'autobahn'], $h)
            ->assertStatus(409)->assertJsonPath('message', 'コースと天候を変更できるのはレースの前だけです');
        foreach ([$h, $b, $c] as $p) {
            $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $raceNo, 'time_ms' => 90_000], $p)->assertOk();
        }
        $this->patchJson("/api/rooms/{$code}", ['time_of_day' => 'rain'], $h)->assertStatus(409);
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('status', 'finished')->assertJsonPath('track_id', 'kirifuri-lakeside');

        // a new host inherits it
        $this->postJson("/api/rooms/{$code}/rematch", [], $h)->assertOk();
        $this->postJson("/api/rooms/{$code}/leave", [], $h)->assertOk();
        $this->patchJson("/api/rooms/{$code}", ['time_of_day' => 'rain'], $c)->assertForbidden();
        $this->patchJson("/api/rooms/{$code}", ['time_of_day' => 'rain'], $b)->assertOk()->assertJsonPath('time_of_day', 'rain');
    }

    public function test_the_next_race_can_be_on_another_course(): void
    {
        [$code, $h, $b, $c] = $this->readyRoom();
        $raceNo = $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk()->json('race_no');
        foreach ([$h, $b, $c] as $p) {
            $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $raceNo, 'time_ms' => 90_000], $p)->assertOk();
        }

        // from the results: back to the lobby and onto another course in one step (the host's alone)
        $this->postJson("/api/rooms/{$code}/rematch", ['track_id' => 'oboro-downhill'], $b)->assertForbidden();
        $this->postJson("/api/rooms/{$code}/rematch", ['track_id' => 'nurburgring'], $h)->assertStatus(422);
        $this->postJson("/api/rooms/{$code}/rematch", ['track_id' => 'oboro-downhill', 'time_of_day' => 'rain'], $h)
            ->assertOk()
            ->assertJsonPath('status', 'waiting')->assertJsonPath('track_id', 'oboro-downhill')->assertJsonPath('time_of_day', 'rain')
            ->assertJsonPath('players.0.finish_ms', null)
            ->assertJsonPath('players.0.loaded', false)->assertJsonPath('players.1.loaded', false)->assertJsonPath('players.2.loaded', false)
            ->assertJsonPath('players.1.ready', false);
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertStatus(409);
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'track_id' => 'oboro-downhill'], $h)->assertOk();
        foreach ([$b, $c] as $g) {
            $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true, 'track_id' => 'oboro-downhill'], $g)->assertOk();
        }
        $second = $this->postJson("/api/rooms/{$code}/start", [], $h)
            ->assertOk()->assertJsonPath('status', 'racing')->assertJsonPath('track_id', 'oboro-downhill')->json('race_no');
        $this->assertSame($raceNo + 1, $second);
        // the finish is checked against the course of this race
        $this->postJson("/api/rooms/{$code}/finish", ['race_no' => $second, 'time_ms' => 40_000], $h)->assertOk();
    }

    public function test_a_vehicle_the_new_course_does_not_offer_is_replaced(): void
    {
        // (a motorcycle bound to two courses, as the fighters are to their air base)
        config(['game.cars.hayabusa.courses' => ['kirifuri-lakeside', 'autobahn']]);
        $this->assertNotContains('hayabusa', Vehicles::on('oboro-downhill'));
        $this->assertContains('hayabusa', Vehicles::on('autobahn'));
        $this->assertSame('hayate', Vehicles::fallback('oboro-downhill'));
        [$code, $h, $b, $c] = $this->readyRoom();

        // a course that offers it: kept, with its paint
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'autobahn'], $h)
            ->assertOk()->assertJsonPath('players.2.car_id', 'hayabusa')->assertJsonPath('players.2.color', '#101010');
        // one that does not: the course's first vehicle, without the other one's paint; the others keep theirs
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'oboro-downhill'], $h)
            ->assertOk()
            ->assertJsonPath('players.2.car_id', 'hayate')->assertJsonPath('players.2.color', null)
            ->assertJsonPath('players.1.car_id', 'hayate')->assertJsonPath('players.1.color', '#c8102e')
            ->assertJsonPath('players.0.car_id', 'raijin');
        // and it cannot be entered there, nor made a room with; who joins with it (by a code: the room's course is
        // not known then) is seated as the change of course seats: the course's first vehicle, without the paint
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'hayabusa'], $c)
            ->assertStatus(422)->assertJsonPath('errors.car_id.0', 'GSX1300R 隼はこのコースでは走れません');
        [, $d] = $this->player('D');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayabusa', 'color' => '#101010'], $d)
            ->assertOk()->assertJsonPath('players.3.car_id', 'hayate')->assertJsonPath('players.3.color', null);
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'ninjah2'], $d)->assertOk();
        $this->postJson('/api/rooms', ['track_id' => 'tenrou-skyline', 'car_id' => 'hayabusa'], $d)->assertStatus(422);
        $this->postJson('/api/rooms', ['track_id' => 'autobahn', 'car_id' => 'hayabusa'], $d)->assertCreated();
    }

    public function test_the_host_takes_a_member_out_of_the_waiting_room(): void
    {
        Event::fake([RoomUpdated::class]);
        [$code, $h, $b, $c] = $this->readyRoom();
        $ids = collect($this->getJson("/api/rooms/{$code}", $h)->json('players'))->pluck('id')->all();

        $this->postJson("/api/rooms/{$code}/kick", ['player_id' => $ids[2]], $b)
            ->assertForbidden()->assertJsonPath('message', 'メンバーを外せるのはホストだけです');
        // not oneself, nobody who is not there
        $this->postJson("/api/rooms/{$code}/kick", ['player_id' => $ids[0]], $h)->assertNotFound();
        $this->postJson("/api/rooms/{$code}/kick", ['player_id' => 999_999], $h)->assertNotFound();
        $this->postJson("/api/rooms/{$code}/kick", [], $h)->assertStatus(422);

        $this->postJson("/api/rooms/{$code}/kick", ['player_id' => $ids[2]], $h)
            ->assertOk()->assertJsonCount(2, 'players')->assertJsonPath('players.1.name', 'B')->assertJsonPath('host_id', $ids[0]);
        Event::assertDispatched(RoomUpdated::class, fn ($e) => count($e->room['players']) === 2);
        // the one taken out is no member any more, and may come back with the code
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $c)->assertForbidden();
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $c)->assertOk()->assertJsonCount(3, 'players');
        $back = collect($this->getJson("/api/rooms/{$code}", $h)->json('players'))->firstWhere('name', 'C')['id'];

        // not in a race
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $c)->assertOk();
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk();
        $this->postJson("/api/rooms/{$code}/kick", ['player_id' => $back], $h)
            ->assertStatus(409)->assertJsonPath('message', 'メンバーを外せるのはレースの前だけです');
    }

    public function test_presence_channel_auth_is_signed_for_members_only(): void
    {
        config(['broadcasting.connections.reverb.key' => 'test-key', 'broadcasting.connections.reverb.secret' => 'test-secret']);
        [$host, $h] = $this->player('HOST');
        [, $other] = $this->player('OTHER');
        $code = $this->createRoom($h);
        $channel = "presence-room.{$code}";

        $res = $this->postJson('/api/broadcasting/auth', ['socket_id' => '1234.5678', 'channel_name' => $channel], $h)->assertOk();
        $expected = hash_hmac('sha256', "1234.5678:{$channel}:".$res->json('channel_data'), 'test-secret');
        $this->assertSame("test-key:{$expected}", $res->json('auth'));
        $this->assertSame((string) $host->id, json_decode($res->json('channel_data'), true)['user_id']);

        $this->postJson('/api/broadcasting/auth', ['socket_id' => '1234.5678', 'channel_name' => $channel], $other)->assertForbidden();
        $this->postJson('/api/broadcasting/auth', ['socket_id' => '1234.5678', 'channel_name' => 'private-admin'], $h)->assertForbidden();
        $this->postJson('/api/broadcasting/auth', ['socket_id' => '1234.5678', 'channel_name' => $channel])->assertUnauthorized();
    }

    public function test_a_fighter_is_taken_only_into_a_room_at_edwards(): void
    {
        $this->edwards(true);
        [, $h] = $this->player('Host');
        [, $b] = $this->player('Guest');

        // a mountain pass: no room is made with a fighter and nobody changes to one; who joins with one (by a code:
        // the course is not known then) is seated in a car, the paint gone
        $this->postJson('/api/rooms', ['track_id' => 'kirifuri-lakeside', 'car_id' => 'f15j'], $h)
            ->assertUnprocessable()->assertJsonValidationErrors('car_id');
        $pass = $this->createRoom($h);
        $this->postJson("/api/rooms/{$pass}/join", ['car_id' => 'su47', 'color' => '#3b4049'], $b)
            ->assertOk()->assertJsonPath('players.1.car_id', 'hayate')->assertJsonPath('players.1.color', null);
        $this->patchJson("/api/rooms/{$pass}/me", ['car_id' => 'supra'], $b)->assertOk();
        $this->patchJson("/api/rooms/{$pass}/me", ['car_id' => 'f15c'], $b)->assertUnprocessable();
        $this->getJson("/api/rooms/{$pass}", $h)->assertJsonPath('players.1.car_id', 'supra');

        // Edwards: fighters and cars side by side
        $code = $this->postJson('/api/rooms', ['track_id' => 'edwards', 'car_id' => 'f15j', 'color' => '#7f8890'], $h)->assertCreated()->json('code');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'r34'], $b)->assertOk();
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'su47'], $b)->assertOk()->assertJsonPath('players.1.car_id', 'su47');

        // the host moves the room to another course: the fighters give way to the course's first vehicle (and
        // their paint goes), everyone loads again
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true], $b)->assertOk();
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'oboro-downhill'], $h)
            ->assertOk()
            ->assertJsonPath('players.0.car_id', 'hayate')->assertJsonPath('players.0.color', null)
            ->assertJsonPath('players.1.car_id', 'hayate')
            ->assertJsonPath('players.0.loaded', false)->assertJsonPath('players.1.loaded', false)->assertJsonPath('players.1.ready', false);
        // and back to Edwards: nobody is put into a fighter, but it can be taken again; the next race from the
        // results on a pass (`rematch` with a course) seats a fighter's pilot the same way
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'edwards'], $h)->assertOk()->assertJsonPath('players.1.car_id', 'hayate');
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'f15c'], $b)->assertOk();
        $this->postJson("/api/rooms/{$code}/rematch", ['track_id' => 'tenrou-skyline'], $h)
            ->assertOk()->assertJsonPath('track_id', 'tenrou-skyline')
            ->assertJsonPath('players.1.car_id', 'hayate')->assertJsonPath('players.0.car_id', 'hayate');
    }

    public function test_before_its_release_no_room_takes_edwards_or_a_fighter(): void
    {
        $this->edwards(false);
        [, $h] = $this->player('Host');
        [, $b] = $this->player('Guest');
        $this->postJson('/api/rooms', ['track_id' => 'edwards', 'car_id' => 'hayate'], $h)->assertUnprocessable()->assertJsonValidationErrors('track_id');
        $this->postJson('/api/rooms', ['track_id' => 'oboro-downhill', 'car_id' => 'f15j'], $h)->assertUnprocessable()->assertJsonValidationErrors('car_id');
        $code = $this->createRoom($h);
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'su47'], $b)->assertUnprocessable()->assertJsonValidationErrors('car_id');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'supra'], $b)->assertOk();
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'f15c'], $b)->assertUnprocessable()->assertJsonValidationErrors('car_id');
        // the host's change of course, in the waiting room and from the results
        $this->patchJson("/api/rooms/{$code}", ['track_id' => 'edwards'], $h)->assertUnprocessable()->assertJsonValidationErrors('track_id');
        $this->postJson("/api/rooms/{$code}/rematch", ['track_id' => 'edwards'], $h)->assertUnprocessable()->assertJsonValidationErrors('track_id');
        $room = $this->getJson("/api/rooms/{$code}", $h)->assertOk()->assertJsonPath('track_id', 'kirifuri-lakeside')->json();
        $this->assertSame(['raijin', 'supra'], array_column($room['players'], 'car_id'));
        // nothing the game is told names them either
        $content = $this->getJson('/api/content')->assertOk()->json();
        $this->assertNotContains('edwards', array_column($content['tracks'], 'id'));
        $this->assertEmpty(array_intersect(['f15j', 'f15c', 'su47'], array_column($content['cars'], 'id')));
    }

    /** Moves the room to another course the moment a request has first read it (the host's change, in between). */
    private function changedOnFirstRead(string $code, string $trackId): void
    {
        $done = false;
        Event::listen('eloquent.retrieved: '.Room::class, function (Room $room) use (&$done, $code, $trackId) {
            if ($done || $room->code !== $code) {
                return;
            }
            $done = true;
            DB::table('rooms')->where('code', $code)->update(['track_id' => $trackId]);
            DB::table('room_players')->where('room_id', $room->id)->whereIn('car_id', ['f15j', 'f15c', 'su47'])->update(['car_id' => 'hayate']);
        });
    }

    public function test_who_joins_while_the_host_changes_the_course_gets_a_vehicle_of_the_new_one(): void
    {
        $this->edwards(true);
        [, $h] = $this->player('Host');
        [, $b] = $this->player('Guest');
        $code = $this->postJson('/api/rooms', ['track_id' => 'edwards', 'car_id' => 'r34'], $h)->assertCreated()->json('code');
        $this->changedOnFirstRead($code, 'oboro-downhill');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'f15j', 'color' => '#79828a'], $b)
            ->assertOk()->assertJsonPath('track_id', 'oboro-downhill')
            ->assertJsonPath('players.1.car_id', 'hayate')->assertJsonPath('players.1.color', null);
    }

    public function test_a_change_of_vehicle_is_checked_against_the_course_the_room_has_then(): void
    {
        $this->edwards(true);
        [, $h] = $this->player('Host');
        [, $b] = $this->player('Guest');
        $code = $this->postJson('/api/rooms', ['track_id' => 'edwards', 'car_id' => 'r34'], $h)->assertCreated()->json('code');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'supra'], $b)->assertOk();
        $this->changedOnFirstRead($code, 'oboro-downhill');
        $this->patchJson("/api/rooms/{$code}/me", ['car_id' => 'su47'], $b)->assertUnprocessable()->assertJsonValidationErrors('car_id');
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('track_id', 'oboro-downhill')->assertJsonPath('players.1.car_id', 'supra');
    }

    public function test_a_race_on_a_course_that_is_closed_meanwhile_cannot_be_finished(): void
    {
        $this->edwards(true);
        [, $h] = $this->player('Host');
        $code = $this->postJson('/api/rooms', ['track_id' => 'edwards', 'car_id' => 'f15j'], $h)->assertCreated()->json('code');
        DB::table('rooms')->where('code', $code)->update(['status' => 'racing', 'race_no' => 1]);
        $this->edwards(false);
        $this->postJson("/api/rooms/{$code}/finish", ['race_no' => 1, 'time_ms' => 200_000], $h)->assertStatus(409);
    }
}
