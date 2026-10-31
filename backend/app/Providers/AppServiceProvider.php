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
    }
}
