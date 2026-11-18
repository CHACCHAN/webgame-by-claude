<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Run;
use App\Support\Vehicles;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

class LeaderboardController extends Controller
{
    public function index(Request $request, string $trackId): JsonResponse
    {
        abort_unless(config("game.tracks.$trackId"), 404, 'Unknown track.');

        $data = $request->validate([
            // (a vehicle the course does not offer has no list there)
            'car_id' => ['nullable', 'string', Rule::in(Vehicles::on($trackId))],
            'limit' => ['nullable', 'integer', 'min:1', 'max:100'],
        ]);
        $limit = $data['limit'] ?? 50;

        $runs = Run::personalBests($trackId, $data['car_id'] ?? null)
            ->with('player:id,name,is_bot,oidc_sub')
            ->withExists('ghost')
            ->limit($limit)
            ->get();

        $entries = $runs->values()->map(fn (Run $run, int $i) => [
            'rank' => $i + 1,
            'run_id' => $run->id,
            'player_id' => $run->player_id,
            'player_name' => $run->player->name,
            'is_bot' => $run->player->is_bot,
            'is_member' => $run->player->isMember(),
            'car_id' => $run->car_id,
            'mode' => $run->mode,
            'time_ms' => $run->time_ms,
            'sector_ms' => $run->sector_ms,
            'has_ghost' => (bool) $run->ghost_exists,
            'created_at' => $run->created_at?->toIso8601String(),
        ]);

        return response()->json([
            'track_id' => $trackId,
            'car_id' => $data['car_id'] ?? null,
            'entries' => $entries,
        ]);
    }
}
