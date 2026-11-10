<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A player's seat in a room. `loaded`: their game shows the room's course (reported by the client by itself).
 * `ready`: they pressed 準備完了 (never true unless loaded; the host needs none, the start button is the host's).
 */
class RoomPlayer extends Model
{
    protected $fillable = ['room_id', 'player_id', 'car_id', 'slot', 'loaded', 'ready', 'finish_ms'];

    /** a new seat is neither loaded nor ready, also on the model just created (as the columns' defaults) */
    protected $attributes = ['loaded' => false, 'ready' => false];

    protected function casts(): array
    {
        return ['slot' => 'integer', 'loaded' => 'boolean', 'ready' => 'boolean', 'finish_ms' => 'integer'];
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
