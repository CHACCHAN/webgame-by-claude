<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Player;
use App\Models\Run;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class PlayerController extends Controller
{
    private const NAME_RULES = ['required', 'string', 'min:1', 'max:16', 'regex:/^[\p{L}\p{N} _\-\.]+$/u'];

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate(['name' => self::NAME_RULES]);
        [$player, $token] = Player::register(trim($data['name']));

        return response()->json([
            'id' => $player->id,
            'name' => $player->name,
            'token' => $token,
        ], 201);
    }

    public function show(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');

        $bests = Run::query()
            ->where('player_id', $player->id)
            ->selectRaw('track_id, car_id, MIN(time_ms) AS best_ms, COUNT(*) AS runs')
            ->groupBy('track_id', 'car_id')
            ->get();

        return response()->json([
            'id' => $player->id,
            'name' => $player->name,
            'bests' => $bests,
        ]);
    }

    public function update(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');
        $data = $request->validate(['name' => self::NAME_RULES]);
        $player->update(['name' => trim($data['name'])]);

        return response()->json(['id' => $player->id, 'name' => $player->name]);
    }
}
