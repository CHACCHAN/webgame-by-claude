<?php

namespace Tests\Feature;

use App\Events\RoomUpdated;
use App\Models\Player;
use App\Models\Room;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class RoomTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{0: Player, 1: array<string, string>} */
    private function player(string $name): array
    {
        [$player, $token] = Player::register($name);

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
            ->assertStatus(409)->assertJsonPath('status', null)->assertJsonPath('message', 'まだコースを読み込んでいるプレイヤーがいます');
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
            ->assertStatus(409)->assertJsonPath('message', 'まだコースを読み込んでいるプレイヤーがいます');
        // any other change of the room (a touch, the status) leaves them alone
        $this->patchJson("/api/rooms/{$code}/me", ['loaded' => true, 'ready' => true], $b)->assertOk();
        $room->touch();
        $this->getJson("/api/rooms/{$code}", $h)->assertJsonPath('players.1.loaded', true)->assertJsonPath('players.1.ready', true);
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
}
