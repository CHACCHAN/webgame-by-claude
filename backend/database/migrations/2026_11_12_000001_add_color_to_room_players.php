<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // the paint the member picked for their vehicle (#rrggbb: a car's colour, a train's line, a livery's
        // swatch); null = none picked, the client paints the seat's colour
        Schema::table('room_players', function (Blueprint $table) {
            $table->string('color', 7)->nullable()->after('car_id');
        });
    }

    public function down(): void
    {
        Schema::table('room_players', function (Blueprint $table) {
            $table->dropColumn('color');
        });
    }
};
