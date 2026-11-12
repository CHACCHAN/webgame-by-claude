<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\DeskController;
use App\Http\Controllers\Api\LeaderboardController;
use App\Http\Controllers\Api\MetaController;
use App\Http\Controllers\Api\PlayerController;
use App\Http\Controllers\Api\RivalAiController;
use App\Http\Controllers\Api\RoomController;
use App\Http\Controllers\Api\RunController;
use App\Http\Middleware\AuthenticatePlayer;
use Illuminate\Support\Facades\Route;

Route::get('/health', [MetaController::class, 'health']);
Route::get('/content', [MetaController::class, 'content']);

Route::get('/tracks/{trackId}/leaderboard', [LeaderboardController::class, 'index']);
Route::get('/runs/{run}/ghost', [RunController::class, 'ghost']);

// a guest: a name and a pass for this sitting
Route::post('/players', [PlayerController::class, 'store'])->middleware('throttle:10,1');

// members: the login through Authentik (config/authentik.php)
Route::middleware('throttle:30,1')->group(function () {
    Route::get('/auth/login', [AuthController::class, 'login']);
    Route::get('/auth/callback', [AuthController::class, 'callback']);
    Route::post('/auth/logout', [AuthController::class, 'logout']);
});
Route::get('/auth/me', [AuthController::class, 'me']);

// the rivals' voice and judgement (a language model behind the server; 503 when there is none)
Route::middleware('throttle:ai')->group(function () {
    Route::post('/ai/taunt', [RivalAiController::class, 'taunt']);
    Route::post('/ai/decide', [RivalAiController::class, 'decide']);
});

// the desk (About → AI窓口): a chat with a model behind the server (503 when there is none) and a plain report form;
// the reports have their own limit per address inside (DeskController::keep), the form a coarse one against floods
Route::post('/desk/chat', [DeskController::class, 'chat'])->middleware('throttle:desk');
Route::post('/desk/report', [DeskController::class, 'report'])->middleware('throttle:60,1');

Route::middleware(AuthenticatePlayer::class)->group(function () {
    Route::get('/players/me', [PlayerController::class, 'show']);
    Route::patch('/players/me', [PlayerController::class, 'update'])->middleware('throttle:20,1');
    Route::post('/runs', [RunController::class, 'store'])->middleware('throttle:30,1');
    Route::post('/auth/claim', [AuthController::class, 'claim'])->middleware('throttle:10,1');
    Route::get('/players/me/save', [PlayerController::class, 'save']);
    Route::put('/players/me/save', [PlayerController::class, 'storeSave'])->middleware('throttle:30,1');

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
