<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // A member is known by Authentik's subject (`oidc_sub`: the one key of an account; never the name). Everyone
        // else who is not a CPU driver is a guest whose pass ends (`token_expires_at`). The players of before (a token
        // kept in the browser for good) stay as guests with their records: their tokens no longer let anyone in
        // (no end date = no pass), but a member can still claim the records with one (AuthController::claim).
        Schema::table('players', function (Blueprint $table) {
            $table->string('oidc_sub', 191)->nullable()->unique();
            $table->timestamp('token_expires_at')->nullable();
            $table->text('save')->nullable();
            $table->unsignedInteger('save_rev')->default(0);
            $table->string('token_hash', 64)->nullable()->change();
        });

        Schema::create('player_sessions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('player_id')->constrained()->cascadeOnDelete();
            $table->string('token_hash', 64)->unique();
            $table->timestamp('expires_at')->index();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('player_sessions');
        Schema::table('players', function (Blueprint $table) {
            $table->dropUnique(['oidc_sub']);
            $table->dropColumn(['oidc_sub', 'token_expires_at', 'save', 'save_rev']);
        });
    }
};
