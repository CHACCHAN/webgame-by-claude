<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // set by the client once the room's course is loaded; the host can start only when everyone is ready
        Schema::table('room_players', function (Blueprint $table) {
            $table->boolean('ready')->default(false)->after('slot');
        });
    }

    public function down(): void
    {
        Schema::table('room_players', function (Blueprint $table) {
            $table->dropColumn('ready');
        });
    }
};
