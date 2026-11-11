<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Player;
use App\Services\MemberSession;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Throwable;

/**
 * Members log in through the owner's Authentik (OpenID Connect: authorization code + PKCE; config/authentik.php).
 * The browser is sent there and comes back with a code; this server changes the code for the member's subject and
 * name (the client secret and the tokens never reach the browser) and starts a login of its own (MemberSession).
 * The account is the subject (`sub`): the same person from any browser is the same player.
 */
class AuthController extends Controller
{
    /** the browser's half of a login under way (the other half is in the cache under its hash) */
    private const FLOW_COOKIE = 'touge_login';

    private const FLOW_MINUTES = 10;

    public function __construct(private MemberSession $sessions) {}

    public static function enabled(): bool
    {
        return config('authentik.base_url') !== '' && config('authentik.client_id') !== '' && config('authentik.client_secret') !== '';
    }

    /** Off to Authentik. `return`: where in the game to come back to (a path of this site only). */
    public function login(Request $request): RedirectResponse
    {
        $return = $this->localPath((string) $request->query('return', '/'));
        if (! self::enabled()) {
            return $this->back($return, 'off');
        }

        $state = Str::random(40);
        $verifier = Str::random(64);
        $redirect = $this->redirectUri($request);
        Cache::put($this->flowKey($state), ['verifier' => $verifier, 'return' => $return, 'redirect' => $redirect], now()->addMinutes(self::FLOW_MINUTES));

        $query = http_build_query([
            'response_type' => 'code',
            'client_id' => config('authentik.client_id'),
            'redirect_uri' => $redirect,
            'scope' => config('authentik.scopes'),
            'state' => $state,
            'code_challenge' => rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '='),
            'code_challenge_method' => 'S256',
        ]);

        return redirect()->away(config('authentik.base_url').'/application/o/authorize/?'.$query)
            ->withCookie($this->sessions->make(self::FLOW_COOKIE, $state, self::FLOW_MINUTES, '/api/auth', $request));
    }

    /** Back from Authentik with a code (or a refusal). */
    public function callback(Request $request): RedirectResponse
    {
        $state = (string) $request->query('state', '');
        // the answer must come back to the browser that asked (else somebody could log a visitor in as themselves)
        $own = is_string($cookie = $request->cookie(self::FLOW_COOKIE)) && $state !== '' && hash_equals($cookie, $state);
        $flow = $own ? Cache::pull($this->flowKey($state)) : null;
        $done = fn (string $result, ?string $return = null) => $this->back($return ?? '/', $result)
            ->withCookie($this->sessions->make(self::FLOW_COOKIE, '', -60 * 24, '/api/auth', $request));

        if (! self::enabled() || ! is_array($flow)) {
            return $done('failed');
        }
        if ($request->query('error') || ! is_string($code = $request->query('code')) || $code === '') {
            return $done($request->query('error') === 'access_denied' ? 'denied' : 'failed', $flow['return']);
        }

        $member = $this->memberOf($code, $flow);
        if (! $member) {
            return $done('failed', $flow['return']);
        }
        $player = Player::forMember($member['sub'], $member['name']);

        return $done('ok', $flow['return'])->withCookie($this->sessions->start($player, $request));
    }

    /** Who this browser is logged in as (null: a guest), and whether there is a login at all. */
    public function me(Request $request): JsonResponse
    {
        $session = self::enabled() ? $this->sessions->find($request) : null;
        $player = $session?->player;
        $response = response()->json([
            'enabled' => self::enabled(),
            'member' => $player?->isMember() ? ['id' => $player->id, 'name' => $player->name] : null,
        ]);

        return $player?->isMember() ? $response->withCookie($this->sessions->renew($session, $request)) : $response;
    }

    public function logout(Request $request): JsonResponse
    {
        if (! $request->headers->has(MemberSession::CLIENT_HEADER)) {
            return response()->json(['message' => 'Unauthenticated player.'], 401);
        }

        return response()->json(['member' => null])->withCookie($this->sessions->finish($request));
    }

    /**
     * A member takes over a guest's records with that guest's token: the record just set before logging in, or
     * the player this browser kept from before the accounts came from Authentik.
     */
    public function claim(Request $request): JsonResponse
    {
        /** @var Player $player */
        $player = $request->attributes->get('player');
        if (! $player->isMember()) {
            return response()->json(['message' => 'Members only.'], 403);
        }
        $data = $request->validate(['token' => ['required', 'string', 'max:128']]);
        $guest = Player::guests()->where('token_hash', Player::hashToken($data['token']))->first();

        return response()->json(['claimed' => $guest ? $player->claim($guest) : 0]);
    }

    /** @return array{sub: string, name: string}|null */
    private function memberOf(string $code, array $flow): ?array
    {
        $base = config('authentik.base_url');
        try {
            $token = Http::asForm()->acceptJson()->connectTimeout(4)->timeout(10)->post($base.'/application/o/token/', [
                'grant_type' => 'authorization_code',
                'code' => $code,
                'redirect_uri' => $flow['redirect'],
                'client_id' => config('authentik.client_id'),
                'client_secret' => config('authentik.client_secret'),
                'code_verifier' => $flow['verifier'],
            ]);
            $access = $token->json('access_token');
            if (! $token->successful() || ! is_string($access) || $access === '') {
                Log::warning('authentik: the token endpoint answered '.$token->status());

                return null;
            }
            $info = Http::withToken($access)->acceptJson()->connectTimeout(4)->timeout(10)->get($base.'/application/o/userinfo/');
            $sub = $info->json('sub');
            if (! $info->successful() || ! is_string($sub) || $sub === '' || strlen($sub) > 191) {
                Log::warning('authentik: the userinfo endpoint answered '.$info->status());

                return null;
            }
            $name = collect(['preferred_username', 'nickname', 'name'])
                ->map(fn (string $key) => $info->json($key))->first(fn ($v) => is_string($v) && trim($v) !== '');

            return ['sub' => $sub, 'name' => (string) ($name ?? '')];
        } catch (Throwable $e) {
            // (nothing of the request goes into the log: it carries the secret and the code)
            Log::warning('authentik: '.class_basename($e));

            return null;
        }
    }

    private function redirectUri(Request $request): string
    {
        $fixed = (string) config('authentik.redirect_uri');

        return $fixed !== '' ? $fixed : MemberSession::origin($request).'/api/auth/callback';
    }

    /** Only a path of this site: never an address somebody put into a link. */
    private function localPath(string $path): string
    {
        return preg_match('#^/(?![/\\\\])[A-Za-z0-9\-._~/]*$#', $path) ? $path : '/';
    }

    private function back(string $path, string $result): RedirectResponse
    {
        // (a relative address: this server sees http behind the tunnel and would write that into an absolute one)
        return new RedirectResponse($path.'?login='.$result);
    }

    private function flowKey(string $state): string
    {
        return 'login:'.hash('sha256', $state);
    }
}
