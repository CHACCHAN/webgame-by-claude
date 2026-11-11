<?php

namespace App\Http\Middleware;

use App\Models\Player;
use App\Services\MemberSession;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Who plays: a guest by the pass of this sitting (a bearer token that ends by itself), or a member by the login
 * cookie (Authentik, App\Services\MemberSession). A token without an end date is a player of before the accounts
 * came from Authentik: it lets nobody in any more (a member can still claim its records).
 */
class AuthenticatePlayer
{
    public function __construct(private MemberSession $sessions) {}

    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->bearerToken();
        $player = $token
            ? Player::guests()->where('token_hash', Player::hashToken($token))->where('token_expires_at', '>', now())->first()
            : $this->sessions->member($request);

        if (! $player) {
            return response()->json(['message' => 'Unauthenticated player.'], 401);
        }

        $request->attributes->set('player', $player);

        return $next($request);
    }
}
