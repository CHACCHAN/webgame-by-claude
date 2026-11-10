<?php

/*
| Game content metadata shared with the frontend. The authoritative lists of
| tracks and cars live here so that submitted runs can be validated.
*/

return [
    'version' => env('GAME_VERSION', '1.0.0'),

    'tracks' => [
        // min_time_ms: anything faster is physically impossible on the course. With the cockroach, the fastest vehicle
        // (twice the grip since 2026-11-10, Mach 1 at the top), a lap on the racing line at its full limits (downforce
        // grip included, no speed cap; frontend tools/sim-run.ts and the course's racing line) takes 37.5 / 30.5 / 27.6 s
        // on the passes and 27.5 s on the autobahn: the floors are ~85 % of those
        'oboro-downhill' => [
            'name' => '朧峠 ダウンヒル',
            'name_en' => 'Oboro Pass Downhill',
            'sectors' => 4,
            'min_time_ms' => 32_000,
            'max_time_ms' => 30 * 60_000,
        ],
        'kirifuri-lakeside' => [
            'name' => '霧降湖 レイクサイド',
            'name_en' => 'Kirifuri Lakeside',
            'sectors' => 4,
            'min_time_ms' => 26_000,
            'max_time_ms' => 30 * 60_000,
        ],
        'tenrou-skyline' => [
            'name' => '天狼スカイライン',
            'name_en' => 'Tenrou Skyline',
            'sectors' => 4,
            'min_time_ms' => 23_500,
            'max_time_ms' => 30 * 60_000,
        ],
        // 8.6 km of motorway from a standing start: the U9 Xtreme's AI ~64 s (503 km/h), the cockroach's AI 35.5 s; the
        // cockroach at its limits (Mach 1 for ~5 km) 27.5 s
        'autobahn' => [
            'name' => 'アウトバーン',
            'name_en' => 'Autobahn',
            'sectors' => 4,
            'min_time_ms' => 23_000,
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
        // electric: the Cybertruck (Cyberbeast) and the fastest production EV (frontend vehicle/carSpecs.ts)
        'cybertruck' => ['name' => 'CYBERTRUCK'],
        'u9' => ['name' => 'YANGWANG U9 Xtreme'],
        // motorcycles (frontend vehicle/bikes.ts)
        'nsr250r' => ['name' => 'NSR250R'],
        'ninjah2' => ['name' => 'Ninja H2'],
        'hayabusa' => ['name' => 'GSX1300R 隼'],
        // joke entries: three-car trains (frontend vehicle/trains.ts)
        'e231' => ['name' => 'E231系'],
        'e235' => ['name' => 'E235系'],
        'keikyu1000' => ['name' => '京急新1000形'],
        'tobu30000' => ['name' => '東武30000系'],
        'e5' => ['name' => '新幹線E5系'],
        'l0' => ['name' => 'L0系'],
        // joke entry: the giant cockroach (frontend vehicle/roach.ts), the quickest on the mountain passes
        'roach' => ['name' => 'ゴキブリ'],
    ],

    'modes' => ['time_attack', 'rival', 'ghost'],

    // Online battle rooms
    'online' => [
        'max_players' => 5,
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
