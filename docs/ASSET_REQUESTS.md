# 外部素材の制作依頼（オーナー様向け）

ゲームは素材なしでも完全に動作します。いただいた素材は、こちらで組み込み・音量調整・記録を行います。
画像は ChatGPT、音楽と動画は Gemini での生成を想定しています。完成したファイルはこの会話に直接アップロードしてください。

| # | 素材 | 依頼先 | ファイル名 | 使う場所 | 優先度 |
|---|---|---|---|---|---|
| 1 | レース BGM | Gemini | `bgm_race.mp3` | レース中 | 高 |
| 2 | メニュー BGM | Gemini | `bgm_menu.mp3` | タイトル・メニュー | 高 |
| 3 | ライバル肖像 ×3 | ChatGPT | `rival_rookie.png` `rival_ace.png` `rival_legend.png` | ライバル選択画面、バトル中の HUD | 高 |
| 4 | キービジュアル | ChatGPT | `keyart.png` | ロード画面、SNS 共有用サムネイル | 中 |
| 5 | ゴール時ジングル | Gemini | `jingle_finish.mp3` | ゴール直後の結果画面 | 中 |
| 6 | ロード画面ループ動画 | Gemini | `loading_loop.mp4` | ロード画面の背景（無音・暗めに表示） | 低（任意） |

共通の注意：既存作品（特定のアニメ・漫画・ゲーム・実在の曲や車種）に似せないため、プロンプトには作品名・曲名・車名を入れていません。
生成サービスの利用規約で商用利用やクレジット表記の条件がある場合は、受け渡し時に教えてください。

---

## 1. レース BGM（Gemini）
- 形式：MP3 または WAV。長さはできれば 2 分以上。短い場合（30 秒程度）でもループ再生するので使えます
- ボーカルなし（インストゥルメンタル）

```
Create an original instrumental track for a night mountain-road racing game.
Eurobeat-inspired high-energy dance music, 155 BPM, driving four-on-the-floor kick,
punchy octave synth bassline, bright detuned supersaw lead with a catchy heroic hook,
fast synth arpeggios and orchestral stabs, a dramatic key change in the last chorus.
Mood: racing downhill through hairpins at 2 a.m., adrenaline and speed.
No vocals, no spoken words. Clean modern mix with strong low end.
Structure that loops well: short intro, build-up, big chorus, breakdown, final chorus.
```

## 2. メニュー BGM（Gemini）
- 形式：MP3 または WAV。1 分 30 秒以上が理想（短くても可）

```
Create an original mellow instrumental track for the title screen of a night-time
Japanese mountain pass racing game. Late-night city pop meets synthwave, 92 BPM,
warm electric piano chords, soft slap bass, gated-reverb drums, airy analog pads and a
gentle nostalgic synth lead. Mood: looking down at the glittering lights of a harbour
city from a quiet mountain pass at 2 a.m., calm with a hint of anticipation.
No vocals. Smooth, loop-friendly ending.
```

## 3. ライバル肖像 ×3（ChatGPT）
- 形式：PNG、**背景透過**、縦長 1024×1536（2:3）
- 同じ会話の中で 3 枚続けて生成すると絵柄が揃います。まず共通スタイルを送り、続けて 1 人ずつ依頼してください

**共通スタイル（最初に送る）**
```
I will ask for three character portraits for an original Japanese street-racing game.
Keep the same art style for all three: semi-realistic anime illustration, cinematic night
lighting with cool blue rim light and warm orange sodium-lamp key light, upper body,
three-quarter view, sharp clean linework, painterly shading. Transparent background,
PNG, portrait 1024x1536. No text, no logos, no car brand emblems. The characters must be
original and must not resemble any existing anime, manga or game character.
```

**ROOKIE：森 健太（rival_rookie.png）**
```
Character 1: Kenta Mori, 19-year-old rookie street racer. Earnest and slightly nervous
smile, messy short dark-brown hair, freckles, oversized mustard-yellow hoodie under an
open grey work jacket, holding a pair of cheap driving gloves. Youthful, likeable,
determined eyes. Transparent background.
```

**LOCAL ACE：高嶺 遼（rival_ace.png）**
```
Character 2: Ryo Takamine, 26-year-old local ace of the mountain pass. Calm, confident,
slightly cocky half-smile, short undercut black hair with a small scar on the eyebrow,
navy mechanic's jumpsuit unzipped to the waist with sleeves tied, black t-shirt, a car
key on a red cord around his fingers. Sharp, focused eyes. Transparent background.
```

**LEGEND：朧（rival_legend.png）**
```
Character 3: "Oboro", a mysterious legendary night driver rumoured to be a ghost.
Ageless, androgynous, long silver-white hair moving as if in wind, pale skin, face half
hidden in shadow so only one calm pale-grey eye is visible, long off-white coat with a
high collar, faint mist curling around the shoulders. Quiet, unsettling, elegant.
Transparent background.
```

## 4. キービジュアル（ChatGPT）
- 形式：PNG、背景透過なし、横長（1536×1024 などの最大サイズで。こちらで 16:9 に切り出します）

```
Cinematic wide landscape illustration. A winding Japanese mountain pass road at 2 a.m.:
a tight hairpin bend in the foreground lined with white guardrails, orange sodium street
lamps and yellow chevron signs, dark cedar forest on steep slopes. Far below on the left,
a harbour city glitters with thousands of warm lights along a bay; a full moon hangs over
the sea with a silver reflection. A single generic 1980s Japanese sports coupe (not any
real brand or model, no logos, no readable text) drifts through the hairpin, red
taillights leaving long light trails and a faint plume of tyre smoke. Deep blue night
palette with warm orange accents, light haze, photorealistic concept art, dramatic
composition. No text, no watermark, no people.
```

## 5. ゴール時ジングル（Gemini）
- 形式：MP3 または WAV、5〜8 秒、ループしない

```
Create a short original victory jingle, 6 seconds long, for crossing the finish line in a
night racing game. Bright supersaw synth fanfare over a big drum fill, rising arpeggio,
ending on a strong sustained major chord with a reverb tail. Energetic and triumphant,
in the style of 90s arcade racing games. No vocals.
```

## 6. ロード画面ループ動画（Gemini・任意）
- 形式：MP4、16:9、8 秒程度。音声は使いません（無音で再生）
- 注意：実写風の映像はゲーム本編（3DCG）と質感が異なるため、暗くぼかして背景にだけ使います

```
Slow cinematic aerial drone shot at night, gliding over a winding mountain road with
hairpin bends lit by orange street lamps, dark cedar forest on the slopes, and a glowing
harbour city with thousands of lights along a bay far below under a full moon. Light
mist in the valleys. Smooth, steady camera motion that could loop. No cars in close-up,
no people, no text, no logos. Deep blue and amber colour palette, 16:9.
```

---

## 受け取り後の作業（こちらで実施）
1. 形式変換・最適化（WebP / Opus などに圧縮）と配置
2. ライバル肖像をライバル選択カードとバトル中 HUD に組み込み、ゴール時ジングルを結果画面に追加
3. 出典（サービス名・生成日）とライセンス条件を `docs/ASSETS.md` に記録
4. 音量バランスの調整と、E2E テストを含む動作確認
