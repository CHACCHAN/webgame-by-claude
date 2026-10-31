<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Run;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;
use Throwable;

class MetaController extends Controller
{
    public function health(): JsonResponse
    {
        try {
            DB::select('select 1');
            $db = 'ok';
        } catch (Throwable) {
            $db = 'unavailable';
        }

        return response()->json([
            'status' => $db === 'ok' ? 'ok' : 'degraded',
            'database' => $db,
            'version' => config('game.version'),
        ], $db === 'ok' ? 200 : 503);
    }

    public function content(): JsonResponse
    {
        $tracks = collect(config('game.tracks'))->map(fn ($t, $id) => [
            'id' => $id,
            'name' => $t['name'],
            'name_en' => $t['name_en'],
            'sectors' => $t['sectors'],
            'total_runs' => Run::where('track_id', $id)->count(),
        ])->values();

        $cars = collect(config('game.cars'))->map(fn ($c, $id) => ['id' => $id] + $c)->values();

        // the Pusher-protocol app key is public by design (the secret stays on the server)
        $realtime = [
            'enabled' => config('broadcasting.default') === 'reverb',
            'key' => config('broadcasting.connections.reverb.key'),
            'max_players' => (int) config('game.online.max_players'),
        ];

        return response()->json(['version' => config('game.version'), 'tracks' => $tracks, 'cars' => $cars, 'realtime' => $realtime]);
    }
}
