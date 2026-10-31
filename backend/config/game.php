<?php

/*
| Game content metadata shared with the frontend. The authoritative lists of
| tracks and cars live here so that submitted runs can be validated.
*/

return [
    'version' => env('GAME_VERSION', '1.0.0'),

    'tracks' => [
        // min_time_ms: anything faster is physically impossible on the course
        'oboro-downhill' => [
            'name' => '朧峠 ダウンヒル',
            'name_en' => 'Oboro Pass Downhill',
            'sectors' => 4,
            'min_time_ms' => 60_000,
            'max_time_ms' => 30 * 60_000,
        ],
        'kirifuri-lakeside' => [
            'name' => '霧降湖 レイクサイド',
            'name_en' => 'Kirifuri Lakeside',
            'sectors' => 4,
            'min_time_ms' => 50_000,
            'max_time_ms' => 30 * 60_000,
        ],
        'tenrou-skyline' => [
            'name' => '天狼スカイライン',
            'name_en' => 'Tenrou Skyline',
            'sectors' => 4,
            'min_time_ms' => 45_000,
            'max_time_ms' => 30 * 60_000,
        ],
    ],

    'cars' => [
        'hayate' => ['name' => 'HAYATE TR-S'],
        'raijin' => ['name' => 'RAIJIN GT-X'],
        'shiden' => ['name' => 'SHIDEN RS'],
    ],

    'modes' => ['time_attack', 'rival', 'ghost'],

    // Online battle rooms
    'online' => [
        'max_players' => 3,
        'min_players_to_start' => 2,
        // the green light is this far after the host presses start (countdown on every client)
        'start_delay_ms' => 6_000,
        // rooms idle longer than this are removed when new rooms are created
        'room_ttl_minutes' => 120,
    ],

    // Ghost recordings: max decoded payload size (bytes) and sampling bounds.
    'ghost' => [
        'max_base64_length' => 2_000_000,
        'min_interval_ms' => 16,
        'max_interval_ms' => 200,
    ],
];
