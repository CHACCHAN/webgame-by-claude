<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\DeskMind;
use App\Services\DeskReports;
use App\Services\MemberSession;
use Illuminate\Contracts\Cache\Lock;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Validation\Rule;

/**
 * The desk (総合窓口; config/desk.php): a chat with a language model about the game that can file a report for
 * the developer, and a plain report form that needs no model.
 *
 * Text is the rule, the model an extra: without a gateway, or when no model answers, the chat says 503 and the
 * form still works. What players write is untrusted everywhere: it is clamped, stripped of control characters,
 * handed to the model as its `user` messages only, and kept as data in a file nothing here reads back.
 * A report holds what the server knows itself (time, id, version, who by kind, the clamped facts), never what
 * the model claims about those.
 */
class DeskController extends Controller
{
    public function __construct(private DeskReports $reports, private MemberSession $sessions) {}

    public function chat(Request $request, DeskMind $mind): JsonResponse
    {
        if (! config('desk.enabled')) {
            return $this->closed();
        }
        $in = $request->validate([
            'messages' => ['required', 'array', 'min:1', 'max:'.config('desk.max_messages')],
            'messages.*' => ['required', 'array:role,content'],
            'messages.*.role' => ['required', Rule::in(['user', 'assistant'])],
            'messages.*.content' => ['required', 'string', 'max:'.config('desk.message_chars')],
            'facts' => ['nullable', 'array'],
        ]);
        $messages = [];
        $total = 0;
        foreach ($in['messages'] as $m) {
            $content = DeskReports::clean($m['content'], (int) config('desk.message_chars'), true);
            if ($content === '') {
                return $this->invalid('空のメッセージは送れません。');
            }
            $total += mb_strlen($content);
            $messages[] = ['role' => $m['role'], 'content' => $content];
        }
        if ($total > (int) config('desk.total_chars')) {
            return $this->invalid('会話が長すぎます。新しい会話を始めてください。');
        }
        if (end($messages)['role'] !== 'user') {
            return $this->invalid('最後のメッセージはプレイヤーのものでなければなりません。');
        }
        if (! $mind->available()) {
            return $this->nobody();
        }

        $facts = $this->facts($request);
        $slot = $this->slot();
        if ($slot === null) {
            return response()->json(['message' => '窓口が混み合っています。少し待ってからもう一度お試しください。'], 429);
        }
        try {
            $answer = $mind->answer($messages, $facts);
        } finally {
            $slot->release();
        }
        if ($answer === null) {
            return $this->nobody();
        }

        $reply = DeskReports::clean($answer['text'], (int) config('desk.reply_chars'), true);
        $out = [];
        if ($answer['report'] !== null) {
            $said = array_column(array_filter($messages, fn ($m) => $m['role'] === 'user'), 'content');
            $filed = $this->keep($request, $facts, [
                'via' => 'ai',
                'kind' => $answer['report']['kind'] ?? null,
                'severity' => $answer['report']['severity'] ?? null,
                'title' => $answer['report']['title'] ?? null,
                'body' => $answer['report']['body'] ?? null,
                'model' => $answer['model'],
                'said' => $this->said($said),
            ]);
            if (is_array($filed)) {
                $out['filed'] = $filed;
                $reply = $reply !== '' ? $reply : ['bug' => '不具合の報告', 'request' => 'ご要望', 'other' => 'ご連絡'][$filed['kind']].'を受け付けました。開発者に伝えます。';
            } else {
                // (whatever the model wrote about having taken it down is not true: the server's own words)
                $reply = $filed === 'limit'
                    ? '報告の受け付けが続いたため、いまは記録できませんでした。しばらく時間をおいてからもう一度お送りください。'
                    : '報告を記録できませんでした。お手数ですが「フォームで送る」からお送りください。';
            }
        }
        if ($reply === '') {
            return $this->nobody();
        }

        return response()->json(['reply' => $reply] + $out);
    }

    public function report(Request $request): JsonResponse
    {
        if (! config('desk.enabled')) {
            return $this->closed();
        }
        $in = $request->validate([
            'kind' => ['required', Rule::in(DeskReports::KINDS)],
            'text' => ['required', 'string', 'max:'.config('desk.body_chars')],
            'facts' => ['nullable', 'array'],
        ]);
        $text = DeskReports::clean($in['text'], (int) config('desk.body_chars'), true);
        if (mb_strlen($text) < 4) {
            return $this->invalid('内容を入力してください。');
        }
        $filed = $this->keep($request, $this->facts($request), [
            'via' => 'form',
            'kind' => $in['kind'],
            'severity' => null,
            // (a form has no title: its first line stands for one in the list)
            'title' => strtok($text, "\n") ?: '',
            'body' => $text,
        ]);
        if ($filed === 'limit') {
            return response()->json(['message' => '短い時間に多くの報告が送られました。しばらく時間をおいてからお試しください。'], 429);
        }
        if (! is_array($filed)) {
            return response()->json(['message' => '報告を保存できませんでした。時間をおいてもう一度お試しください。'], 503);
        }

        return response()->json(['filed' => $filed], 201);
    }

    /**
     * Clamps a report and appends it to the file: `['id', 'kind']`, or `'limit'` (this address has filed its
     * share for the hour), or `'failed'` (it could not be written).
     */
    private function keep(Request $request, array $facts, array $report): array|string
    {
        $key = 'desk-report:'.$request->ip();
        if (RateLimiter::tooManyAttempts($key, (int) config('desk.reports_per_hour'))) {
            return 'limit';
        }
        $kind = in_array($report['kind'], DeskReports::KINDS, true) ? $report['kind'] : 'other';
        $member = $this->sessions->member($request);
        $id = $this->reports->file([
            'via' => $report['via'],
            'kind' => $kind,
            'severity' => in_array($report['severity'], DeskReports::SEVERITIES, true) ? $report['severity'] : null,
            'title' => DeskReports::clean($report['title'], (int) config('desk.title_chars')) ?: '（無題）',
            'body' => DeskReports::clean($report['body'], (int) config('desk.body_chars'), true),
            'version' => (string) config('game.version'),
            // (a member by the id of their records only: no name, no mail; a guest is nobody in particular)
            'who' => $member ? ['type' => 'member', 'player_id' => $member->id] : ['type' => 'guest'],
            'facts' => $facts,
        ] + array_intersect_key($report, ['model' => 1, 'said' => 1]));
        if ($id === null) {
            return 'failed';
        }
        RateLimiter::hit($key, 3600);

        return ['id' => $id, 'kind' => $kind];
    }

    /**
     * One of the few places at the model (`desk.concurrent`), or null when all are taken. A place that is never
     * given back (a worker that was ended) frees itself after 40 s.
     */
    private function slot(): ?Lock
    {
        for ($i = 0; $i < (int) config('desk.concurrent'); $i++) {
            $lock = Cache::lock('desk-slot:'.$i, 40);
            if ($lock->get()) {
                return $lock;
            }
        }

        return null;
    }

    /** The player's own last messages, verbatim (cleaned), newest kept when they are too many or too long. */
    private function said(array $texts): array
    {
        $out = [];
        $room = (int) config('desk.said_chars');
        foreach (array_reverse(array_slice($texts, -(int) config('desk.said_messages'))) as $text) {
            $text = mb_substr($text, 0, $room);
            if ($text === '') {
                break;
            }
            $room -= mb_strlen($text);
            array_unshift($out, $text);
        }

        return $out;
    }

    /**
     * What the client says about itself, kept only where it is one of a known set or a whole number in a range;
     * anything else is dropped. The browser's family is read from the request itself.
     */
    private function facts(Request $request): array
    {
        $in = $request->input('facts');
        $in = is_array($in) ? $in : [];
        $enum = fn (string $key, array $set) => is_string($in[$key] ?? null) && in_array($in[$key], $set, true) ? $in[$key] : null;
        $int = fn (string $key, int $lo, int $hi) => is_int($in[$key] ?? null) && $in[$key] >= $lo && $in[$key] <= $hi ? $in[$key] : null;
        $bool = fn (string $key) => is_bool($in[$key] ?? null) ? $in[$key] : null;
        $match = fn (string $key, string $pattern) => is_string($in[$key] ?? null) && preg_match($pattern, $in[$key]) ? $in[$key] : null;

        return array_filter([
            'client' => $match('version', '/^\d{1,3}\.\d{1,3}\.\d{1,4}$/'),
            'course' => $enum('course', array_keys(config('game.tracks'))),
            'vehicle' => $enum('vehicle', array_keys(config('game.cars'))),
            'tod' => $enum('tod', config('game.times_of_day')),
            'mode' => $enum('mode', ['time_attack', 'rival', 'ghost', 'online']),
            'quality' => $enum('quality', ['low', 'medium', 'high', 'ultra']),
            'backend' => $enum('backend', ['webgpu', 'webgl2']),
            'software' => $bool('software'),
            'upscale' => $bool('upscale'),
            'upscale_mode' => $enum('upscale_mode', ['native', 'ultra', 'quality', 'balanced', 'performance']),
            'scale' => $int('scale', 10, 100),
            'w' => $int('w', 1, 20000),
            'h' => $int('h', 1, 20000),
            'dpr' => $int('dpr', 25, 800),
            'touch' => $bool('touch'),
            'pad' => $bool('pad'),
            // the graphics adapter as the browser names it: letters, digits and the few marks such names use
            'gpu' => $match('gpu', '/^[A-Za-z0-9 ()\[\]\/.,:_+\-]{1,96}$/'),
            'lang' => $match('lang', '/^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,2}$/'),
            'ua' => $this->browser((string) $request->userAgent()),
        ], fn ($v) => $v !== null);
    }

    /** "Chrome 142 / Windows": the family, never the whole user agent string. */
    private function browser(string $ua): ?string
    {
        if ($ua === '') {
            return null;
        }
        $family = 'other';
        foreach (['Edge' => '/Edg(?:e|A|iOS)?\/(\d+)/', 'Opera' => '/OPR\/(\d+)/', 'Firefox' => '/(?:Firefox|FxiOS)\/(\d+)/', 'Chrome' => '/(?:Chrome|CriOS)\/(\d+)/', 'Safari' => '/Version\/(\d+)[\d.]* (?:Mobile\/\S+ )?Safari/'] as $name => $pattern) {
            if (preg_match($pattern, $ua, $m)) {
                $family = $name.' '.min(9999, (int) $m[1]);
                break;
            }
        }
        $os = 'other';
        foreach (['Android' => '/Android/', 'iOS' => '/iPhone|iPad|iPod/', 'Windows' => '/Windows/', 'ChromeOS' => '/CrOS/', 'macOS' => '/Mac OS X|Macintosh/', 'Linux' => '/Linux|X11/'] as $name => $pattern) {
            if (preg_match($pattern, $ua)) {
                $os = $name;
                break;
            }
        }

        return $family.' / '.$os;
    }

    private function invalid(string $message): JsonResponse
    {
        return response()->json(['message' => $message], 422);
    }

    private function nobody(): JsonResponse
    {
        return response()->json(['message' => 'AI窓口はいま応答できません。フォームから報告・要望を送れます。'], 503);
    }

    private function closed(): JsonResponse
    {
        return response()->json(['message' => '窓口は現在受け付けていません。'], 404);
    }
}
