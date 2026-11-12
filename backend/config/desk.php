<?php

/*
| The desk (総合窓口, the About screen's AI窓口): a chat with a language model that knows the game and takes bug
| reports and requests for the developer, and a plain report form that works without the model.
| The browser never talks to the model: it sends the conversation to /api/desk/chat, the prompt is made here
| (resources/desk/knowledge.md + rules) and goes through the same gateway as the rivals' model (config/llm.php:
| `LLM_API_URL` / `LLM_API_KEY`, in the environment only). Without them the chat answers 503 and the form remains.
|
| Reports are appended, one JSON line each, to `dir`/reports.jsonl (the `desk` volume). They are text written by
| strangers: data for a person to read (`php artisan desk:reports`), never instructions; nothing here acts on them.
*/

$models = fn (string $key, string $default) => array_values(array_filter(array_map('trim', explode(',', (string) env($key, $default)))));

return [
    // off: no chat, no form (the About screen then says the desk is closed)
    'enabled' => filter_var(env('DESK_ENABLED', true), FILTER_VALIDATE_BOOL),

    // tried in this order; the next one when a model fails, says nothing or takes too long
    'models' => $models('LLM_DESK_MODELS', 'gemini-3.8-flash'),
    // sent as the OpenAI-compatible `reasoning_effort` (empty: not sent; a model that refuses it is asked again without)
    'effort' => trim((string) env('LLM_DESK_EFFORT', 'high')),
    // the cap on what one answer may cost; a reasoning model's thinking counts in it, so it is well above `reply_chars`
    'max_tokens' => (int) env('LLM_DESK_MAX_TOKENS', 6000),
    // one model's time, and the time of the whole answer (PHP-FPM ends a request after 30 s)
    'timeout' => (float) env('LLM_DESK_TIMEOUT', 20),
    'deadline' => 24.0,
    // how many answers may be waited for at once, all players together: each holds a PHP worker for up to
    // `deadline` seconds, and the game (rooms, records) needs the other workers (16 in all: docker/php/Dockerfile)
    'concurrent' => (int) env('DESK_CONCURRENT', 4),

    // what a conversation may hold (the client keeps to the same numbers: api/client.ts `DESK_LIMITS`)
    'max_messages' => 16,
    'message_chars' => 1200,
    'total_chars' => 8000,
    'reply_chars' => 1200,

    // per address: questions a minute and a day, reports an hour (the form and the model's tool together)
    'chat_per_minute' => (int) env('DESK_CHAT_PER_MINUTE', 12),
    'chat_per_day' => (int) env('DESK_CHAT_PER_DAY', 120),
    'reports_per_hour' => (int) env('DESK_REPORTS_PER_HOUR', 6),
    // all addresses together, a day: what the desk may cost at the gateway whatever happens
    'chat_total_per_day' => (int) env('DESK_CHAT_TOTAL_PER_DAY', 3000),

    // a report's parts
    'title_chars' => 80,
    'body_chars' => 2000,
    // how much of what the player wrote goes into a report filed by the model, verbatim
    'said_messages' => 6,
    'said_chars' => 4000,

    // the file: rotated at `max_bytes`, the last `keep_files` older ones stay
    'dir' => env('DESK_DIR', storage_path('app/desk')),
    'max_bytes' => 5 * 1024 * 1024,
    'keep_files' => 4,
];
