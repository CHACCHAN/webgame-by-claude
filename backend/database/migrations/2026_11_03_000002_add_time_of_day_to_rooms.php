<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // the host picks the conditions with the course: every racer in the room drives in the same ones
        Schema::table('rooms', function (Blueprint $table) {
            $table->string('time_of_day', 8)->default('night')->after('track_id');
        });
    }

    public function down(): void
    {
        Schema::table('rooms', function (Blueprint $table) {
            $table->dropColumn('time_of_day');
        });
    }
};
