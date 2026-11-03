<?php

namespace App\Http\Controllers\Api;

use App\Events\RoomUpdated;
use App\Http\Controllers\Controller;
use App\Models\Player;
use App\Models\Room;
use App\Models\RoomPlayer;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Broadcast;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

/**
 * Online battle rooms. The lobby, the start signal and the results go through this API; while
 * racing, clients exchange their car states directly as client events on the room's presence
 * channel (Laravel Reverb).
 */
class RoomController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'track_id' => ['required', 'string', Rule::in(array_keys(config('game.tracks')))],
            'time_of_day' => ['sometimes', 'string', Rule::in(config('game.times_of_day'))],
            'car_id' => ['required', 'string', Rule::in(array_keys(config('game.cars')))],
        ]);
        $player = $this->player($request);

        Room::where('updated_at', '<', now()->subMinutes((int) config('game.online.room_ttl_minutes')))->delete();
        $this->leaveAllRooms($player);

        $room = DB::transaction(function () use ($data, $player) {
            $room = Room::create([
                'code' => Room::newCode(),
                'host_player_id' => $player->id,
                'track_id' => $data['track_id'],
                'time_of_day' => $data['time_of_day'] ?? 'night',
                'status' => 'waiting',
                'race_no' => 0,
            ]);
            $room->members()->create(['player_id' => $player->id, 'car_id' => $data['car_id'], 'slot' => 0]);

            return $room;
        });

        return response()->json($room->payload(), 201);
    }

    public function show(string $code): JsonResponse
    {
        return response()->json($this->room($code)->payload());
    }

    public function join(Request $request, string $code): JsonResponse
    {
        $data = $request->validate([
            'car_id' => ['required', 'string', Rule::in(array_keys(config('game.cars')))],
        ]);
        $player = $this->player($request);
        $room = $this->room($code);
        if ($member = $room->memberFor($player)) {
            // back in after a reload: loading the course again
            if ($member->ready) {
                $member->update(['ready' => false]);
                $this->broadcastRoom($room);
            }

            return response()->json($room->payload());
        }
        $this->leaveAllRooms($player);
        $max = (int) config('game.online.max_players');
        if ($room->members()->count() >= $max) {
            $this->pruneDisconnected($room);
        }

        $error = DB::transaction(function () use ($room, $player, $data, $max) {
            $room = Room::whereKey($room->id)->lockForUpdate()->first();
            if (! $room) {
                return ['ルームが見つかりません', 404];
            }
            if ($room->status !== 'waiting') {
                return ['このルームはレース中です', 409];
            }
            $taken = $room->members()->pluck('slot')->all();
            if (count($taken) >= $max) {
                return ['このルームは満員です（最大'.$max.'人）', 409];
            }
            $slot = 0;
            while (in_array($slot, $taken, true)) {
                $slot++;
            }
            $room->members()->create(['player_id' => $player->id, 'car_id' => $data['car_id'], 'slot' => $slot]);
            $room->touch();

            return null;
        });
        if ($error) {
            return response()->json(['message' => $error[0]], $error[1]);
        }

        $room->refresh();
        $this->broadcastRoom($room);

        return response()->json($room->payload());
    }

    /** The member's car, and `ready` once their game has loaded the room's course. */
    public function update(Request $request, string $code): JsonResponse
    {
        $data = $request->validate([
            'car_id' => ['required_without:ready', 'string', Rule::in(array_keys(config('game.cars')))],
            'ready' => ['sometimes', 'boolean'],
        ]);
        [$room, $member] = $this->membership($request, $code);
        if (isset($data['car_id']) && $room->status === 'racing') {
            return response()->json(['message' => 'レース中は車を変更できません'], 409);
        }
        $member->update($data);
        $room->touch();
        $this->broadcastRoom($room);

        return response()->json($room->payload());
    }

    public function leave(Request $request, string $code): JsonResponse
    {
        [$room] = $this->membership($request, $code);
        $this->removeMember($room, $this->player($request));

        return response()->json(['left' => true]);
    }

    public function start(Request $request, string $code): JsonResponse
    {
        [$room] = $this->membership($request, $code);
        if ($room->host_player_id !== $this->player($request)->id) {
            return response()->json(['message' => 'スタートできるのはホストだけです'], 403);
        }
        if ($room->status === 'racing') {
            return response()->json(['message' => 'すでにレース中です'], 409);
        }
        $min = (int) config('game.online.min_players_to_start');
        if ($room->members()->count() < $min) {
            return response()->json(['message' => "{$min}人以上そろうとスタートできます"], 409);
        }
        // nobody may start the countdown while another game is still loading the course
        if ($room->members()->where('ready', false)->exists()) {
            $this->pruneDisconnected($room);
            if ($room->members()->where('ready', false)->exists()) {
                return response()->json(['message' => 'まだコースを読み込んでいるプレイヤーがいます'], 409);
            }
        }

        DB::transaction(function () use ($room) {
            $room->members()->update(['finish_ms' => null]);
            $room->update([
                'status' => 'racing',
                'race_no' => $room->race_no + 1,
                'start_at_ms' => (int) floor(microtime(true) * 1000) + (int) config('game.online.start_delay_ms'),
            ]);
        });
        $this->broadcastRoom($room);

        return response()->json($room->payload());
    }

    public function finish(Request $request, string $code): JsonResponse
    {
        [$room, $member] = $this->membership($request, $code);
        $track = config('game.tracks.'.$room->track_id);
        $data = $request->validate([
            'race_no' => ['required', 'integer'],
            'time_ms' => ['required', 'integer', 'min:'.$track['min_time_ms'], 'max:'.$track['max_time_ms']],
        ]);
        if ($room->status !== 'racing' || $data['race_no'] !== $room->race_no) {
            return response()->json(['message' => 'このレースはもう終わっています'], 409);
        }
        // plausibility is the course minimum (validated above); clients time online races with the
        // later of their physics clock and the wall clock since the shared green light
        if ($member->finish_ms === null) {
            $member->update(['finish_ms' => $data['time_ms']]);
        }
        if ($room->members()->whereNull('finish_ms')->doesntExist()) {
            $room->update(['status' => 'finished']);
        } else {
            $room->touch();
        }
        $this->broadcastRoom($room);

        return response()->json($room->payload());
    }

    /** Back to the lobby for another race with the same people. */
    public function rematch(Request $request, string $code): JsonResponse
    {
        [$room] = $this->membership($request, $code);
        if ($room->host_player_id !== $this->player($request)->id) {
            return response()->json(['message' => 'ホストだけが操作できます'], 403);
        }
        DB::transaction(function () use ($room) {
            $room->members()->update(['finish_ms' => null]);
            $room->update(['status' => 'waiting', 'start_at_ms' => null]);
        });
        $this->broadcastRoom($room);

        return response()->json($room->payload());
    }

    /**
     * Pusher-protocol authorization for the room's presence channel, signed with the Reverb app
     * secret; only room members may subscribe (and so send car states to the others).
     */
    public function auth(Request $request): JsonResponse
    {
        $data = $request->validate([
            'socket_id' => ['required', 'string', 'regex:/^\d+\.\d+$/'],
            'channel_name' => ['required', 'string', 'max:64'],
        ]);
        if (! preg_match('/^presence-room\.([A-Z0-9]{4,8})$/', $data['channel_name'], $m)) {
            return response()->json(['message' => 'Unknown channel.'], 403);
        }
        $player = $this->player($request);
        $room = Room::where('code', $m[1])->first();
        $member = $room?->memberFor($player);
        if (! $member) {
            return response()->json(['message' => 'Not a member of this room.'], 403);
        }
        $channelData = json_encode([
            'user_id' => (string) $player->id,
            'user_info' => ['name' => $player->name, 'car_id' => $member->car_id, 'slot' => $member->slot],
        ]);
        $key = (string) config('broadcasting.connections.reverb.key');
        $secret = (string) config('broadcasting.connections.reverb.secret');
        $signature = hash_hmac('sha256', $data['socket_id'].':'.$data['channel_name'].':'.$channelData, $secret);

        return response()->json(['auth' => $key.':'.$signature, 'channel_data' => $channelData]);
    }

    private function player(Request $request): Player
    {
        return $request->attributes->get('player');
    }

    private function room(string $code): Room
    {
        return Room::where('code', strtoupper($code))->firstOrFail();
    }

    /** @return array{0: Room, 1: RoomPlayer} */
    private function membership(Request $request, string $code): array
    {
        $room = $this->room($code);
        $member = $room->memberFor($this->player($request));
        abort_unless($member, 403, 'このルームのメンバーではありません');

        return [$room, $member];
    }

    private function leaveAllRooms(Player $player): void
    {
        $rooms = Room::whereIn('id', RoomPlayer::where('player_id', $player->id)->pluck('room_id'))->get();
        foreach ($rooms as $room) {
            $this->removeMember($room, $player);
        }
    }

    private function removeMember(Room $room, Player $player): void
    {
        $room->members()->where('player_id', $player->id)->delete();
        $next = $room->members()->first();
        if (! $next) {
            $room->delete();

            return;
        }
        $changes = [];
        if ($room->host_player_id === $player->id) {
            $changes['host_player_id'] = $next->player_id;
        }
        if ($room->status === 'racing' && $room->members()->whereNull('finish_ms')->doesntExist()) {
            $changes['status'] = 'finished';
        }
        $room->update($changes);
        $room->touch();
        $this->broadcastRoom($room);
    }

    /** A full room may hold players who closed the game: drop members no longer on the channel. */
    private function pruneDisconnected(Room $room): void
    {
        try {
            $response = Broadcast::connection('reverb')->getPusher()
                ->get('/channels/presence-'.$room->channelName().'/users');
            $online = collect($response->users ?? [])->pluck('id')->map(fn ($id) => (int) $id)->all();
        } catch (\Throwable) {
            return; // realtime server unreachable: keep everyone
        }
        foreach ($room->members()->with('player')->get() as $member) {
            if (! in_array($member->player_id, $online, true) && $member->updated_at < now()->subSeconds(30)) {
                $this->removeMember($room, $member->player);
            }
        }
    }

    private function broadcastRoom(Room $room): void
    {
        try {
            broadcast(RoomUpdated::for($room->fresh()));
        } catch (\Throwable $e) {
            report($e); // the HTTP response still carries the state; clients also poll as a fallback
        }
    }
}
