<?php

namespace Database\Seeders;

use App\Models\Player;
use App\Models\Run;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

/**
 * Seeds the leaderboard with the "house" rivals so a fresh install has times
 * (and ghosts) to chase. Records are produced by the AI driver running the
 * real vehicle simulation: see tools/gen-bot-ghosts.ts. A bot keeps one run per
 * course and car: regenerated records (new physics or road grip) replace the old.
 */
class BotRunSeeder extends Seeder
{
    public function run(): void
    {
        $path = database_path('seeders/data/bot_runs.json');
        if (! is_file($path)) {
            $this->command?->warn('No bot run data found; skipping.');

            return;
        }

        $records = json_decode(file_get_contents($path), true, flags: JSON_THROW_ON_ERROR);

        DB::transaction(function () use ($records) {
            foreach ($records as $rec) {
                $player = Player::where('name', $rec['player_name'])->where('is_bot', true)->first()
                    ?? Player::register($rec['player_name'], true)[0];

                $existing = Run::where('player_id', $player->id)
                    ->where('track_id', $rec['track_id'])
                    ->where('car_id', $rec['car_id'])
                    ->get();
                if ($existing->contains('time_ms', $rec['time_ms'])) {
                    continue;
                }
                foreach ($existing as $old) {
                    $old->ghost()->delete();
                    $old->delete();
                }

                $run = Run::create([
                    'player_id' => $player->id,
                    'track_id' => $rec['track_id'],
                    'car_id' => $rec['car_id'],
                    'mode' => 'time_attack',
                    'time_ms' => $rec['time_ms'],
                    'sector_ms' => $rec['sector_ms'],
                    'client_version' => 'seed',
                ]);

                if (! empty($rec['ghost'])) {
                    $run->ghost()->create($rec['ghost']);
                }
            }
        });
    }
}
