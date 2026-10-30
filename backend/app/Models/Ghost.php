<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Ghost extends Model
{
    protected $fillable = ['run_id', 'format', 'interval_ms', 'frame_count', 'data'];

    public function run(): BelongsTo
    {
        return $this->belongsTo(Run::class);
    }
}
