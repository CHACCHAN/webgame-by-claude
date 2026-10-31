<?php

namespace App\Events;

use App\Models\Room;
use Illuminate\Broadcasting\PresenceChannel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;

/** Room state for everyone in the room: members, cars, start time, finish times. */
class RoomUpdated implements ShouldBroadcastNow
{
    public function __construct(public array $room, private string $channel) {}

    public static function for(Room $room): self
    {
        return new self($room->payload(), $room->channelName());
    }

    public function broadcastOn(): PresenceChannel
    {
        return new PresenceChannel($this->channel);
    }

    public function broadcastAs(): string
    {
        return 'room.updated';
    }

    public function broadcastWith(): array
    {
        return ['room' => $this->room];
    }
}
