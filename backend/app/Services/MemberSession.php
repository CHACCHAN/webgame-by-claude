<?php

namespace App\Services;

use App\Models\Player;
use App\Models\PlayerSession;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Cookie;

/**
 * A member's login on one browser. The account itself lives in Authentik; what the browser keeps is an opaque
 * token in a cookie no script can read (HttpOnly, SameSite=Lax, Secure over https), and the table keeps its hash.
 * It ends by logging out, or by itself after `authentik.session_days` without a visit.
 */
class MemberSession
{
    /** A request that changes something must carry this header when the cookie is what says who it is (CSRF). */
    public const CLIENT_HEADER = 'X-Touge-Client';

    public function start(Player $player, Request $request): Cookie
    {
        PlayerSession::where('expires_at', '<', now())->delete();
        $token = Str::random(64);
        $player->sessions()->create(['token_hash' => Player::hashToken($token), 'expires_at' => $this->end()]);

        return $this->cookie($token, $request);
    }

    public function find(Request $request): ?PlayerSession
    {
        $token = $request->cookie($this->name());
        if (! is_string($token) || $token === '') {
            return null;
        }

        return PlayerSession::with('player')->where('token_hash', Player::hashToken($token))
            ->where('expires_at', '>', now())->first();
    }

    /** The member a cookie stands for; requests that change something only with the client's header. */
    public function member(Request $request): ?Player
    {
        if (! $request->isMethodSafe() && ! $request->headers->has(self::CLIENT_HEADER)) {
            return null;
        }
        $player = $this->find($request)?->player;

        return $player?->isMember() ? $player : null;
    }

    /** A visit: the login lasts another `session_days` from now. */
    public function renew(PlayerSession $session, Request $request): Cookie
    {
        $session->update(['expires_at' => $this->end()]);

        return $this->cookie((string) $request->cookie($this->name()), $request);
    }

    public function finish(Request $request): Cookie
    {
        $this->find($request)?->delete();

        return $this->make($this->name(), '', -60 * 24, '/', $request);
    }

    public function make(string $name, string $value, int $minutes, string $path, Request $request): Cookie
    {
        return cookie($name, $value, $minutes, $path, null, self::https($request), true, false, 'lax');
    }

    /** The address the visitor typed: nginx talks http to us, the tunnel says what it was outside. */
    public static function origin(Request $request): string
    {
        return (self::https($request) ? 'https' : 'http').'://'.$request->getHttpHost();
    }

    public static function https(Request $request): bool
    {
        $forwarded = strtolower(trim(explode(',', (string) $request->headers->get('X-Forwarded-Proto', ''))[0]));

        return $forwarded === 'https' || ($forwarded === '' && $request->isSecure());
    }

    private function cookie(string $token, Request $request): Cookie
    {
        return $this->make($this->name(), $token, $this->days() * 24 * 60, '/', $request);
    }

    private function end(): \DateTimeInterface
    {
        return now()->addDays($this->days());
    }

    private function days(): int
    {
        return max(1, (int) config('authentik.session_days'));
    }

    private function name(): string
    {
        return (string) config('authentik.cookie');
    }
}
