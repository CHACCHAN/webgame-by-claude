<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Support\Facades\DB;

class Run extends Model
{
    protected $fillable = [
        'player_id', 'track_id', 'car_id', 'mode', 'time_ms', 'sector_ms',
        'rival_level', 'rival_won', 'client_version',
    ];

    protected function casts(): array
    {
        return [
            'sector_ms' => 'array',
            'time_ms' => 'integer',
            'rival_won' => 'boolean',
        ];
    }

    public function player(): BelongsTo
    {
        return $this->belongsTo(Player::class);
    }

    public function ghost(): HasOne
    {
        return $this->hasOne(Ghost::class);
    }

    /**
     * Each player's single best run on a track (optionally for one car),
     * ordered fastest first. Ties are broken by who set the time first.
     */
    public static function personalBests(string $trackId, ?string $carId = null): Builder
    {
        $ranked = DB::table('runs')
            ->select('runs.id')
            ->selectRaw('ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY time_ms ASC, id ASC) AS rn')
            ->where('track_id', $trackId)
            ->when($carId, fn ($q) => $q->where('car_id', $carId));

        return static::query()
            ->joinSub($ranked, 'ranked', 'ranked.id', '=', 'runs.id')
            ->where('ranked.rn', 1)
            ->orderBy('runs.time_ms')
            ->orderBy('runs.id')
            ->select('runs.*');
    }
}
