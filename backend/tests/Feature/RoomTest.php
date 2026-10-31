<?php

namespace Tests\Feature;

use App\Events\RoomUpdated;
use App\Models\Player;
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

    public function test_up_to_three_players_join_and_the_fourth_is_refused(): void
    {
        Event::fake([RoomUpdated::class]);
        [$host, $h] = $this->player('HOST');
        $code = $this->createRoom($h);
        $this->assertMatchesRegularExpression('/^[A-Z2-9]{4}$/', $code);

        [, $b] = $this->player('B');
        [, $c] = $this->player('C');
        [, $d] = $this->player('D');
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)->assertOk()->assertJsonCount(2, 'players');
        $this->postJson('/api/rooms/'.strtolower($code).'/join', ['car_id' => 'shiden'], $c)
            ->assertOk()
            ->assertJsonCount(3, 'players')
            ->assertJsonPath('players.2.slot', 2)
            ->assertJsonPath('host_id', $host->id);
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $d)->assertStatus(409);
        // joining twice is harmless
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)->assertOk()->assertJsonCount(3, 'players');
        Event::assertDispatched(RoomUpdated::class, fn ($e) => $e->broadcastOn()->name === "presence-room.{$code}");
    }

    public function test_race_lifecycle_start_finish_results_and_rematch(): void
    {
        [, $h] = $this->player('HOST');
        [, $b] = $this->player('B');
        $code = $this->createRoom($h);

        // the host alone cannot start, guests cannot start at all
        $this->postJson("/api/rooms/{$code}/start", [], $h)->assertStatus(409);
        $this->postJson("/api/rooms/{$code}/join", ['car_id' => 'hayate'], $b)->assertOk();
        $this->postJson("/api/rooms/{$code}/start", [], $b)->assertForbidden();
        $start = $this->postJson("/api/rooms/{$code}/start", [], $h)->assertOk()->assertJsonPath('status', 'racing');
        $this->assertGreaterThan($start->json('server_time_ms'), $start->json('start_at_ms'));
        $raceNo = $start->json('race_no');

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
        $this->postJson("/api/rooms/{$code}/rematch", [], $h)
            ->assertOk()->assertJsonPath('status', 'waiting')->assertJsonPath('players.0.finish_ms', null);
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
