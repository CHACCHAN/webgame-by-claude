<?php

namespace App\Providers;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        // online rooms poll and update often; limit per player so friends behind one router are not throttled together
        RateLimiter::for('rooms', fn (Request $request) => Limit::perMinute(240)
            ->by('room:'.($request->attributes->get('player')?->id ?? $request->ip())));
        // the rivals' model: one race asks every few seconds at most; per address (no player is needed to race a rival)
        RateLimiter::for('ai', fn (Request $request) => Limit::perMinute(45)->by('ai:'.$request->ip()));
        // the desk's model (config/desk.php): per address a minute and a day, and all addresses together a day (what
        // the desk may cost at the gateway whatever happens). The form is not stopped by these: it has its own count
        $busy = fn (string $message) => fn () => response()->json(['message' => $message], 429);
        RateLimiter::for('desk', fn (Request $request) => [
            Limit::perMinute((int) config('desk.chat_per_minute'))->by('desk-m:'.$request->ip())
                ->response($busy('質問が続いています。1分ほど待ってからもう一度お試しください。')),
            Limit::perDay((int) config('desk.chat_per_day'))->by('desk-d:'.$request->ip())
                ->response($busy('本日のAI窓口の利用回数に達しました。報告・要望はフォームから送れます。')),
            Limit::perDay((int) config('desk.chat_total_per_day'))->by('desk-all')
                ->response($busy('AI窓口が混み合っています。報告・要望はフォームから送れます。')),
        ]);
    }
}
