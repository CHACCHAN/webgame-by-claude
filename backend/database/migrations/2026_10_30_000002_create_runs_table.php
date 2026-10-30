<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('runs', function (Blueprint $table) {
            $table->id();
            $table->foreignId('player_id')->constrained()->cascadeOnDelete();
            $table->string('track_id', 40);
            $table->string('car_id', 40);
            $table->string('mode', 20);
            $table->unsignedInteger('time_ms');
            $table->json('sector_ms');
            $table->string('rival_level', 20)->nullable();
            $table->boolean('rival_won')->nullable();
            $table->string('client_version', 20)->nullable();
            $table->timestamps();

            $table->index(['track_id', 'time_ms']);
            $table->index(['player_id', 'track_id']);
        });

        Schema::create('ghosts', function (Blueprint $table) {
            $table->id();
            $table->foreignId('run_id')->unique()->constrained()->cascadeOnDelete();
            $table->unsignedSmallInteger('format');
            $table->unsignedSmallInteger('interval_ms');
            $table->unsignedInteger('frame_count');
            // base64 encoded, gzip compressed binary frames (see frontend ghost codec)
            $table->longText('data');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ghosts');
        Schema::dropIfExists('runs');
    }
};
