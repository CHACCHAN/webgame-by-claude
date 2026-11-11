<?php

/*
| Members log in through the owner's Authentik (OpenID Connect, authorization code flow with PKCE; the code is
| exchanged here, the client secret never leaves the server). Whoever logs in is an account of the game; everyone
| else is a guest (app/Http/Controllers/Api/AuthController.php). Without these values there is no login: all guests.
|
| The provider in Authentik needs one redirect URI: <the game's public address>/api/auth/callback
*/

return [
    'base_url' => rtrim(trim((string) env('AUTHENTIK_BASE_URL', '')), '/'),
    'client_id' => trim((string) env('AUTHENTIK_CLIENT_ID', '')),
    'client_secret' => trim((string) env('AUTHENTIK_CLIENT_SECRET', '')),
    // only when the address the visitor sees cannot be told from the request (a proxy that rewrites the host)
    'redirect_uri' => trim((string) env('AUTHENTIK_REDIRECT_URI', '')),
    'scopes' => 'openid profile',

    // a login lasts this long without a visit (each visit renews it); then Authentik is asked again
    'session_days' => (int) env('AUTH_SESSION_DAYS', 30),
    'cookie' => 'touge_session',

    // a guest's pass: for the sitting only (one record, one evening of online races)
    'guest_hours' => 24,
    // a member's save data (settings that follow the player, favourites, records against rivals …), JSON
    'save_max_bytes' => 65536,
];
