<?php

use Illuminate\Support\Facades\Route;

// The game client is served by nginx; Laravel only exposes the JSON API.
Route::get('/', fn () => response()->json(['name' => config('app.name'), 'api' => url('/api')]));
