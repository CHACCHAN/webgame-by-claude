# 外部素材の制作依頼（オーナー様向け）

ゲームは素材がなくても完全に動作します（肖像はシルエット、BGM は共通曲、キーアートは共通画像で代替）。
画像は ChatGPT、音楽は Gemini での生成を想定しています。完成したファイルはこの会話に直接アップロードしてください。

## 受け取り済み（第 1 弾）
`bgm_menu.mp3` / `bgm_race.mp3` / `jingle_finish.mp3` / `loading_loop.mp4` / 朧峠のライバル肖像 ×3 / キービジュアル。
組み込み済みです。加工内容は `docs/ASSETS.md` に記録しています。

## 第 2 弾：霧降湖・天狼スカイライン用（まとめて生成できます）

**状況（2026-10-31）**：第 2 弾はすべて受け取り・組み込み済み（霧降湖の肖像 ×3 とキーアートは 1 枚ずつ再送いただきました）。


| # | 素材 | 依頼先 | ファイル名 | 使う場所 | 優先度 |
|---|---|---|---|---|---|
| 1 | ライバル肖像 ×6 | ChatGPT | `kirifuri_rookie.png` `kirifuri_ace.png` `kirifuri_legend.png` `tenrou_rookie.png` `tenrou_ace.png` `tenrou_legend.png` | ライバル選択、バトル中 HUD | 高 |
| 2 | コースキーアート ×2 | ChatGPT | `course_kirifuri.png` `course_tenrou.png` | コース選択カード、ロード画面 | 高 |
| 3 | レース BGM ×2 | Gemini | `bgm_race_kirifuri.mp3` `bgm_race_tenrou.mp3` | 各コースのレース中 | 中 |
| 4 | 敗北ジングル | Gemini | `jingle_lose.mp3` | ライバルに負けたときの結果画面 | 低（任意） |

共通の注意：既存作品（特定のアニメ・漫画・ゲーム・実在の曲や車種）に似せないため、プロンプトには作品名・曲名・車名を入れていません。
第 1 弾のキービジュアルの車は実在の 80 年代クーペに近く見えるため、今回のキーアートは「車を描かず、テールランプの光跡だけ」にしています。

---

## 1. ライバル肖像 ×6（ChatGPT）
- 形式：PNG、**背景透過**、縦長 1024×1536（2:3）
- 第 1 弾と絵柄を揃えるため、**第 1 弾と同じ会話の続きで**生成するのが理想です。別の会話で作る場合は、
  第 1 弾の肖像を 1 枚添付して「この絵柄に合わせて」と伝えてから共通スタイルを送ってください

**共通スタイル（最初に送る）**
```
I will ask for six more character portraits for the same original Japanese street-racing game.
Keep exactly the same art style as before: semi-realistic anime illustration, cinematic night
lighting with cool blue rim light and warm orange sodium-lamp key light, upper body,
three-quarter view, sharp clean linework, painterly shading. Transparent background,
PNG, portrait 1024x1536. No text, no logos, no car brand emblems. The characters must be
original and must not resemble any existing anime, manga or game character.
```

**霧降湖 ROOKIE：椎名 ほのか（kirifuri_rookie.png）**
```
Character: Honoka Shiina, 20-year-old woman who delivers goods for her family's hot-spring inn
by the lake and has no idea how fast she is. Cheerful, slightly surprised smile, shoulder-length
chestnut hair in a low ponytail with loose strands, a lemon-yellow fleece jacket over an
indigo inn happi coat with a plain white pattern, a small wooden delivery crate under one arm.
Faint lake mist around her. Transparent background.
```

**霧降湖 LOCAL ACE：九条 迅（kirifuri_ace.png）**
```
Character: Jin Kujo, 28-year-old owner of a small tuning shop by a caldera lake. Cool,
analytical expression with a faint confident smile, swept-back dark hair with one loose strand,
thin rectangular glasses, deep wine-red mechanic's jacket with the sleeves pushed up, forearms
with light grease marks, holding a torque wrench resting on his shoulder. Transparent background.
```

**霧降湖 LEGEND：霧姫（kirifuri_legend.png）**
```
Character: "Kirihime", a mysterious legendary female night driver who appears only on foggy
nights over the lake. Ageless and elegant, long straight blue-black hair, pale silver-blue eyes,
calm unreadable expression, a long pale grey-blue coat with a high collar over a dark turtleneck,
thin wisps of fog flowing around her as if she brought it with her, a single faint red glow
reflected in her eyes like distant taillights. Quiet, cold, beautiful. Transparent background.
```

**天狼スカイライン ROOKIE：大河内 拓也（tenrou_rookie.png）**
```
Character: Takuya Okochi, 20-year-old second-year member of a university motor club, a
theory-first driver with little real experience. Serious, studious face with an eager look,
short neat black hair, round glasses, a royal-blue club windbreaker over a grey hoodie,
holding a small notebook full of handwritten lap notes and a pencil. Transparent background.
```

**天狼スカイライン LOCAL ACE：真壁 冴子（tenrou_ace.png）**
```
Character: Saeko Makabe, 34-year-old former rally driver. Sharp, fearless expression with a
knowing half-smile, short tousled ash-brown hair, a white racing jacket with plain blue and
red stripes and no logos, worn leather gloves, an open-face helmet held under one arm, a thin
scar on the chin. Strong, composed presence. Transparent background.
```

**天狼スカイライン LEGEND：天狼（tenrou_legend.png）**
```
Character: "Tenrou", a silent legendary night driver known as the wolf of the ridge.
Late 30s, tall and lean, long black hair tied back loosely, a scar across the left cheek,
piercing pale gold eyes, a dark charcoal long coat with a high collar, a faint silver-grey
fur trim, cold wind blowing his hair. Few words, overwhelming presence, calm like a wolf.
Starlight reflections on the coat. Transparent background.
```

## 2. コースキーアート ×2（ChatGPT）
- 形式：PNG、背景透過なし、横長 1536×1024（こちらで切り出します）

**霧降湖（course_kirifuri.png）**
```
Cinematic wide landscape illustration at 2 a.m. A winding mountain road descends through a
dark cedar forest towards a calm caldera lake. A full moon hangs over the rim mountains and
lays a long silver reflection on the still water; thin bands of mist float over the lake
surface. On the far shore, a small Japanese hot-spring town glows with warm lantern and window
lights and rising steam. Orange sodium street lamps and white guardrails line the lakeside
road, and a long-exposure red taillight trail curves along it (no car visible). Deep blue and
silver palette with warm amber accents, photorealistic concept art, dramatic composition.
No text, no watermark, no people, no cars.
```

**天狼スカイライン（course_tenrou.png）**
```
Cinematic wide landscape illustration at night. A two-lane skyline road runs along the crest
of a long grassy mountain ridge under a brilliant starry sky with the Milky Way. A row of
modern wind turbines stands along the ridge, each with a blinking red aviation light. Far
below and far away, the orange glow of a large city spreads across the plain to the horizon.
In the foreground the road drops off the ridge into a ladder of tight hairpin bends lit by
orange street lamps, with a long-exposure red taillight trail sweeping through them (no car
visible). Cool, windswept atmosphere, deep navy and violet palette with orange accents,
photorealistic concept art. No text, no watermark, no people, no cars.
```

## 3. レース BGM ×2（Gemini）
- 形式：MP3 または WAV、ボーカルなし、できれば 2 分以上（短くてもループします）

**霧降湖（bgm_race_kirifuri.mp3）**
```
Create an original instrumental track for a night mountain-road racing game, course set by a
misty caldera lake under the moon. Eurobeat-inspired dance music, 150 BPM, minor key, driving
four-on-the-floor kick and octave synth bass, a haunting lead melody played on a koto-like
plucked synth and a breathy bamboo-flute-like synth, shimmering arpeggios, a soaring
supersaw chorus. Mood: mysterious, elegant and fast, chasing a ghostly car through fog.
No vocals, no spoken words. Clean modern mix. Loop-friendly structure: short intro,
build-up, chorus, breakdown, final chorus.
```

**天狼スカイライン（bgm_race_tenrou.mp3）**
```
Create an original instrumental track for a night mountain-road racing game, course set on a
high ridge road under the stars with wind turbines. Fast trance-eurobeat, 160 BPM, heroic
major-key hook, huge detuned supersaw leads, galloping bassline, rolling toms and orchestral
brass stabs, a wide open euphoric chorus and a tense breakdown with wind-like noise sweeps
before the final drop. Mood: flat out at full speed along the skyline, then diving into the
hairpins. No vocals, no spoken words. Loop-friendly structure.
```

## 4. 敗北ジングル（Gemini・任意）
- 形式：MP3 または WAV、4〜6 秒、ループしない

```
Create a short original "race lost" sting, 5 seconds long, for a night racing game.
A descending minor-key synth phrase over a soft drum hit, ending on an unresolved, lingering
pad chord with a long reverb tail. Bittersweet rather than comic: "next time I'll catch you".
In the style of 90s arcade racing games. No vocals.
```

---

## 受け取り後の作業（こちらで実施）
1. 形式変換・最適化（WebP、MP3 の音量正規化）と配置。肖像は `public/img/rivals/<コース>-<レベル>.webp`、
   キーアートは `public/img/courses/<コース>.webp`
2. BGM のループ位置の設定（`AudioEngine.ts` の MUSIC 表）
3. 出典（サービス名・生成日）と加工内容を `docs/ASSETS.md` に記録
4. 動作確認（E2E テストを含む）
