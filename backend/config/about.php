<?php

/*
| Who made the game, as the About screen shows it (/api/content `about`). The owner's details are configuration,
| not code: nothing personal is written into the repository. Without these the screen shows the project's name
| and no links.
|   ABOUT_CREATOR       a name or a handle (up to 60 characters)
|   ABOUT_CREATOR_NOTE  a few words under it (up to 400 characters)
|   ABOUT_LINKS         "label|https://…,label|https://…" (up to six; http(s) only; no comma inside a link)
*/

$line = fn (string $text, int $max) => mb_substr(trim((string) preg_replace('/[\p{Cc}\p{Cf}]+/u', ' ', $text)), 0, $max);

$links = [];
foreach (explode(',', (string) env('ABOUT_LINKS', '')) as $entry) {
    [$label, $url] = array_pad(array_map('trim', explode('|', $entry, 2)), 2, '');
    // (a link is opened by the visitor's browser: web addresses only, nothing a script could hide in)
    if ($label !== '' && preg_match('#^https?://[^\s<>"\']{4,300}$#i', $url) && count($links) < 6) {
        $links[] = ['label' => $line($label, 40), 'url' => $url];
    }
}

return [
    'creator' => $line((string) env('ABOUT_CREATOR', ''), 60) ?: 'Touge Nocturne Project',
    'note' => $line((string) env('ABOUT_CREATOR_NOTE', ''), 400),
    'links' => $links,
];
