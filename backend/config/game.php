<?php

/*
| Game content metadata shared with the frontend. The authoritative lists of
| tracks and cars live here so that submitted runs can be validated.
*/

/*
| Content that is in the code but not yet open to players (the frontend's switch of the same name:
| frontend/src/game/release.ts; a vitest compares the two). An entry with 'release' => '<name>' is left out of
| `tracks` / `cars` until its name is true here, so nothing can be listed, raced or recorded on it before; the whole
| catalogue stays readable as `catalog` (tests).
*/
$release = [
    'edwards' => false,
];
$open = fn (array $list): array => array_filter($list, fn (array $e): bool => ! isset($e['release']) || $release[$e['release']]);

$tracks = [
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
        // 11.9 km from the ramp to the lakebed runway: nothing on wheels here passes Mach 1.2 (the Su-47 at its top),
        // and at Mach 1 all the way the distance alone takes 35 s: the floor is 85 % of that
        'edwards' => [
            'name' => 'エドワーズ空軍基地',
            'name_en' => 'Edwards AFB',
            'sectors' => 4,
            'min_time_ms' => 30_000,
            'max_time_ms' => 30 * 60_000,
            'release' => 'edwards',
        ],
];

// ids are stable (stored runs and ghosts refer to them); names follow the car models in use
$cars = [
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
        // fighters, driven on the ground (frontend vehicle/jets.ts): 'tracks' = the only courses they may be used on
        // (App\Support\Vehicles::allowedOn: rooms and runs are refused elsewhere)
        'f15j' => ['name' => 'F-15J イーグル', 'tracks' => ['edwards'], 'release' => 'edwards'],
        'f15c' => ['name' => 'F-15C イーグル', 'tracks' => ['edwards'], 'release' => 'edwards'],
        'su47' => ['name' => 'Su-47 ベールクト', 'tracks' => ['edwards'], 'release' => 'edwards'],
];

return [
    'version' => env('GAME_VERSION', '2.2.1'),

    'release' => $release,
    'catalog' => ['tracks' => $tracks, 'cars' => $cars],
    'tracks' => $open($tracks),

    // race conditions a room can be created with (the client's TimeOfDay)
    'times_of_day' => ['night', 'rain', 'dawn'],

    'cars' => $open($cars),

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
