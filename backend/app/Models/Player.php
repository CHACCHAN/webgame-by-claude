<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Str;

class Player extends Model
{
    protected $fillable = ['name', 'token_hash', 'is_bot'];

    protected $hidden = ['token_hash'];

    protected function casts(): array
    {
        return ['is_bot' => 'boolean'];
    }

    public function runs(): HasMany
    {
        return $this->hasMany(Run::class);
    }

    public static function hashToken(string $token): string
    {
        return hash('sha256', $token);
    }

    /**
     * Create a player and return it together with its plain-text token.
     *
     * @return array{0: Player, 1: string}
     */
    public static function register(string $name, bool $isBot = false): array
    {
        $token = Str::random(48);
        $player = static::create([
            'name' => $name,
            'token_hash' => static::hashToken($token),
            'is_bot' => $isBot,
        ]);

        return [$player, $token];
    }
}
