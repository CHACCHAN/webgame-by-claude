# 外部素材の制作依頼（オーナー様向け）

ゲームは素材なしでも完全に動作します（音楽はシンセのアンビエント、画像は 3D シーン）。
以下の素材をいただければ、そのままファイルを置くだけで自動的に使われます。
**依頼は 3 点のみ**です。優先度順に並べています。

---

## 依頼 1（優先度：高）レース BGM

- **依頼先**：音楽生成 AI（Suno / Udio / Gemini の音楽生成機能など。ChatGPT は音楽生成不可）
- **用途**：レース中の BGM（カウントダウン後からゴールまでループ再生）
- **希望ファイル形式**：MP3（192kbps 以上）、ステレオ
- **長さ**：2 分 30 秒〜3 分（ループ再生するので、終わり方は自然なフェードやカットで OK）
- **希望ファイル名**：`bgm_race.mp3`
- **配置先**：`frontend/public/audio/bgm_race.mp3`
- **注意**：既存曲の模倣にならないよう、曲名やアーティスト名をプロンプトに入れていません

**コピー＆ペースト用プロンプト（英語の方が品質が安定します）**

```
Original high-energy instrumental for a night mountain-road racing game.
Eurobeat-inspired dance track, 155 BPM, driving four-on-the-floor kick, punchy octave bassline,
bright detuned supersaw lead melody with a memorable hook, fast synth arpeggios, orchestral hits,
dramatic key change in the final chorus. Japanese 90s arcade racing atmosphere, energetic and
heroic, no vocals, no spoken words. Clean modern mix, strong low end, loop-friendly structure:
intro 8 bars, verse, pre-chorus build-up, big chorus, breakdown, final chorus.
```

（Suno の場合：Style 欄に `eurobeat, high energy, 155 bpm, instrumental, synth lead, arcade racing` 、Instrumental をオンにしてください）

---

## 依頼 2（優先度：中）メニュー BGM

- **依頼先**：音楽生成 AI（同上）
- **用途**：タイトル・メニュー・ランキング画面の BGM（ループ再生）
- **希望ファイル形式**：MP3（192kbps 以上）
- **長さ**：1 分 30 秒〜2 分 30 秒
- **希望ファイル名**：`bgm_menu.mp3`
- **配置先**：`frontend/public/audio/bgm_menu.mp3`

**コピー＆ペースト用プロンプト**

```
Original mellow instrumental for the title screen of a night-time Japanese mountain pass racing game.
Late-night city pop meets synthwave, 92 BPM, warm electric piano chords, soft slap bass,
gated reverb drums, airy analog pad, a gentle nostalgic synth lead. Mood: looking down at the
glittering lights of a harbour city from a quiet mountain pass at 2 a.m., calm but with a hint of
anticipation. No vocals. Seamless loop-friendly ending.
```

---

## 依頼 3（優先度：低）ロード画面のキービジュアル

- **依頼先**：ChatGPT（画像生成）または Gemini（Imagen）
- **用途**：起動時ロード画面の背景（半透明で表示）。SNS 共有用のサムネイルにも使えます
- **希望ファイル形式**：PNG または WebP（WebP 推奨。PNG ならこちらで変換します）
- **サイズ・縦横比**：1920×1080（16:9）、背景透過なし
- **希望ファイル名**：`keyart.webp`（PNG の場合 `keyart.png`）
- **配置先**：`frontend/public/img/keyart.webp`
- **構図**：手前に夜の峠道のヘアピン、ガードレール、オレンジのナトリウム灯。左奥の眼下に港町の夜景と海、
  空に満月。車は特定の実在車種に見えない 80 年代風の国産クーペのシルエットとテールランプの光跡のみ。

**コピー＆ペースト用プロンプト**

```
Cinematic wide 16:9 illustration, 1920x1080. A winding Japanese mountain pass road at 2 a.m.,
a tight hairpin bend in the foreground lined with white guardrails, orange sodium street lamps
and yellow chevron signs, dark cedar forest on steep slopes. Far below on the left, a harbour city
glitters with thousands of warm lights along a bay; a full moon hangs over the sea with a silver
reflection. A single generic 1980s Japanese sports coupe (not any real brand or model, no logos,
no readable text) drifts through the hairpin, its red taillights leaving long light trails and a
faint plume of tyre smoke. Moody deep blue night palette with warm orange accents, light haze,
photorealistic concept art, dramatic composition, high detail. No text, no watermark, no people.
```

---

## 受け取り後の作業（こちらで実施）

1. ファイルを上記の配置先に置く
2. 出典（使用サービス名・生成日）とライセンス条件を `docs/ASSETS.md` に記録
3. 音量バランスを調整して動作確認

※ 生成サービスの利用規約で商用利用やクレジット表記の条件が異なります。
   有料プランでのみ商用利用可などの条件がある場合は、受け渡し時に教えてください。
