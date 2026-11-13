<?php

namespace App\Http\Controllers\Api;

use App\Events\RoomUpdated;
use App\Http\Controllers\Controller;
use App\Models\Player;
use App\Models\Room;
use App\Models\RoomPlayer;
use App\Support\Vehicles;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Broadcast;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

/**
 * Online battle rooms. The lobby, the start signal and the results go through this API; while
 * racing, clients exchange their car states directly as client events on the room's presence
 * channel (Laravel Reverb).
 */
class RoomController extends Controller
{
    /**
     * A vehicle's paint as the game's swatches give it. The server does not know which colours a vehicle offers
     * (the game's lists): it keeps any well-formed one, and the game that draws it falls back to the seat's colour
     * for one its vehicle does not offer.
     */
    private const COLOR_RULE = ['sometimes', 'nullable', 'string', 'regex:/^#[0-9a-fA-F]{6}$/'];

    /** @param array<string, mixed> $data */
    private static function color(array $data): ?string
    {
        return isset($data['color']) ? strtolower($data['color']) : null;
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'track_id' => ['required', 'string', Rule::in(array_keys(config('game.tracks')))],
            'time_of_day' => ['sometimes', 'string', Rule::in(config('game.times_of_day'))],
            'car_id' => ['required', 'string', Rule::in(array_keys(config('game.cars')))],
            'color' => self::COLOR_RULE,
        ]);
        $this->offered($data['car_id'], $data['track_id']);
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
            $room->members()->create(['player_id' => $player->id, 'car_id' => $data['car_id'], 'color' => self::color($data), 'slot' => 0]);

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
            'color' => self::COLOR_RULE,
        ]);
        $player = $this->player($request);
        $room = $this->room($code);
        if ($member = $room->memberFor($player)) {
            // back in after a reload: loading the course again (and so not ready either)
            if ($member->loaded || $member->ready) {
                $member->update(['loaded' => false, 'ready' => false]);
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
            // whoever comes in by a code cannot know the room's course: a vehicle that does not run there (a fighter
            // anywhere but at Edwards) is not refused, its driver is seated in the course's first one, without a paint
            // (as when the host changes the course: `Room::change`), and picks another in the room. Asked of the
            // locked row: the host may have changed the course since the room was first read.
            if (! Vehicles::allowedOn($data['car_id'], $room->track_id)) {
                $data['car_id'] = Vehicles::fallback($room->track_id);
                $data['color'] = null;
            }
            $slot = 0;
            while (in_array($slot, $taken, true)) {
                $slot++;
            }
            $room->members()->create(['player_id' => $player->id, 'car_id' => $data['car_id'], 'color' => self::color($data), 'slot' => $slot]);
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

    /**
     * The member's own state: the car, `loaded` (sent by the game once it shows the room's course) and `ready`
     * (the 準備完了 button, a toggle). Another car takes the ready back; nobody is ready before their game has loaded.
     * `color`: the vehicle's paint (null: none, the seat's colour). Another car sent without one drops the old paint
     * (it was that vehicle's); another paint alone keeps the ready: it changes nothing of the race.
     * `track_id` with `loaded`: the course that game has loaded. A report for a course the room has left meanwhile
     * (the host changed it while the report was on its way) is dropped: that game is loading again.
     */
    public function update(Request $request, string $code): JsonResponse
    {
        $data = $request->validate([
            // (a request without any of these is refused below: `required_without_all` takes a null colour for none)
            'car_id' => ['sometimes', 'string', Rule::in(array_keys(config('game.cars')))],
            'color' => self::COLOR_RULE,
            'loaded' => ['sometimes', 'boolean'],
            'ready' => ['sometimes', 'boolean'],
            'track_id' => ['sometimes', 'string', 'max:64'],
        ]);
        if (! array_intersect_key($data, array_flip(['car_id', 'color', 'loaded', 'ready']))) {
            throw ValidationException::withMessages(['car_id' => '車両を指定してください']);
        }
        [$room, $member] = $this->membership($request, $code);
        if ((isset($data['car_id']) || array_key_exists('color', $data)) && $room->status === 'racing') {
            return response()->json(['message' => 'レース中は車を変更できません'], 409);
        }
        $changes = [];
        $another = isset($data['car_id']) && $data['car_id'] !== $member->car_id;
        if ($another) {
            $changes += ['car_id' => $data['car_id'], 'color' => null, 'ready' => false];
        }
        if (array_key_exists('color', $data)) {
            $changes['color'] = self::color($data);
        }
        $stale = isset($data['track_id']) && $data['track_id'] !== $room->track_id;
        if ($request->has('loaded') && ! ($stale && $request->boolean('loaded'))) {
            $changes['loaded'] = $request->boolean('loaded');
            if (! $changes['loaded']) {
                $changes['ready'] = false;
            }
        }
        if ($request->has('ready')) {
            if ($request->boolean('ready')) {
                if ($room->status !== 'waiting') {
                    return response()->json(['message' => '準備完了にできるのはレースの前だけです'], 409);
                }
                if (! ($changes['loaded'] ?? $member->loaded)) {
                    return response()->json(['message' => 'コースの読み込みが終わってから準備完了にできます'], 409);
                }
            }
            $changes['ready'] = $request->boolean('ready');
        }
        DB::transaction(function () use ($room, $member, $changes, $another, $data) {
            // (another vehicle against the course as it is under the lock: the host's change of course takes it too)
            $locked = Room::whereKey($room->id)->lockForUpdate()->first();
            if ($another) {
                $this->offered($data['car_id'], $locked->track_id);
            }
            $member->update($changes);
        });
        $room->refresh()->touch();
        $this->broadcastRoom($room);

        return response()->json($room->payload());
    }

    /**
     * The host changes the room's course and / or its time & weather, while the room waits (before the first race
     * and between races). Another course: every game loads it again (`loaded` and `ready` go back for everyone) and
     * a vehicle the course does not offer is replaced; other conditions alone: the readies go back.
     */
    public function settings(Request $request, string $code): JsonResponse
    {
        $data = $request->validate(self::settingsRules());
        if (! isset($data['track_id']) && ! isset($data['time_of_day'])) {
            throw ValidationException::withMessages(['track_id' => 'コースか時間帯・天候を指定してください']);
        }
        [$room] = $this->membership($request, $code);
        if ($room->host_player_id !== $this->player($request)->id) {
            return response()->json(['message' => 'コースと天候を変更できるのはホストだけです'], 403);
        }
        if ($room->status !== 'waiting') {
            return response()->json(['message' => 'コースと天候を変更できるのはレースの前だけです'], 409);
        }
        DB::transaction(fn () => Room::whereKey($room->id)->lockForUpdate()->first()->change($data['track_id'] ?? null, $data['time_of_day'] ?? null));
        $room->touch();
        $this->broadcastRoom($room);

        return response()->json($room->fresh()->payload());
    }

    /**
     * The host takes a member out of the waiting room (a game that never finishes loading, a tab left asleep: the
     * start waits for every member). Only while the room waits; the member can come back with the code.
     */
    public function kick(Request $request, string $code): JsonResponse
    {
        $data = $request->validate(['player_id' => ['required', 'integer']]);
        [$room] = $this->membership($request, $code);
        $host = $this->player($request);
        if ($room->host_player_id !== $host->id) {
            return response()->json(['message' => 'メンバーを外せるのはホストだけです'], 403);
        }
        if ($room->status !== 'waiting') {
            return response()->json(['message' => 'メンバーを外せるのはレースの前だけです'], 409);
        }
        $member = $data['player_id'] === $host->id ? null : $room->members()->with('player')->where('player_id', $data['player_id'])->first();
        if (! $member) {
            return response()->json(['message' => 'そのプレイヤーはこのルームにいません'], 404);
        }
        $this->removeMember($room, $member->player);

        return response()->json($room->fresh()->payload());
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
        // nobody may start the countdown while another game is still loading the course, or before every guest
        // has pressed 準備完了 (the host's own ready is this request)
        if ($this->startBlocker($room)) {
            $this->pruneDisconnected($room, $this->player($request));
            if ($room->members()->count() < $min) {
                return response()->json(['message' => "{$min}人以上そろうとスタートできます"], 409);
            }
            if ($blocker = $this->startBlocker($room)) {
                return response()->json(['message' => $blocker], 409);
            }
        }

        DB::transaction(function () use ($room) {
            // the race uses the readies up: back in the lobby everyone presses again
            $room->members()->update(['finish_ms' => null, 'ready' => false]);
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
        if (! $track) {
            return response()->json(['message' => 'このコースはいま走れません'], 409);
        }
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

    /**
     * Back to the lobby for another race with the same people; with `track_id` / `time_of_day` on another course or
     * in other conditions at once (the host picks the next course on the results screen: one step for everyone).
     */
    public function rematch(Request $request, string $code): JsonResponse
    {
        $data = $request->validate(self::settingsRules());
        [$room] = $this->membership($request, $code);
        if ($room->host_player_id !== $this->player($request)->id) {
            return response()->json(['message' => 'ホストだけが操作できます'], 403);
        }
        DB::transaction(function () use ($room, $data) {
            $room = Room::whereKey($room->id)->lockForUpdate()->first();
            // `loaded` stays: the course is still on everybody's screen (unless it is another one now)
            $room->members()->update(['finish_ms' => null, 'ready' => false]);
            $room->update(['status' => 'waiting', 'start_at_ms' => null]);
            $room->change($data['track_id'] ?? null, $data['time_of_day'] ?? null);
        });
        $room->refresh();
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

    /** @return array<string, list<mixed>> a room's course and conditions, each optional (as `store` takes them) */
    private static function settingsRules(): array
    {
        return [
            'track_id' => ['sometimes', 'string', Rule::in(array_keys(config('game.tracks')))],
            'time_of_day' => ['sometimes', 'string', Rule::in(config('game.times_of_day'))],
        ];
    }

    /** Refuses a vehicle that may not race on the course (the game does not offer it there either). */
    private function offered(string $carId, string $trackId): void
    {
        if (! Vehicles::allowedOn($carId, $trackId)) {
            throw ValidationException::withMessages(['car_id' => config("game.cars.{$carId}.name").'はこのコースでは走れません']);
        }
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

    /** Why the host cannot start yet (a message for the host), or null when everyone is loaded and every guest ready. */
    private function startBlocker(Room $room): ?string
    {
        $loading = $room->members()->with('player')->where('loaded', false)->get();
        if ($loading->isNotEmpty()) {
            return $loading->map(fn (RoomPlayer $m) => $m->player->name)->implode('、').' がコースを読み込んでいます';
        }
        $waiting = $room->members()->where('ready', false)->where('player_id', '!=', $room->host_player_id)->count();

        return $waiting > 0 ? "まだ準備完了になっていないプレイヤーがいます（あと{$waiting}人）" : null;
    }

    /**
     * A full room may hold players who closed the game: drop members no longer on the channel (never `$keep`, the
     * player whose request this is).
     */
    private function pruneDisconnected(Room $room, ?Player $keep = null): void
    {
        try {
            $response = Broadcast::connection('reverb')->getPusher()
                ->get('/channels/presence-'.$room->channelName().'/users');
            $online = collect($response->users ?? [])->pluck('id')->map(fn ($id) => (int) $id)->all();
        } catch (\Throwable) {
            return; // realtime server unreachable: keep everyone
        }
        foreach ($room->members()->with('player')->get() as $member) {
            if ($member->player_id === $keep?->id) {
                continue;
            }
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
