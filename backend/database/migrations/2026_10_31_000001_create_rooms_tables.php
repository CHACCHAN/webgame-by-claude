<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // online battle rooms (up to config('game.online.max_players') racers)
        Schema::create('rooms', function (Blueprint $table) {
            $table->id();
            $table->string('code', 8)->unique();
            $table->foreignId('host_player_id')->constrained('players')->cascadeOnDelete();
            $table->string('track_id', 40);
            $table->string('status', 16)->default('waiting'); // waiting | racing | finished
            $table->unsignedInteger('race_no')->default(0);
            $table->unsignedBigInteger('start_at_ms')->nullable(); // unix epoch ms of the green light
            $table->timestamps();
        });

        Schema::create('room_players', function (Blueprint $table) {
            $table->id();
            $table->foreignId('room_id')->constrained()->cascadeOnDelete();
            $table->foreignId('player_id')->constrained()->cascadeOnDelete();
            $table->string('car_id', 20);
            $table->unsignedTinyInteger('slot');
            $table->unsignedInteger('finish_ms')->nullable();
            $table->timestamps();
            $table->unique(['room_id', 'player_id']);
            $table->unique(['room_id', 'slot']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('room_players');
        Schema::dropIfExists('rooms');
    }
};
