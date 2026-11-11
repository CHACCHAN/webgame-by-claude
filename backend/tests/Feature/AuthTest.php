<?php

namespace Tests\Feature;

use App\Models\Player;
use App\Models\PlayerSession;
use App\Models\Run;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class AuthTest extends TestCase
{
    use RefreshDatabase;

    private const HEADER = ['X-Touge-Client' => '1'];

    protected function setUp(): void
    {
        parent::setUp();
        config(['authentik.base_url' => 'https://id.test', 'authentik.client_id' => 'game', 'authentik.client_secret' => 'hush', 'authentik.redirect_uri' => '']);
    }

    private function runPayload(int $timeMs): array
    {
        $q = intdiv($timeMs, 4);

        return ['track_id' => 'oboro-downhill', 'car_id' => 'hayate', 'mode' => 'time_attack', 'time_ms' => $timeMs, 'sector_ms' => [$q, $q * 2, $q * 3, $timeMs]];
    }

    /** what Authentik answers now: [token status, token body, userinfo body] */
    private array $authentik = [];

    private function fakeAuthentik(string $sub = 'abc123', array $info = ['preferred_username' => 'ryo']): void
    {
        $this->answers(200, ['access_token' => 'at-1', 'token_type' => 'Bearer', 'id_token' => 'x'], ['sub' => $sub] + $info);
    }

    private function answers(int $status, array $token, array $info): void
    {
        // (stubs given to Http::fake pile up and the first one wins: one stub that reads what is wanted now)
        if (! $this->authentik) {
            Http::fake(fn (Request $r) => str_ends_with($r->url(), '/token/')
                ? Http::response($this->authentik[1], $this->authentik[0])
                : Http::response($this->authentik[2]));
        }
        $this->authentik = [$status, $token, $info];
    }

    /** The whole trip: to Authentik and back; returns the callback's response. */
    private function logIn(array $loginHeaders = []): TestResponse
    {
        $login = $this->get('/api/auth/login', $loginHeaders)->assertRedirect();
        parse_str((string) parse_url($login->headers->get('Location'), PHP_URL_QUERY), $query);
        $state = $login->getCookie('touge_login', false)->getValue();
        $this->assertSame($state, $query['state']);

        return $this->withUnencryptedCookie('touge_login', $state)->get('/api/auth/callback?code=the-code&state='.$state);
    }

    private function asMember(TestResponse $callback): static
    {
        return $this->withoutHeader('Authorization')->withCredentials()->withUnencryptedCookie('touge_session', $callback->getCookie('touge_session', false)->getValue());
    }

    public function test_without_authentik_everyone_is_a_guest(): void
    {
        config(['authentik.client_secret' => '']);
        $this->getJson('/api/content')->assertOk()->assertJsonPath('auth.enabled', false);
        $this->get('/api/auth/login')->assertRedirect('/?login=off');
        $this->getJson('/api/auth/me')->assertOk()->assertExactJson(['enabled' => false, 'member' => null]);
    }

    public function test_login_sends_the_browser_to_authentik_with_pkce_and_this_sites_callback(): void
    {
        $this->getJson('/api/content')->assertOk()->assertJsonPath('auth.enabled', true);
        $login = $this->get('http://touge.test/api/auth/login', ['X-Forwarded-Proto' => 'https'])->assertRedirect();
        $to = $login->headers->get('Location');
        $this->assertStringStartsWith('https://id.test/application/o/authorize/?', $to);
        parse_str((string) parse_url($to, PHP_URL_QUERY), $query);
        $this->assertSame('code', $query['response_type']);
        $this->assertSame('game', $query['client_id']);
        $this->assertSame('https://touge.test/api/auth/callback', $query['redirect_uri']);
        $this->assertSame('openid profile', $query['scope']);
        $this->assertSame('S256', $query['code_challenge_method']);
        $this->assertMatchesRegularExpression('/^[A-Za-z0-9_-]{43}$/', $query['code_challenge']);
        $this->assertStringNotContainsString('hush', $to);

        $cookie = $login->getCookie('touge_login', false);
        $this->assertSame($query['state'], $cookie->getValue());
        $this->assertTrue($cookie->isHttpOnly());
        $this->assertTrue($cookie->isSecure());
        $this->assertSame('lax', $cookie->getSameSite());
    }

    public function test_the_callback_makes_the_member_by_the_subject_and_starts_a_login(): void
    {
        $this->fakeAuthentik();
        $callback = $this->logIn()->assertRedirect('/?login=ok');

        Http::assertSent(fn (Request $r) => $r->url() === 'https://id.test/application/o/token/'
            && $r['grant_type'] === 'authorization_code' && $r['code'] === 'the-code' && $r['client_secret'] === 'hush'
            && $r['redirect_uri'] === 'http://localhost/api/auth/callback' && strlen($r['code_verifier']) === 64);
        Http::assertSent(fn (Request $r) => $r->url() === 'https://id.test/application/o/userinfo/' && $r->hasHeader('Authorization', 'Bearer at-1'));

        $member = Player::sole();
        $this->assertSame('abc123', $member->oidc_sub);
        $this->assertSame('ryo', $member->name);
        $this->assertTrue($member->isMember());
        $this->assertNull($member->token_hash);

        $session = $callback->getCookie('touge_session', false);
        $this->assertTrue($session->isHttpOnly());
        $this->assertSame('lax', $session->getSameSite());
        $this->assertNotSame($session->getValue(), PlayerSession::sole()->token_hash);

        $this->asMember($callback)->getJson('/api/auth/me')->assertOk()
            ->assertExactJson(['enabled' => true, 'member' => ['id' => $member->id, 'name' => 'ryo']]);
        $this->asMember($callback)->getJson('/api/players/me')->assertOk()->assertJsonPath('member', true)->assertJsonPath('name', 'ryo');
        // nothing of the account goes out with the player
        $this->assertArrayNotHasKey('oidc_sub', $member->toArray());
    }

    public function test_the_same_subject_is_the_same_player_whatever_the_name(): void
    {
        $this->fakeAuthentik('abc123', ['preferred_username' => 'ryo']);
        $this->logIn()->assertRedirect('/?login=ok');
        $this->fakeAuthentik('abc123', ['preferred_username' => '<b>高嶺 遼@example.com, the one and only</b>']);
        $this->logIn()->assertRedirect('/?login=ok');
        $this->assertSame(1, Player::count());
        $this->assertSame('b高嶺 遼example.com', Player::sole()->name);

        // another subject with the same name is somebody else
        $this->fakeAuthentik('zzz999', ['preferred_username' => 'ryo']);
        $this->logIn()->assertRedirect('/?login=ok');
        $this->assertSame(2, Player::count());
    }

    public function test_an_answer_for_another_browser_or_a_refusal_logs_nobody_in(): void
    {
        $this->fakeAuthentik();
        $login = $this->get('/api/auth/login')->assertRedirect();
        $state = $login->getCookie('touge_login', false)->getValue();

        // no cookie of the browser that asked; a state that was never given out; a refusal at Authentik
        $this->get('/api/auth/callback?code=the-code&state='.$state)->assertRedirect('/?login=failed');
        $this->withUnencryptedCookie('touge_login', 'made-up')->get('/api/auth/callback?code=the-code&state=made-up')->assertRedirect('/?login=failed');
        $this->withUnencryptedCookie('touge_login', $state)->get('/api/auth/callback?error=access_denied&state='.$state)->assertRedirect('/?login=denied');
        // (and the state is spent)
        $this->withUnencryptedCookie('touge_login', $state)->get('/api/auth/callback?code=the-code&state='.$state)->assertRedirect('/?login=failed');
        Http::assertNothingSent();
        $this->assertSame(0, Player::count());
    }

    public function test_authentik_failing_logs_nobody_in(): void
    {
        $this->answers(400, ['error' => 'invalid_grant'], []);
        $this->logIn()->assertRedirect('/?login=failed')->assertCookieMissing('touge_session');
        $this->answers(200, ['access_token' => 'at-1'], ['name' => 'no subject']);
        $this->logIn()->assertRedirect('/?login=failed');
        Http::assertSentCount(3);
        $this->assertSame(0, Player::count());
    }

    public function test_the_way_back_is_a_path_of_this_site_only(): void
    {
        config(['authentik.client_id' => '']);
        $this->get('/api/auth/login?return=/garage')->assertRedirect('/garage?login=off');
        foreach (['//evil.test', 'https://evil.test', '/\\evil.test', '/a?b=c', "/a\r\nX: y"] as $bad) {
            $this->get('/api/auth/login?return='.urlencode($bad))->assertRedirect('/?login=off');
        }
    }

    public function test_a_member_keeps_records_and_a_change_needs_the_clients_header(): void
    {
        $this->fakeAuthentik();
        $callback = $this->logIn();

        // the cookie alone (a form on another site) changes nothing
        $this->asMember($callback)->postJson('/api/runs', $this->runPayload(150_000))->assertUnauthorized();
        $this->asMember($callback)->postJson('/api/runs', $this->runPayload(150_000), self::HEADER)->assertCreated();
        $this->asMember($callback)->postJson('/api/runs', $this->runPayload(160_000), self::HEADER)->assertCreated();
        $this->asMember($callback)->getJson('/api/players/me')->assertOk()->assertJsonCount(1, 'best_runs')
            ->assertJsonPath('best_runs.0.track_id', 'oboro-downhill')->assertJsonPath('best_runs.0.time_ms', 150_000)
            ->assertJsonPath('best_runs.0.has_ghost', false);
        $this->getJson('/api/tracks/oboro-downhill/leaderboard')->assertOk()
            ->assertJsonPath('entries.0.player_name', 'ryo')->assertJsonPath('entries.0.is_member', true);
        // a member is named in Authentik
        $this->asMember($callback)->patchJson('/api/players/me', ['name' => 'Other'], self::HEADER)->assertForbidden();

        // logging out ends the login on the server too
        $this->asMember($callback)->postJson('/api/auth/logout')->assertUnauthorized();
        $this->asMember($callback)->postJson('/api/auth/logout', [], self::HEADER)->assertOk();
        $this->assertSame(0, PlayerSession::count());
        $this->asMember($callback)->getJson('/api/players/me')->assertUnauthorized();
        $this->asMember($callback)->getJson('/api/auth/me')->assertOk()->assertJsonPath('member', null);
    }

    public function test_a_login_ends_by_itself(): void
    {
        $this->fakeAuthentik();
        $callback = $this->logIn();
        $this->travel(29)->days();
        $this->asMember($callback)->getJson('/api/auth/me')->assertOk()->assertJsonPath('member.name', 'ryo');
        // (that visit renewed it)
        $this->travel(29)->days();
        $this->asMember($callback)->getJson('/api/players/me')->assertOk();
        $this->travel(31)->days();
        $this->asMember($callback)->getJson('/api/players/me')->assertUnauthorized();
        $this->asMember($callback)->getJson('/api/auth/me')->assertOk()->assertJsonPath('member', null);
    }

    public function test_a_guest_is_a_name_and_a_pass_for_the_sitting(): void
    {
        $guest = $this->postJson('/api/players', ['name' => 'Visitor'])->assertCreated()->assertJsonStructure(['id', 'name', 'token', 'expires_at']);
        $token = $guest->json('token');
        $this->withToken($token)->getJson('/api/players/me')->assertOk()->assertJsonPath('member', false);
        $this->withToken($token)->postJson('/api/runs', $this->runPayload(150_000))->assertCreated();
        $this->getJson('/api/tracks/oboro-downhill/leaderboard')->assertJsonPath('entries.0.is_member', false);
        $this->withToken($token)->getJson('/api/players/me/save')->assertForbidden();
        $this->withToken($token)->postJson('/api/auth/claim', ['token' => $token])->assertForbidden();

        $this->travel(25)->hours();
        $this->withToken($token)->getJson('/api/players/me')->assertUnauthorized();
        // the record stays on the board under the name
        $this->getJson('/api/tracks/oboro-downhill/leaderboard')->assertJsonPath('entries.0.player_name', 'Visitor');

        // a guest who left no record is gone once the pass is long over; one with a record stays
        $this->postJson('/api/players', ['name' => 'Passing'])->assertCreated();
        $this->travel(4)->days();
        $this->postJson('/api/players', ['name' => 'Later'])->assertCreated();
        $this->assertEqualsCanonicalizing(['Visitor', 'Later'], Player::pluck('name')->all());
    }

    public function test_a_player_of_before_cannot_come_in_but_a_member_can_claim_the_records(): void
    {
        // as the migration leaves them: a token for good, no end date
        $old = Player::create(['name' => 'OldTimer', 'token_hash' => Player::hashToken('kept-in-the-browser')]);
        Run::create(['player_id' => $old->id] + $this->runPayload(140_000));
        $this->withToken('kept-in-the-browser')->getJson('/api/players/me')->assertUnauthorized();
        $this->withToken('kept-in-the-browser')->postJson('/api/runs', $this->runPayload(139_000))->assertUnauthorized();

        $this->fakeAuthentik();
        $callback = $this->logIn();
        $this->asMember($callback)->postJson('/api/auth/claim', ['token' => 'somebody-elses'], self::HEADER)->assertOk()->assertExactJson(['claimed' => 0]);
        $this->asMember($callback)->postJson('/api/auth/claim', ['token' => 'kept-in-the-browser'], self::HEADER)->assertOk()->assertExactJson(['claimed' => 1]);
        $this->asMember($callback)->postJson('/api/auth/claim', ['token' => 'kept-in-the-browser'], self::HEADER)->assertOk()->assertExactJson(['claimed' => 0]);

        $member = Player::sole();
        $this->assertSame('abc123', $member->oidc_sub);
        $this->assertSame(1, $member->runs()->count());
        $this->getJson('/api/tracks/oboro-downhill/leaderboard')->assertJsonCount(1, 'entries')
            ->assertJsonPath('entries.0.player_name', 'ryo')->assertJsonPath('entries.0.time_ms', 140_000);
    }

    public function test_a_members_save_data_follows_them_and_two_machines_do_not_overwrite_each_other(): void
    {
        $this->fakeAuthentik();
        $a = $this->logIn();
        $this->asMember($a)->getJson('/api/players/me/save')->assertOk()->assertExactJson(['rev' => 0, 'save' => null]);
        $this->asMember($a)->putJson('/api/players/me/save', ['rev' => 0, 'save' => ['favorites' => ['hayate'], 'rivals' => ['oboro-downhill' => ['wins' => 2]]]], self::HEADER)
            ->assertOk()->assertExactJson(['rev' => 1]);

        // another machine, the same member
        $b = $this->logIn();
        $this->asMember($b)->getJson('/api/players/me/save')->assertOk()
            ->assertJsonPath('rev', 1)->assertJsonPath('save.favorites.0', 'hayate')->assertJsonPath('save.rivals.oboro-downhill.wins', 2);
        $this->asMember($b)->putJson('/api/players/me/save', ['rev' => 1, 'save' => ['favorites' => ['r34']]], self::HEADER)->assertOk()->assertExactJson(['rev' => 2]);
        // the first machine still has revision 1: it gets what is there now, to merge
        $this->asMember($a)->putJson('/api/players/me/save', ['rev' => 1, 'save' => ['favorites' => ['supra']]], self::HEADER)
            ->assertStatus(409)->assertJsonPath('rev', 2)->assertJsonPath('save.favorites.0', 'r34');

        $this->asMember($a)->putJson('/api/players/me/save', ['rev' => 2, 'save' => ['blob' => str_repeat('x', 70_000)]], self::HEADER)->assertStatus(413);
        $this->asMember($a)->putJson('/api/players/me/save', ['rev' => 2, 'save' => 'text'], self::HEADER)->assertUnprocessable();
        $this->assertSame(1, Player::count());
    }
}
