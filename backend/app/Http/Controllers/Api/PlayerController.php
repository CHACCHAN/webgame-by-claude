<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Player;
use App\Models\Run;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class PlayerController extends Controller
{
    private const NAME_RULES = ['required', 'string', 'min:1', 'max:16', 'regex:'.Player::NAME_PATTERN];

    /** A guest: the name typed for a record (or for an evening online) and a pass for this sitting. */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate(['name' => self::NAME_RULES]);
        [$player, $token] = Player::registerGuest(trim($data['name']));

        return response()->json([
            'id' => $player->id,
            'name' => $player->name,
            'token' => $token,
            'expires_at' => $player->token_expires_at->toIso8601String(),
        ], 201);
    }

    public function show(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');

        $bests = Run::query()
            ->where('player_id', $player->id)
            ->whereIn('car_id', array_keys(config('game.cars')))
            ->selectRaw('track_id, car_id, MIN(time_ms) AS best_ms, COUNT(*) AS runs')
            ->groupBy('track_id', 'car_id')
            ->get();

        return response()->json([
            'id' => $player->id,
            'name' => $player->name,
            'member' => $player->isMember(),
            'bests' => $bests,
            // the best run per course, with its ghost if it has one (a member on a new machine fetches these)
            'best_runs' => collect(array_keys(config('game.tracks')))->map(fn (string $track) => Run::query()
                ->where('player_id', $player->id)->where('track_id', $track)
                ->whereIn('car_id', array_keys(config('game.cars')))
                ->withExists('ghost')->orderBy('time_ms')->orderBy('id')->first())
                ->filter()->map(fn (Run $run) => [
                    'run_id' => $run->id, 'track_id' => $run->track_id, 'car_id' => $run->car_id,
                    'time_ms' => $run->time_ms, 'sector_ms' => $run->sector_ms, 'has_ghost' => (bool) $run->ghost_exists,
                    'created_at' => $run->created_at?->toIso8601String(),
                ])->values(),
        ]);
    }

    public function update(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');
        if ($player->isMember()) {
            // a member's name is Authentik's (taken again at every login)
            return response()->json(['message' => 'A member is named in Authentik.'], 403);
        }
        $data = $request->validate(['name' => self::NAME_RULES]);
        $player->update(['name' => trim($data['name'])]);

        return response()->json(['id' => $player->id, 'name' => $player->name]);
    }

    /** A member's save data: what follows the person from one machine to the next (the client decides what is in it). */
    public function save(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');
        if (! $player->isMember()) {
            return response()->json(['message' => 'Members only.'], 403);
        }

        return response()->json(['rev' => $player->save_rev, 'save' => $player->save !== null ? json_decode($player->save) : null]);
    }

    /**
     * Written with the revision it was read at; a save changed meanwhile on another machine comes back with a 409
     * for the client to merge and send again.
     */
    public function storeSave(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');
        if (! $player->isMember()) {
            return response()->json(['message' => 'Members only.'], 403);
        }
        $data = $request->validate(['rev' => ['required', 'integer', 'min:0'], 'save' => ['required', 'array']]);
        $json = json_encode($data['save'], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if ($json === false || strlen($json) > (int) config('authentik.save_max_bytes')) {
            return response()->json(['message' => 'The save data is too large.'], 413);
        }

        // (the revision in the condition: of two machines writing at once, one wins and the other merges)
        $written = Player::whereKey($player->id)->where('save_rev', $data['rev'])
            ->update(['save' => $json, 'save_rev' => $data['rev'] + 1]);
        if (! $written) {
            $player->refresh();

            return response()->json(['rev' => $player->save_rev, 'save' => $player->save !== null ? json_decode($player->save) : null], 409);
        }

        return response()->json(['rev' => $data['rev'] + 1]);
    }
}
