<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Str;

class Player extends Model
{
    protected $fillable = ['name', 'token_hash', 'is_bot', 'oidc_sub', 'token_expires_at', 'save', 'save_rev'];

    protected $hidden = ['token_hash', 'oidc_sub', 'save'];

    protected function casts(): array
    {
        return ['is_bot' => 'boolean', 'token_expires_at' => 'datetime', 'save_rev' => 'integer'];
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
     * A member: logged in through Authentik, the records and the save data are theirs wherever they play.
     * The account is Authentik's subject (`oidc_sub`) and nothing else; `id` only ties the records to it.
     */
    public function isMember(): bool
    {
        return $this->oidc_sub !== null;
    }

    /** Neither a member nor a CPU driver: a name typed for a record. */
    public function isGuest(): bool
    {
        return $this->oidc_sub === null && ! $this->is_bot;
    }

    public function scopeGuests(Builder $query): Builder
    {
        return $query->whereNull('oidc_sub')->where('is_bot', false);
    }

    /** What a name may hold (the leaderboard shows it): letters, digits, space, _ - . up to 16 */
    public const NAME_PATTERN = '/^[\p{L}\p{N} _\-\.]+$/u';

    /** A name from outside (Authentik) made to fit. */
    public static function fitName(string $name): string
    {
        $name = trim((string) preg_replace('/[^\p{L}\p{N} _\-\.]+/u', '', $name));

        return $name === '' ? 'MEMBER' : mb_substr($name, 0, 16);
    }

    /**
     * A guest for one sitting: a name typed for a record or for an evening online, and a pass that ends by itself.
     * Returns the player together with the plain-text pass.
     *
     * @return array{0: Player, 1: string}
     */
    public static function registerGuest(string $name): array
    {
        // guests that left nothing (no record) go once their pass is long over
        static::guests()->whereNotNull('token_expires_at')
            ->where('token_expires_at', '<', now()->subDays(2))->whereDoesntHave('runs')->delete();

        $token = Str::random(48);
        $player = static::create([
            'name' => $name,
            'token_hash' => static::hashToken($token),
            'token_expires_at' => now()->addHours((int) config('authentik.guest_hours')),
        ]);

        return [$player, $token];
    }

    /** A CPU driver (seeded ghosts): never logs in. */
    public static function registerBot(string $name): Player
    {
        return static::create(['name' => $name, 'is_bot' => true]);
    }

    /** The member behind an Authentik subject, made on the first login; the name follows Authentik's at every login. */
    public static function forMember(string $sub, string $name): Player
    {
        $player = static::firstOrCreate(['oidc_sub' => $sub], ['name' => static::fitName($name)]);
        if ($player->name !== static::fitName($name)) {
            $player->update(['name' => static::fitName($name)]);
        }

        return $player;
    }

    /**
     * A guest's records become this member's (a record set before logging in, or the player this browser had
     * before accounts came from Authentik). Returns how many runs moved.
     */
    public function claim(Player $guest): int
    {
        if (! $this->isMember() || ! $guest->isGuest() || $guest->is($this)) {
            return 0;
        }
        $moved = Run::where('player_id', $guest->id)->update(['player_id' => $this->id]);
        // (a guest sitting in a room stays until the room is over; the pass ends by itself)
        if (! RoomPlayer::where('player_id', $guest->id)->exists() && ! Room::where('host_player_id', $guest->id)->exists()) {
            $guest->delete();
        } else {
            $guest->update(['token_hash' => null]);
        }

        return $moved;
    }

    public function sessions(): HasMany
    {
        return $this->hasMany(PlayerSession::class);
    }
}
