<?php

/*
| The rivals' voice and judgement (taunts before a race, whether to block or sound the horn in one).
| The browser never talks to the model: it sends the situation as numbers and names to /api/ai/*, the prompt is
| made here and goes through the gateway (Gravitee → LiteLLM, OpenAI-compatible) with the key from the environment.
| Without a key or an address the endpoints answer 503 and the game uses its own lines and rules.
*/

$models = fn (string $key, string $default) => array_values(array_filter(array_map('trim', explode(',', (string) env($key, $default)))));

return [
    'key' => env('LLM_API_KEY'),
    // the gateway's address comes from the environment only (`LLM_API_URL` in `.env`: the OpenAI-compatible base,
    // …/v1, or the chat completions endpoint itself); without it, as without a key, nobody is asked
    'url' => (function (): string {
        $url = rtrim(trim((string) env('LLM_API_URL', '')), '/');

        return $url === '' || str_ends_with($url, '/chat/completions') ? $url : $url.'/chat/completions';
    })(),
    'key_header' => env('LLM_KEY_HEADER', 'X-Gravitee-Api-Key'),

    // tried in this order; the next one when a model fails or takes too long (measured 2026-11-11: taunts
    // 2.0 s / 0.3 s, decisions with tool calls 0.15–0.5 s)
    'taunt_models' => $models('LLM_TAUNT_MODELS', 'gemini-3.5-flash-lite,sarashina-3-mini'),
    'decide_models' => $models('LLM_DECIDE_MODELS', 'sarashina-3-mini,gemini-3.5-flash-lite'),
    'taunt_timeout' => (float) env('LLM_TAUNT_TIMEOUT', 6),
    // a decision that comes later than this is about a situation that is gone
    'decide_timeout' => (float) env('LLM_DECIDE_TIMEOUT', 2.5),

    'taunt_max_chars' => 48,
];
