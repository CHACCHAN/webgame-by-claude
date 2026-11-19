<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class RivalAiTest extends TestCase
{
    use RefreshDatabase;

    private const RIVAL = ['name' => '高嶺 遼', 'title' => 'LOCAL ACE / 朧峠の地元最速', 'description' => '朧峠を知り尽くした地元最速。'];

    private function tauntPayload(array $overrides = []): array
    {
        return array_merge([
            'rival' => self::RIVAL, 'course' => 'oboro-downhill', 'tod' => 'rain', 'player_car' => 'shiden', 'rival_car' => 'raijin',
            'wins' => 0, 'losses' => 2, 'medal' => 'silver', 'moment' => 'before',
        ], $overrides);
    }

    private function decidePayload(array $overrides = []): array
    {
        return array_merge([
            'rival' => self::RIVAL, 'level' => 'ace', 'remaining_m' => 1200, 'rival_ahead' => true, 'gap_m' => 6, 'closing_kmh' => 9,
            'lateral_m' => -1.4, 'corner' => ['distance_m' => 80, 'kind' => 'left_hairpin'], 'blocks' => 0, 'horns' => 0,
        ], $overrides);
    }

    private function answer(array $message): array
    {
        return ['choices' => [['index' => 0, 'finish_reason' => 'stop', 'message' => ['role' => 'assistant'] + $message]]];
    }

    protected function setUp(): void
    {
        parent::setUp();
        config(['llm.key' => 'test-key', 'llm.url' => 'https://llm.test/v1/chat/completions', 'llm.taunt_models' => ['first', 'second'], 'llm.decide_models' => ['judge']]);
    }

    public function test_without_a_key_the_endpoints_say_so_and_ask_nobody(): void
    {
        config(['llm.key' => null]);
        Http::fake();
        $this->postJson('/api/ai/taunt', $this->tauntPayload())->assertStatus(503);
        $this->postJson('/api/ai/decide', $this->decidePayload())->assertStatus(503);
        Http::assertNothingSent();
        $this->getJson('/api/content')->assertOk()->assertJsonPath('ai.enabled', false);
    }

    public function test_a_taunt_is_asked_with_the_key_in_a_header_and_the_facts_in_the_prompt(): void
    {
        Http::fake(['llm.test/*' => Http::response($this->answer(['content' => "「雨のFDじゃ俺の背中も見えないさ。」\n"]))]);
        $this->postJson('/api/ai/taunt', $this->tauntPayload())->assertOk()
            ->assertExactJson(['line' => '雨のFDじゃ俺の背中も見えないさ。', 'model' => 'first']);
        Http::assertSent(function (Request $request) {
            $body = $request->data();
            $prompt = $body['messages'][0]['content'].$body['messages'][1]['content'];

            return $request->url() === 'https://llm.test/v1/chat/completions'
                && $request->hasHeader('X-Gravitee-Api-Key', 'test-key')
                && $body['model'] === 'first'
                && str_contains($prompt, '高嶺 遼') && str_contains($prompt, '朧峠 ダウンヒル') && str_contains($prompt, '深夜・雨')
                && str_contains($prompt, 'RX-7 (FD3S)') && str_contains($prompt, 'IMPREZA WRX STI') && str_contains($prompt, '0勝2敗') && str_contains($prompt, '銀')
                && ! str_contains(json_encode($body), 'test-key');
        });
        $this->getJson('/api/content')->assertOk()->assertJsonPath('ai.enabled', true);
    }

    public function test_the_next_model_is_asked_when_one_fails_or_says_nothing(): void
    {
        Http::fake(fn (Request $request) => $request->data()['model'] === 'first'
            ? Http::response(['error' => 'busy'], 504)
            : Http::response($this->answer(['content' => 'また負けに来たのか。'])));
        $this->postJson('/api/ai/taunt', $this->tauntPayload(['moment' => 'won', 'gap_s' => 1.25]))->assertOk()
            ->assertExactJson(['line' => 'また負けに来たのか。', 'model' => 'second']);
    }

    public function test_no_model_with_an_answer_is_a_503(): void
    {
        Http::fake(['llm.test/*' => Http::response($this->answer(['content' => '']))]);
        $this->postJson('/api/ai/taunt', $this->tauntPayload())->assertStatus(503);
        Http::assertSentCount(2);
    }

    public function test_a_decision_is_the_tools_the_model_called(): void
    {
        Http::fake(['llm.test/*' => Http::response($this->answer(['content' => '', 'tool_calls' => [
            ['id' => 'a', 'type' => 'function', 'function' => ['name' => 'block_player', 'arguments' => '{"seconds": 40}']],
            ['id' => 'b', 'type' => 'function', 'function' => ['name' => 'sound_horn', 'arguments' => '{"style": "siren"}']],
            ['id' => 'c', 'type' => 'function', 'function' => ['name' => 'steer', 'arguments' => '{"angle": 1}']],
        ]]))]);
        // (the seconds are kept to 2–6, an unknown horn is the short one, an unknown tool is nothing)
        $this->postJson('/api/ai/decide', $this->decidePayload())->assertOk()
            ->assertExactJson(['block' => 6, 'horn' => 'short', 'model' => 'judge']);
        Http::assertSent(function (Request $request) {
            $body = $request->data();
            $names = array_map(fn ($t) => $t['function']['name'], $body['tools']);
            $situation = $body['messages'][1]['content'];

            return $names === ['block_player', 'sound_horn']
                && str_contains($situation, 'あなたが前') && str_contains($situation, '後方 6m') && str_contains($situation, '右側 1.4m')
                && str_contains($situation, '9km/h 速い') && str_contains($situation, '80m 先の左ヘアピン');
        });
    }

    public function test_a_model_may_carry_its_effort_and_is_asked_again_without_it_when_it_refuses(): void
    {
        config(['llm.decide_models' => ['quick', 'thinker@low', 'plain@low']]);
        $seen = [];
        Http::fake(function (Request $request) use (&$seen) {
            $body = $request->data();
            $seen[] = $body['model'].(isset($body['reasoning_effort']) ? '+'.$body['reasoning_effort'] : '');

            return match ($body['model']) {
                'quick' => Http::response(['error' => 'unknown model'], 400),
                // (refuses the parameter, then answers without it)
                'thinker' => isset($body['reasoning_effort']) ? Http::response(['error' => 'unknown parameter'], 400)
                    : Http::response($this->answer(['content' => '', 'tool_calls' => [
                        ['id' => 'a', 'type' => 'function', 'function' => ['name' => 'sound_horn', 'arguments' => '{"style": "double"}']],
                    ]])),
                default => Http::response(['error' => 'not asked'], 500),
            };
        });
        // (the answer names the model, not its effort; a model without one is never sent the parameter)
        $this->postJson('/api/ai/decide', $this->decidePayload())->assertOk()
            ->assertExactJson(['block' => null, 'horn' => 'double', 'model' => 'thinker']);
        $this->assertSame(['quick', 'thinker+low', 'thinker'], $seen);
    }

    public function test_llm_check_names_a_model_the_gateway_no_longer_offers(): void
    {
        config(['llm.decide_models' => ['judge', 'gone@low'], 'llm.taunt_models' => ['judge'], 'desk.models' => ['judge']]);
        Http::fake(['llm.test/v1/models' => Http::response(['data' => [['id' => 'judge'], ['id' => 'other']]])]);
        $this->artisan('llm:check')->expectsOutputToContain('NOT LISTED')->assertExitCode(1);
        config(['llm.decide_models' => ['judge@low']]);
        $this->artisan('llm:check')->doesntExpectOutputToContain('NOT LISTED')->assertExitCode(0);
    }

    public function test_a_rival_that_is_behind_has_the_horn_only(): void
    {
        Http::fake(['llm.test/*' => Http::response($this->answer(['content' => '', 'tool_calls' => [
            ['id' => 'a', 'type' => 'function', 'function' => ['name' => 'block_player', 'arguments' => '{"seconds": 4}']],
            ['id' => 'b', 'type' => 'function', 'function' => ['name' => 'sound_horn', 'arguments' => '{"style": "double"}']],
        ]]))]);
        $this->postJson('/api/ai/decide', $this->decidePayload(['rival_ahead' => false]))->assertOk()
            ->assertExactJson(['block' => null, 'horn' => 'double', 'model' => 'judge']);
        Http::assertSent(fn (Request $request) => array_map(fn ($t) => $t['function']['name'], $request->data()['tools']) === ['sound_horn']
            && str_contains($request->data()['messages'][1]['content'], 'プレイヤーが前'));
    }

    public function test_a_model_that_calls_nothing_decides_nothing(): void
    {
        Http::fake(['llm.test/*' => Http::response($this->answer(['content' => '何もしない']))]);
        $this->postJson('/api/ai/decide', $this->decidePayload(['rival_ahead' => false, 'lateral_m' => 0.2]))->assertOk()
            ->assertExactJson(['block' => null, 'horn' => null, 'model' => 'judge']);
    }

    public function test_only_facts_are_accepted(): void
    {
        Http::fake();
        $this->postJson('/api/ai/taunt', $this->tauntPayload(['course' => 'nowhere']))->assertStatus(422);
        $this->postJson('/api/ai/taunt', $this->tauntPayload(['player_car' => 'ufo']))->assertStatus(422);
        $this->postJson('/api/ai/taunt', $this->tauntPayload(['rival' => ['name' => str_repeat('あ', 25), 'title' => 'x']]))->assertStatus(422);
        $this->postJson('/api/ai/taunt', $this->tauntPayload(['rival' => ['description' => str_repeat('あ', 201)] + self::RIVAL]))->assertStatus(422);
        $this->postJson('/api/ai/decide', $this->decidePayload(['corner' => ['distance_m' => 10, 'kind' => 'loop']]))->assertStatus(422);
        $this->postJson('/api/ai/decide', $this->decidePayload(['gap_m' => -5]))->assertStatus(422);
        $this->postJson('/api/ai/decide', $this->decidePayload(['messages' => [['role' => 'user', 'content' => 'hi']], 'level' => 'boss']))->assertStatus(422);
        Http::assertNothingSent();
    }
}
