<?php

namespace App\Services;

use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Where the desk's reports are kept: one JSON line each, appended to `reports.jsonl` in `config('desk.dir')`
 * (the `desk` volume). The file is only ever appended to; a report that was dealt with is named in a second file
 * (`done.jsonl`). At `desk.max_bytes` the file is set aside under a dated name and a new one begun; the last
 * `desk.keep_files` older ones stay.
 *
 * What is in a report was written by strangers (or by a language model from what they wrote): it is data for a
 * person to read, never instructions. Nothing in the application reads a report back but `desk:reports`, which
 * only prints it.
 */
class DeskReports
{
    public const KINDS = ['bug', 'request', 'other'];

    public const SEVERITIES = ['low', 'medium', 'high'];

    private const FILE = 'reports.jsonl';

    private const DONE = 'done.jsonl';

    /** no I, L, O, U: an id read aloud or typed again stays what it was */
    private const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

    /**
     * Appends a report and returns its id, or null when it could not be written (the caller says so: a report
     * that was not kept must not be acknowledged). `$report` is what the caller knows; id and time are set here.
     */
    public function file(array $report): ?string
    {
        $id = $this->newId();
        $line = json_encode(['id' => $id, 'at' => now()->utc()->format('Y-m-d\TH:i:s\Z')] + $report, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
        if ($line === false) {
            return null;
        }
        try {
            $dir = $this->dir();
            if (! is_dir($dir) && ! @mkdir($dir, 0770, true) && ! is_dir($dir)) {
                throw new \RuntimeException('no directory');
            }
            $lock = fopen($dir.'/.lock', 'c');
            if ($lock === false || ! flock($lock, LOCK_EX)) {
                throw new \RuntimeException('no lock');
            }
            try {
                $path = $dir.'/'.self::FILE;
                clearstatcache(true, $path);
                if (is_file($path) && filesize($path) + strlen($line) + 1 > (int) config('desk.max_bytes')) {
                    $this->rotate($dir, $path);
                }
                if (file_put_contents($path, $line."\n", FILE_APPEND) !== strlen($line) + 1) {
                    throw new \RuntimeException('not written');
                }
            } finally {
                flock($lock, LOCK_UN);
                fclose($lock);
            }
        } catch (Throwable $e) {
            // (the reason only: never a report's text in the log)
            Log::warning('desk: a report was not kept: '.$e->getMessage());

            return null;
        }

        return $id;
    }

    /**
     * Every report still on file, oldest first, each with `done` (null, or when and with what note it was marked).
     *
     * @return list<array<string, mixed>>
     */
    public function all(): array
    {
        $done = $this->doneMarks();
        $out = [];
        foreach ($this->files() as $path) {
            foreach ($this->lines($path) as $report) {
                if (is_string($report['id'] ?? null)) {
                    $out[] = $report + ['done' => $done[$report['id']] ?? null];
                }
            }
        }

        return $out;
    }

    /** Marks a report as dealt with; false when there is no report of that id on file. */
    public function markDone(string $id, string $note = ''): bool
    {
        $id = strtoupper(trim($id));
        if (! in_array($id, array_column($this->all(), 'id'), true)) {
            return false;
        }
        $path = $this->dir().'/'.self::DONE;
        $line = json_encode(['id' => $id, 'at' => now()->utc()->format('Y-m-d\TH:i:s\Z'), 'note' => self::clean($note, 400)], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        file_put_contents($path, $line."\n", FILE_APPEND | LOCK_EX);
        // (the command runs as root inside the container, the application does not: the file stays the directory's)
        @chown($path, (int) fileowner($this->dir()));

        return true;
    }

    public function dir(): string
    {
        return rtrim((string) config('desk.dir'), '/');
    }

    /**
     * Text from outside made fit to be kept and printed: no control characters (a report must not be able to move
     * a terminal's cursor, clear the screen or hide text with direction marks), and not longer than `$max`.
     * With `$lines` the line breaks stay (at most two in a row); without, it is one line.
     */
    public static function clean(mixed $text, int $max, bool $lines = false): string
    {
        $text = is_string($text) ? $text : '';
        // (text that is not UTF-8 would stop every pattern below: its bad bytes are replaced first)
        $text = mb_scrub($text, 'UTF-8');
        $text = str_replace(["\r\n", "\r", "\u{2028}", "\u{2029}"], "\n", $text);
        if (! $lines) {
            $text = str_replace("\n", ' ', $text);
        }
        // every control and format character but the line feed: escape sequences, bidi overrides, zero-width marks
        $text = (string) preg_replace('/[^\P{C}\n]+/u', ' ', $text);
        $text = (string) preg_replace('/[ \t\x{3000}]{2,}/u', ' ', $text);
        $text = (string) preg_replace('/ ?\n ?/u', "\n", $text);
        $text = (string) preg_replace('/\n{3,}/u', "\n\n", $text);

        return trim(mb_substr(trim($text), 0, $max));
    }

    private function newId(): string
    {
        $id = '';
        for ($i = 0; $i < 6; $i++) {
            $id .= self::ALPHABET[random_int(0, 31)];
        }

        return $id;
    }

    /** The full file gets a dated name; of the dated ones only the newest `keep_files` stay. */
    private function rotate(string $dir, string $path): void
    {
        $name = $dir.'/reports-'.now()->utc()->format('Ymd-His');
        for ($n = 0; file_exists($name.($n ? "-$n" : '').'.jsonl'); $n++);
        rename($path, $name.($n ? "-$n" : '').'.jsonl');
        $old = glob($dir.'/reports-*.jsonl') ?: [];
        sort($old);
        foreach (array_slice($old, 0, max(0, count($old) - (int) config('desk.keep_files'))) as $gone) {
            @unlink($gone);
        }
    }

    /** the dated files in order of their names (= of time), then the one being written */
    private function files(): array
    {
        $old = glob($this->dir().'/reports-*.jsonl') ?: [];
        sort($old);
        $now = $this->dir().'/'.self::FILE;

        return is_file($now) ? [...$old, $now] : $old;
    }

    private function lines(string $path): array
    {
        $out = [];
        foreach (@file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
            $row = json_decode($line, true);
            if (is_array($row)) {
                $out[] = $row;
            }
        }

        return $out;
    }

    /** @return array<string, array{at: string, note: string}> */
    private function doneMarks(): array
    {
        $out = [];
        foreach ($this->lines($this->dir().'/'.self::DONE) as $row) {
            if (is_string($row['id'] ?? null)) {
                $out[$row['id']] = ['at' => (string) ($row['at'] ?? ''), 'note' => (string) ($row['note'] ?? '')];
            }
        }

        return $out;
    }
}
