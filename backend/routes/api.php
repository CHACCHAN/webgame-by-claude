<?php

use App\Http\Controllers\Api\LeaderboardController;
use App\Http\Controllers\Api\MetaController;
use App\Http\Controllers\Api\PlayerController;
use App\Http\Controllers\Api\RunController;
use App\Http\Middleware\AuthenticatePlayer;
use Illuminate\Support\Facades\Route;

Route::get('/health', [MetaController::class, 'health']);
Route::get('/content', [MetaController::class, 'content']);

Route::get('/tracks/{trackId}/leaderboard', [LeaderboardController::class, 'index']);
Route::get('/runs/{run}/ghost', [RunController::class, 'ghost']);

Route::post('/players', [PlayerController::class, 'store'])->middleware('throttle:10,1');

Route::middleware(AuthenticatePlayer::class)->group(function () {
    Route::get('/players/me', [PlayerController::class, 'show']);
    Route::patch('/players/me', [PlayerController::class, 'update'])->middleware('throttle:20,1');
    Route::post('/runs', [RunController::class, 'store'])->middleware('throttle:30,1');
});
