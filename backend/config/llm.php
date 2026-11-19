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

    // tried in this order; the next one when a model fails or takes too long. `name@effort` sends that
    // `reasoning_effort` with the request (a model that refuses it is asked again without). Owner, 11-19: the rival
    // runs on sarashina, then deepseek-v4.1-flash at low effort (the gateway had renamed sarashina-3-mini to
    // sarashina3-mini and dropped gemini-3.5-flash-lite: both answered 400). Measured 11-19 through the gateway:
    // sarashina3-mini 0.3–0.5 s, deepseek-v4.1-flash@low 0.9–1.3 s for a line, 0.9–1.7 s for a decision with tool calls.
    'taunt_models' => $models('LLM_TAUNT_MODELS', 'sarashina3-mini,deepseek-v4.1-flash@low'),
    'decide_models' => $models('LLM_DECIDE_MODELS', 'sarashina3-mini,deepseek-v4.1-flash@low'),
    'taunt_timeout' => (float) env('LLM_TAUNT_TIMEOUT', 6),
    // a decision that comes later than this is about a situation that is gone
    'decide_timeout' => (float) env('LLM_DECIDE_TIMEOUT', 2.5),

    'taunt_max_chars' => 48,
];
