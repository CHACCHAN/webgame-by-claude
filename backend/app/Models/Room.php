<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Room extends Model
{
    /** unambiguous characters for spoken / typed room codes */
    private const CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

    protected $fillable = ['code', 'host_player_id', 'track_id', 'status', 'race_no', 'start_at_ms'];

    protected function casts(): array
    {
        return ['race_no' => 'integer', 'start_at_ms' => 'integer'];
    }

    public function members(): HasMany
    {
        return $this->hasMany(RoomPlayer::class)->orderBy('slot');
    }

    public function host(): BelongsTo
    {
        return $this->belongsTo(Player::class, 'host_player_id');
    }

    public static function newCode(): string
    {
        do {
            $code = '';
            for ($i = 0; $i < 4; $i++) {
                $code .= self::CODE_ALPHABET[random_int(0, strlen(self::CODE_ALPHABET) - 1)];
            }
        } while (static::where('code', $code)->exists());

        return $code;
    }

    public function memberFor(Player $player): ?RoomPlayer
    {
        return $this->members()->where('player_id', $player->id)->first();
    }

    /** Presence channel name (without the "presence-" prefix Pusher clients add). */
    public function channelName(): string
    {
        return 'room.'.$this->code;
    }

    /** Snapshot sent to clients over HTTP and the room's presence channel. */
    public function payload(): array
    {
        $this->load('members.player');

        return [
            'code' => $this->code,
            'track_id' => $this->track_id,
            'status' => $this->status,
            'race_no' => $this->race_no,
            'host_id' => $this->host_player_id,
            'start_at_ms' => $this->start_at_ms,
            'server_time_ms' => (int) floor(microtime(true) * 1000),
            'max_players' => (int) config('game.online.max_players'),
            'players' => $this->members->map(fn (RoomPlayer $m) => [
                'id' => $m->player_id,
                'name' => $m->player->name,
                'car_id' => $m->car_id,
                'slot' => $m->slot,
                'finish_ms' => $m->finish_ms,
            ])->values()->all(),
        ];
    }
}
