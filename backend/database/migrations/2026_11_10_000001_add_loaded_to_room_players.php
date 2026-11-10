<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // `loaded`: set by the client once the room's course is loaded (what `ready` used to mean).
        // `ready` is now the player's own 準備完了 button: the host can start only when everyone is loaded and
        // every guest is ready.
        Schema::table('room_players', function (Blueprint $table) {
            $table->boolean('loaded')->default(false)->after('slot');
        });
        DB::table('room_players')->update(['loaded' => DB::raw('ready')]);
        DB::table('room_players')->update(['ready' => false]);
    }

    public function down(): void
    {
        DB::table('room_players')->update(['ready' => DB::raw('loaded')]);
        Schema::table('room_players', function (Blueprint $table) {
            $table->dropColumn('loaded');
        });
    }
};
