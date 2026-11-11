<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * What a rival says and decides, asked of a language model through the gateway. The model never drives: for a
 * race it may only call the two tools below (take the blocking line for some seconds, sound the horn) or do
 * nothing; the game's own driver carries them out.
 */
class RivalMind
{
    private const TOD = ['night' => '深夜・晴れ', 'rain' => '深夜・雨', 'dawn' => '夜明け'];

    private const MEDAL = ['none' => 'なし', 'bronze' => '銅', 'silver' => '銀', 'gold' => '金'];

    private const CORNER = [
        'straight' => '直線', 'left' => '左コーナー', 'right' => '右コーナー', 'left_fast' => '左高速コーナー',
        'right_fast' => '右高速コーナー', 'left_hairpin' => '左ヘアピン', 'right_hairpin' => '右ヘアピン',
    ];

    public const CORNERS = ['straight', 'left', 'right', 'left_fast', 'right_fast', 'left_hairpin', 'right_hairpin'];

    public const HORNS = ['short', 'long', 'double'];

    public function available(): bool
    {
        return (string) config('llm.key') !== '' && (string) config('llm.url') !== '';
    }

    /** One line in the rival's voice, or null (no key, every model failed). `$in` is validated by the controller. */
    public function taunt(array $in): ?array
    {
        $max = (int) config('llm.taunt_max_chars');
        $system = $this->persona($in['rival'])
            ."この人物として話す。日本語で1文、{$max}文字以内。かぎ括弧・絵文字・説明・名乗りは付けない。差別的な言葉や下品な言葉は使わない。";
        $facts = 'コース='.$in['course_name'].'（'.self::TOD[$in['tod']].'）。相手の車='.$in['player_car_name'].'。あなたの車='.$in['rival_car_name'].'。'
            .'これまでの対戦: 相手の'.$in['wins'].'勝'.$in['losses'].'敗。相手のこのコースのメダル: '.self::MEDAL[$in['medal']].'。';
        $ask = match ($in['moment']) {
            // (no gap given: nothing is said about it, a model told "0 s" spoke of a dead heat)
            'won' => 'レースが終わり、あなたが'.(isset($in['gap_s']) ? $this->seconds($in['gap_s']).'差で' : '').'勝った。相手に一言。',
            'lost' => 'レースが終わり、あなたは'.(isset($in['gap_s']) ? $this->seconds($in['gap_s']).'差で' : '').'負けた。相手に一言。',
            default => 'これからレースが始まる。相手を挑発する一言を。',
        };

        foreach (config('llm.taunt_models') as $model) {
            $message = $this->chat($model, (float) config('llm.taunt_timeout'), [
                'max_tokens' => 120,
                'temperature' => 0.9,
                'messages' => [['role' => 'system', 'content' => $system], ['role' => 'user', 'content' => '状況: '.$facts.$ask]],
            ]);
            $line = $this->line((string) ($message['content'] ?? ''), $max);
            if ($line !== '') {
                return ['line' => $line, 'model' => $model];
            }
        }

        return null;
    }

    /** What the rival does about the situation: `block` (seconds) and / or `horn` (style), both null = nothing. */
    public function decide(array $in): ?array
    {
        $system = $this->persona($in['rival'])
            .'あなたはこの人物の判断役。車の運転は自動で行われ、あなたは運転しない。状況を見て、必要な時だけツールを呼ぶ。'
            .'何もしない方がよい時はツールを呼ばず「何もしない」とだけ答える。'
            .['rookie' => '性格: 遠慮がち。めったに進路をふさがない。', 'ace' => '性格: 負けず嫌い。抜かれそうなら進路をふさぐ。', 'legend' => '性格: 冷徹。勝つために必要な時だけ、正確に進路をふさぐ。'][$in['level']];

        $side = abs($in['lateral_m']) < 0.6 ? '真後ろ' : ($in['lateral_m'] > 0 ? '左側 ' : '右側 ').number_format(abs($in['lateral_m']), 1).'m';
        $closing = round($in['closing_kmh']);
        $speed = $closing === 0.0 ? '速度差なし' : ($closing > 0 ? "前の車より {$closing}km/h 速い" : '前の車より '.abs($closing).'km/h 遅い');
        $situation = '残り距離 '.round($in['remaining_m']).'m。'
            .($in['rival_ahead']
                ? 'あなたが前。プレイヤーは後方 '.round($in['gap_m'])."m、{$side}にいて、{$speed}。"
                : 'プレイヤーが前。あなたは後方 '.round($in['gap_m'])."m にいて、{$speed}。プレイヤーはあなたから見て".($side === '真後ろ' ? '真正面' : $side).'。')
            .'次のコーナー: '.round($in['corner']['distance_m']).'m 先の'.self::CORNER[$in['corner']['kind']].'。'
            .'このレースで進路をふさいだ回数: '.$in['blocks'].'、クラクションを鳴らした回数: '.$in['horns'].'。';

        foreach (config('llm.decide_models') as $model) {
            $message = $this->chat($model, (float) config('llm.decide_timeout'), [
                'max_tokens' => 120,
                'temperature' => 0.4,
                'tools' => $this->tools($in['rival_ahead']),
                'messages' => [['role' => 'system', 'content' => $system], ['role' => 'user', 'content' => $situation]],
            ]);
            if ($message === null) {
                continue;
            }
            $out = ['block' => null, 'horn' => null, 'model' => $model];
            foreach ($message['tool_calls'] ?? [] as $call) {
                $args = json_decode((string) ($call['function']['arguments'] ?? ''), true) ?: [];
                match ($call['function']['name'] ?? '') {
                    // (only a car in front can block: a model that asks for it from behind gets nothing)
                    'block_player' => $out['block'] = $in['rival_ahead'] ? round(min(6, max(2, (float) ($args['seconds'] ?? 3))), 1) : null,
                    'sound_horn' => $out['horn'] = in_array($args['style'] ?? '', self::HORNS, true) ? $args['style'] : 'short',
                    default => null,
                };
            }

            return $out;
        }

        return null;
    }

    private function persona(array $rival): string
    {
        return 'あなたは峠レースゲームのライバルドライバー「'.$rival['name'].'」（'.$rival['title'].'）。'
            .(($rival['description'] ?? '') !== '' ? '人物像: '.$rival['description'].' ' : '');
    }

    private function seconds(float $s): string
    {
        return number_format($s, $s < 10 ? 2 : 1).'秒';
    }

    /** The model's answer as one clean line: no quotes, no line breaks, not longer than asked. */
    private function line(string $text, int $max): string
    {
        $text = trim((string) preg_replace('/\s+/u', ' ', $text));
        // (not trim(): it works on bytes, and a list with 「」 in it cuts into other characters, the 。 at the end of a line)
        $text = (string) preg_replace('/^[\s「」『』"\'“”]+|[\s「」『』"\'“”]+$/u', '', $text);
        if (mb_strlen($text) > $max + 12) {
            // (it ignored the limit: the first sentence, if that fits)
            $first = preg_split('/(?<=[。！？!?])/u', $text)[0] ?? '';
            $text = mb_strlen($first) <= $max + 12 ? $first : '';
        }

        return $text;
    }

    /** What the model may call: blocking is offered only to a rival that is in front. */
    private function tools(bool $ahead): array
    {
        return array_slice([
            ['type' => 'function', 'function' => [
                'name' => 'block_player',
                'description' => 'プレイヤーの進路をふさぐ走行ラインを数秒間取る。あなたが前にいて、プレイヤーが後ろから迫って抜こうとしている時に使う。',
                'parameters' => ['type' => 'object', 'properties' => ['seconds' => ['type' => 'number', 'description' => 'ふさぐ時間（2〜6秒）']], 'required' => ['seconds']],
            ]],
            ['type' => 'function', 'function' => [
                'name' => 'sound_horn',
                'description' => 'クラクションを鳴らす。プレイヤーに前をふさがれている時や、抜き去る時の挨拶に使う。',
                'parameters' => ['type' => 'object', 'properties' => ['style' => ['type' => 'string', 'enum' => self::HORNS]], 'required' => ['style']],
            ]],
        ], $ahead ? 0 : 1);
    }

    /** One chat completion; the assistant's message, or null when the model failed or took too long. */
    private function chat(string $model, float $timeout, array $body): ?array
    {
        try {
            $response = Http::withHeaders([(string) config('llm.key_header') => (string) config('llm.key')])
                ->connectTimeout(2)->timeout($timeout)->acceptJson()
                ->post((string) config('llm.url'), ['model' => $model] + $body);
            if ($response->successful() && is_array($message = $response->json('choices.0.message'))) {
                return $message;
            }
            Log::warning('llm: '.$model.' answered '.$response->status());
        } catch (Throwable $e) {
            // (the message of a connection error names the URL, never the key: it is a header)
            Log::warning('llm: '.$model.' failed: '.class_basename($e));
        }

        return null;
    }
}
