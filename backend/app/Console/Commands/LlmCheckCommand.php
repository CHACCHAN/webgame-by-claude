<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * Whether the models the rivals and the desk are set to ask are still offered by the gateway:
 *   php artisan llm:check
 * One line per list entry: listed or not by the gateway's `/models`. Exit code 1 when one is missing. The gateway
 * renames and drops models without notice (11-19: every rival model answered 400 and the rivals ran on the game's
 * own lines). Prints model names only, never the gateway's address or key.
 */
class LlmCheckCommand extends Command
{
    protected $signature = 'llm:check';

    protected $description = 'Checks the configured rival and desk models against the gateway\'s model list';

    public function handle(): int
    {
        $url = (string) config('llm.url');
        if ($url === '' || (string) config('llm.key') === '') {
            $this->line('no gateway configured (LLM_API_URL / LLM_API_KEY): nobody is asked, the game uses its own lines');

            return self::SUCCESS;
        }
        try {
            $response = Http::withHeaders([(string) config('llm.key_header') => (string) config('llm.key')])
                ->connectTimeout(3)->timeout(15)->acceptJson()
                ->get(preg_replace('#/chat/completions$#', '', $url).'/models');
        } catch (Throwable $e) {
            $this->error('the gateway did not answer ('.class_basename($e).')');

            return self::FAILURE;
        }
        if (! $response->successful()) {
            $this->error('the gateway answered '.$response->status().' to /models');

            return self::FAILURE;
        }
        $offered = array_map(fn ($m) => (string) ($m['id'] ?? ''), (array) $response->json('data'));
        $missing = 0;
        foreach (['rival lines' => 'llm.taunt_models', 'rival decisions' => 'llm.decide_models', 'desk' => 'desk.models'] as $what => $key) {
            foreach ((array) config($key) as $spec) {
                $name = explode('@', (string) $spec, 2)[0];
                $ok = in_array($name, $offered, true);
                $missing += $ok ? 0 : 1;
                $this->line(sprintf('%-16s %-32s %s', $what, $spec, $ok ? 'listed' : 'NOT LISTED'));
            }
        }

        return $missing === 0 ? self::SUCCESS : self::FAILURE;
    }
}
