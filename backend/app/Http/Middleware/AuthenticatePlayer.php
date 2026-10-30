<?php

namespace App\Http\Middleware;

use App\Models\Player;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Lightweight bearer-token auth for anonymous players. The token is issued
 * once on registration and only its SHA-256 hash is stored.
 */
class AuthenticatePlayer
{
    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->bearerToken();
        $player = $token ? Player::where('token_hash', Player::hashToken($token))->first() : null;

        if (! $player) {
            return response()->json(['message' => 'Unauthenticated player.'], 401);
        }

        $request->attributes->set('player', $player);

        return $next($request);
    }
}
