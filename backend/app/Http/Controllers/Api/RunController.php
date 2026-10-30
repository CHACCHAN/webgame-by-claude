<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Player;
use App\Models\Run;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

class RunController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');

        $data = $request->validate([
            'track_id' => ['required', 'string', Rule::in(array_keys(config('game.tracks')))],
            'car_id' => ['required', 'string', Rule::in(array_keys(config('game.cars')))],
            'mode' => ['required', 'string', Rule::in(config('game.modes'))],
            'time_ms' => ['required', 'integer', 'min:1'],
            'sector_ms' => ['required', 'array'],
            'sector_ms.*' => ['integer', 'min:1'],
            'rival_level' => ['nullable', 'string', Rule::in(['rookie', 'ace', 'legend'])],
            'rival_won' => ['nullable', 'boolean'],
            'client_version' => ['nullable', 'string', 'max:20'],
            'ghost' => ['nullable', 'array'],
            'ghost.format' => ['required_with:ghost', 'integer', 'min:1', 'max:100'],
            'ghost.interval_ms' => ['required_with:ghost', 'integer'],
            'ghost.frame_count' => ['required_with:ghost', 'integer', 'min:2'],
            'ghost.data' => ['required_with:ghost', 'string', 'max:'.config('game.ghost.max_base64_length')],
        ]);

        $this->validatePlausibility($data);

        $previousBest = Run::where('player_id', $player->id)
            ->where('track_id', $data['track_id'])
            ->min('time_ms');

        $run = DB::transaction(function () use ($player, $data) {
            $run = Run::create([
                'player_id' => $player->id,
                'track_id' => $data['track_id'],
                'car_id' => $data['car_id'],
                'mode' => $data['mode'],
                'time_ms' => $data['time_ms'],
                'sector_ms' => array_values($data['sector_ms']),
                'rival_level' => $data['rival_level'] ?? null,
                'rival_won' => $data['rival_won'] ?? null,
                'client_version' => $data['client_version'] ?? null,
            ]);

            if (! empty($data['ghost'])) {
                $run->ghost()->create([
                    'format' => $data['ghost']['format'],
                    'interval_ms' => $data['ghost']['interval_ms'],
                    'frame_count' => $data['ghost']['frame_count'],
                    'data' => $data['ghost']['data'],
                ]);
            }

            return $run;
        });

        $isPersonalBest = $previousBest === null || $run->time_ms < $previousBest;
        $bestTime = $isPersonalBest ? $run->time_ms : (int) $previousBest;

        return response()->json([
            'run_id' => $run->id,
            'time_ms' => $run->time_ms,
            'is_personal_best' => $isPersonalBest,
            'previous_best_ms' => $previousBest !== null ? (int) $previousBest : null,
            'rank' => $this->rankOf($data['track_id'], $bestTime, $player->id),
            'total_players' => Run::where('track_id', $data['track_id'])->distinct('player_id')->count('player_id'),
        ], 201);
    }

    public function ghost(Run $run): JsonResponse
    {
        $ghost = $run->ghost;
        if (! $ghost) {
            return response()->json(['message' => 'This run has no ghost recording.'], 404);
        }

        return response()->json([
            'run_id' => $run->id,
            'player_name' => $run->player->name,
            'car_id' => $run->car_id,
            'track_id' => $run->track_id,
            'time_ms' => $run->time_ms,
            'sector_ms' => $run->sector_ms,
            'format' => $ghost->format,
            'interval_ms' => $ghost->interval_ms,
            'frame_count' => $ghost->frame_count,
            'data' => $ghost->data,
        ]);
    }

    /** Rank = 1 + number of other players whose personal best beats this time. */
    private function rankOf(string $trackId, int $timeMs, int $playerId): int
    {
        $faster = DB::table('runs')
            ->where('track_id', $trackId)
            ->where('player_id', '!=', $playerId)
            ->groupBy('player_id')
            ->havingRaw('MIN(time_ms) < ?', [$timeMs])
            ->select('player_id')
            ->get()
            ->count();

        return $faster + 1;
    }

    private function validatePlausibility(array $data): void
    {
        $track = config('game.tracks.'.$data['track_id']);
        $errors = [];

        if ($data['time_ms'] < $track['min_time_ms'] || $data['time_ms'] > $track['max_time_ms']) {
            $errors['time_ms'] = 'The time is outside the plausible range for this track.';
        }

        $sectors = array_values($data['sector_ms']);
        if (count($sectors) !== $track['sectors']) {
            $errors['sector_ms'] = "Exactly {$track['sectors']} cumulative sector splits are required.";
        } else {
            for ($i = 1; $i < count($sectors); $i++) {
                if ($sectors[$i] <= $sectors[$i - 1]) {
                    $errors['sector_ms'] = 'Sector splits must be strictly increasing.';
                }
            }
            if (end($sectors) !== $data['time_ms']) {
                $errors['sector_ms'] = 'The final split must equal the total time.';
            }
        }

        if (! empty($data['ghost'])) {
            $g = $data['ghost'];
            $cfg = config('game.ghost');
            if ($g['interval_ms'] < $cfg['min_interval_ms'] || $g['interval_ms'] > $cfg['max_interval_ms']) {
                $errors['ghost.interval_ms'] = 'Unsupported ghost sampling interval.';
            } else {
                $expected = $data['time_ms'] / $g['interval_ms'];
                if (abs($g['frame_count'] - $expected) > max(10, $expected * 0.05)) {
                    $errors['ghost.frame_count'] = 'Ghost length does not match the run time.';
                }
            }
            if (base64_decode($g['data'], true) === false) {
                $errors['ghost.data'] = 'Ghost data must be base64 encoded.';
            }
        }

        if ($errors) {
            throw ValidationException::withMessages($errors);
        }
    }
}
