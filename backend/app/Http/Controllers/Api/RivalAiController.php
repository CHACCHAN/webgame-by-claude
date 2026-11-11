<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\RivalMind;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

/**
 * The rivals' lines and decisions (config/llm.php). The requests carry facts only (ids, numbers, the rival's
 * name and short description), never a prompt: this is not a relay to the model for whoever finds the URL.
 * 503 = no model to ask (no key, or all of them failed): the game then uses its own lines and rules.
 */
class RivalAiController extends Controller
{
    public function taunt(Request $request, RivalMind $mind): JsonResponse
    {
        $in = $request->validate($this->rival() + [
            'course' => ['required', Rule::in(array_keys(config('game.tracks')))],
            'tod' => ['required', Rule::in(config('game.times_of_day'))],
            'player_car' => ['required', Rule::in(array_keys(config('game.cars')))],
            'rival_car' => ['required', Rule::in(array_keys(config('game.cars')))],
            'wins' => ['required', 'integer', 'between:0,9999'],
            'losses' => ['required', 'integer', 'between:0,9999'],
            'medal' => ['required', Rule::in(['none', 'bronze', 'silver', 'gold'])],
            'moment' => ['required', Rule::in(['before', 'won', 'lost'])],
            'gap_s' => ['nullable', 'numeric', 'between:0,3600'],
        ]);
        $in['rival'] = $this->clean($in['rival']);
        $in['course_name'] = config('game.tracks')[$in['course']]['name'];
        $in['player_car_name'] = config('game.cars')[$in['player_car']]['name'];
        $in['rival_car_name'] = config('game.cars')[$in['rival_car']]['name'];

        $out = $mind->available() ? $mind->taunt($in) : null;

        return $out ? response()->json($out) : response()->json(['message' => 'no model available'], 503);
    }

    public function decide(Request $request, RivalMind $mind): JsonResponse
    {
        $in = $request->validate($this->rival() + [
            'level' => ['required', Rule::in(['rookie', 'ace', 'legend'])],
            'remaining_m' => ['required', 'numeric', 'between:0,50000'],
            'rival_ahead' => ['required', 'boolean'],
            'gap_m' => ['required', 'numeric', 'between:0,1000'],
            // + = the car behind is the faster one
            'closing_kmh' => ['required', 'numeric', 'between:-1500,1500'],
            // where the player is, seen from the rival: + = to its left
            'lateral_m' => ['required', 'numeric', 'between:-30,30'],
            'corner' => ['required', 'array'],
            'corner.distance_m' => ['required', 'numeric', 'between:0,20000'],
            'corner.kind' => ['required', Rule::in(RivalMind::CORNERS)],
            'blocks' => ['required', 'integer', 'between:0,999'],
            'horns' => ['required', 'integer', 'between:0,999'],
        ]);
        $in['rival'] = $this->clean($in['rival']);

        $out = $mind->available() ? $mind->decide($in) : null;

        return $out ? response()->json($out) : response()->json(['message' => 'no model available'], 503);
    }

    /** Who speaks: the course's rival as the client knows it (short, single-line texts). */
    private function rival(): array
    {
        return [
            'rival' => ['required', 'array'],
            'rival.name' => ['required', 'string', 'max:24'],
            'rival.title' => ['required', 'string', 'max:60'],
            'rival.description' => ['nullable', 'string', 'max:200'],
        ];
    }

    private function clean(array $rival): array
    {
        return array_map(fn ($v) => trim((string) preg_replace('/[\x00-\x1F\x7F]+/u', ' ', (string) $v)), $rival);
    }
}
