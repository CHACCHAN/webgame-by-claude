<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class RoomPlayer extends Model
{
    protected $fillable = ['room_id', 'player_id', 'car_id', 'slot', 'finish_ms'];

    protected function casts(): array
    {
        return ['slot' => 'integer', 'finish_ms' => 'integer'];
    }

    public function room(): BelongsTo
    {
        return $this->belongsTo(Room::class);
    }

    public function player(): BelongsTo
    {
        return $this->belongsTo(Player::class);
    }
}
