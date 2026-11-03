<?php

/*
| Game content metadata shared with the frontend. The authoritative lists of
| tracks and cars live here so that submitted runs can be validated.
*/

return [
    'version' => env('GAME_VERSION', '1.0.0'),

    'tracks' => [
        // min_time_ms: anything faster is physically impossible on the course (with the cockroach, the fastest
        // vehicle: its AI lap is ~1.4× these and a player can go faster on the straights)
        'oboro-downhill' => [
            'name' => '朧峠 ダウンヒル',
            'name_en' => 'Oboro Pass Downhill',
            'sectors' => 4,
            'min_time_ms' => 50_000,
            'max_time_ms' => 30 * 60_000,
        ],
        'kirifuri-lakeside' => [
            'name' => '霧降湖 レイクサイド',
            'name_en' => 'Kirifuri Lakeside',
            'sectors' => 4,
            'min_time_ms' => 42_000,
            'max_time_ms' => 30 * 60_000,
        ],
        'tenrou-skyline' => [
            'name' => '天狼スカイライン',
            'name_en' => 'Tenrou Skyline',
            'sectors' => 4,
            'min_time_ms' => 38_000,
            'max_time_ms' => 30 * 60_000,
        ],
    ],

    // ids are stable (stored runs and ghosts refer to them); names follow the car models in use
    // race conditions a room can be created with (the client's TimeOfDay)
    'times_of_day' => ['night', 'rain', 'dawn'],

    'cars' => [
        'hayate' => ['name' => 'SPRINTER TRUENO AE86'],
        's15' => ['name' => 'SILVIA spec-R (S15)'],
        'shiden' => ['name' => 'RX-7 (FD3S)'],
        'supra' => ['name' => 'SUPRA RZ (JZA80)'],
        'raijin' => ['name' => 'IMPREZA WRX STI'],
        'r34' => ['name' => 'SKYLINE GT-R (BNR34)'],
        // joke entries: three-car trains (frontend vehicle/trains.ts)
        'e231' => ['name' => 'E231系'],
        'jr117' => ['name' => '117系'],
        'keisei3300' => ['name' => '京成3300形'],
        'ginza1000' => ['name' => '東京メトロ1000系'],
        'n700' => ['name' => '新幹線N700系'],
        // joke entry: the giant cockroach (frontend vehicle/roach.ts), the fastest vehicle
        'roach' => ['name' => 'ゴキブリ'],
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
