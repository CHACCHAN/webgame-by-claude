<?php

use App\Http\Controllers\Api\LeaderboardController;
use App\Http\Controllers\Api\MetaController;
use App\Http\Controllers\Api\PlayerController;
use App\Http\Controllers\Api\RoomController;
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

    // online battle rooms
    Route::middleware('throttle:rooms')->group(function () {
        Route::post('/rooms', [RoomController::class, 'store']);
        Route::get('/rooms/{code}', [RoomController::class, 'show']);
        Route::post('/rooms/{code}/join', [RoomController::class, 'join']);
        Route::patch('/rooms/{code}/me', [RoomController::class, 'update']);
        Route::post('/rooms/{code}/leave', [RoomController::class, 'leave']);
        Route::post('/rooms/{code}/start', [RoomController::class, 'start']);
        Route::post('/rooms/{code}/finish', [RoomController::class, 'finish']);
        Route::post('/rooms/{code}/rematch', [RoomController::class, 'rematch']);
        Route::post('/broadcasting/auth', [RoomController::class, 'auth']);
    });
});
