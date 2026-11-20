# 再開メモ（2026-11-20、Claude Code → 別ハーネス → また Claude Code）

オーナーが利用制限のため、しばらく Claude 以外のモデル・ハーネスで作業する。このファイルは
**その時点で作業中だったもの**と、**どこから続ければよいか**をまとめたもの。読む順:

1. このファイル
2. `CLAUDE.md`: 構成・コマンド・落とし穴。Claude 用の名前だが**プロジェクトの規則そのもの**なので、どのハーネスでも守ること。
3. `docs/HANDOVER.md` の `-0.` の行: 版ごとの変更（オーナー向けの日本語）
4. `docs/PROGRESS.md` の末尾: 新しい節ほど下。検証済み／未検証を区別して書く。

**別ハーネスへのお願い:** 作業したら、この下の「その後」に 1 行ずつ足すこと（日付・版・ブランチ・コミット・何を検証したか）。
Claude Code に戻ったとき、そこから続ける。

## 本番の状態（11-20 時点）
- 公開中は **v2.7.6**（main `ccr-de1f3a33-58aazj` = `92af06c`）。GitHub の main も同じ。
- 反映は main の作業ツリーで `docker compose up -d --build`（CLAUDE.md の「owner's PC」節）。
- 反映したら次を確かめる:
  - 公開側でも新しいバンドルが出ている;
  - `/api/content` の version;
  - `/api/tracks/oboro-downhill/leaderboard` が 200;
  - `docker exec touge-nocturne-app-1 php artisan llm:check`。
- 反映の前に GPU で `node tools/gpu-errors.cjs` を回し、レースの画像を 1 枚見る。描画に触れたときは 3 回、`QUERY='?webgl=1'` でも回す。

## 作業中 1: v2.8.0 戦車 5 両の公開（オーナー承認済み 11-20「はい」）
- **ブランチ `course-proposal` の `7c82266`**。作業ツリーは `.claude/worktrees/fx3d`。main には未マージ、未反映。
- 中身:
  - 戦車 5 ブランチ（tank-type10 / type16 / leopard2a5 / m1a2 / t14）のマージ;
  - 非公開スイッチ `tanks` をオンにした（`frontend/src/game/release.ts` と `backend/config/game.php`）;
  - 版を 2.8.0 に;
  - AI 窓口の知識に戦車と砲の操作を追加（知識ファイルの上限テストを 8 kB → 10 kB に）;
  - テストの台数を 22 → 27 に;
  - E2E の操作画面の表を 2 つ（車と戦車の砲）に;
  - CLAUDE.md と ASSETS.md を更新。
- **済んだ確認:**
  - フロント: tsc、vitest 293、build（`index-BmLIhppp.js`）;
  - GPU（`~/.local/opt/wt/v280/gpu.log`）: gpu-errors は WebGPU（標準・戦車入り ×2）、WebGL 2（戦車入り）、エドワーズ（hayate, f15j, m1a2, su47）がすべて 0 件;
  - tank-check: type10 / type16 / leopard2a5 / m1a2 / phone（16式、スマホ表示）は全手順 ok、0 件;
  - tank-check t14:
    - 1 回目: 全手順 ok。ただし起動時に 4 件出た: 模型 3 つの Failed to fetch と、index 数 0 の Draw 警告 1 件。そのとき負荷は 10 前後で、ファイルは 200 で出ていた。
    - 再実行（`tc-t14b`）: GPU のエラーは 0 件。照準器での 2 発目が外れて 3 手順が FAIL。ライバルは 263 m 先を走っていた（`dawn-sight.jpg`）。
    - 2 回目の FAIL は、CLAUDE.md に書いた tank-check の既知の揺れ（当たった後のポーズを外すと、ライバルが走り続ける）と同じ形。
    - 反映前にもう一度回し、出力を全部残すとよい（`| tee`）。
  - バックエンド 80 件すべて通過（知識ファイルの大きさと台数の修正後）;
  - E2E `game.spec.ts` 10 件通過（操作表の修正後。前回の全体実行でほかの 18 件は通過済み）;
  - tank-duel（M1A2 対 hayate、テスト用スタック）: 全手順 ok。A の弾が B に当たり、B は自分の画面でコースに戻り、A の画面でもそこに見えた。0 件。
  - ログ: `~/.local/opt/wt/e2e-280b.log`。テスト用スタックは片付け済み。
- **まだ:** 確認は上で全部回った（11-20 04:20、`GPU-DONE` と `STACK-DONE` あり）。残りは下の手順 2 から。
- 残りの手順:
  1. ログで `GPU-DONE`、`E2E-DONE`、`STACK-DONE` と各 `ok` を確かめ、`~/.local/opt/wt/v280/tc-*/` の画像を見る。
     - 途中で止まっていたら、プレビューを立て直してから流し直す:
       `cd .claude/worktrees/fx3d/frontend && API_PROXY=http://127.0.0.1:9 npx vite preview --port 4179 --strictPort --host 127.0.0.1`
     - 流し直すのは `~/.local/opt/wt/v280/gpu.sh` の該当行と `~/.local/opt/wt/e2e-280b.sh`。
  2. `docs/PROGRESS.md` の末尾に `## v2.8.0 (11-20): …` の節を書く。
  3. `docs/HANDOVER.md` に `-0. **v2.8.0（2026-11-20、オーナー承認）**: …` の行を足す。
  4. コミットする。
  5. main の作業ツリーで `git merge --ff-only course-proposal`。この RESUME.md のコミットが main に先にあるので、ff にならなければ `course-proposal` 側で main をマージしてから。
  6. `docker compose up -d --build` で反映し、上の確認をする。
  7. GitHub へプッシュ: `G=$(git config --get remote.origin.url); git push -q "$G" HEAD:refs/heads/ccr-de1f3a33-58aazj`。GitLab のミラーには押さない。
- オーナーへの報告に入れること:
  - 未検証: 音を耳で、実機のゲームパッド、平地での超信地旋回、実機スマホ;
  - M1A2 の GLB は 1,505,780 B で、予算 1.5 MB を 0.4 %（5.8 kB）超えている。作り直しても ±20 kB 動くので、そのままにした;
  - 戦車 5 両の模型（計 6.3 MB）は、ほかの車両と同じくメニューの裏で全員が読み込む。

## 作業中 2: スマホの車両選択で車両が見切れる（oboro / kirifuri、zoom 1.62 > 許容 1.52）
- ブランチ `phone-framing`、作業ツリー `.claude/worktrees/agent-a4f14c5da1b2280fe`。v2.7.5 が土台。
- 途中状態のコミットは `c04001c`（WIP。電車では合わせ込みが遅いので、このままでは取り込まない）。状態は `~/.local/opt/wt/phone-framing/STATE.md`（11-20 04:02）。続きはそこから。
- 取り込むときは main（v2.8.0 以降）をマージしてから確認し、パッチ版（2.8.x）として出す。

## オーナーの判断待ち: スマホの画質「低」の解像度（測定はオーナーが 11-20 に了承）
- ブランチ `low-resolution` の `84f7f5b`。v2.7.6 が土台。未マージ。
- 今: 画質「低」は DPR に関係なく 0.75 CSS px。DPR 3 のスマホ（844×390）では 633×292 で描くので粗い。
- 案: 「低」は最大 0.5 MP（下限は今の 0.75 CSS px、上限は 0.75×DPR）。
  - そのスマホでは 1040×480 になる;
  - DPR 1 の PC と大きな DPR 2 の画面は変わらない;
  - 定数は `store/settings.ts` の `LOW_PIXELS`。
- コスト:
  - RX 5700 XT の実測: GPU 時間が朧峠の夜で ×1.6、エドワーズで ×2;
  - 3DMark の比から見積もった朧峠の GPU 時間（±2 倍の幅）: iPhone 13 級 5 → 8 ms、Galaxy A56 級 9 → 15 ms、**A36 級 13 → 21 ms（60fps の枠 16.7 ms を超える）**。
- 比較シート: `~/.local/opt/wt/lowres/sheet-lowres.png`。1:1 の切り抜きは `~/.local/opt/wt/lowres/crops/`。
- Claude の推奨: **0.5 MP を上限にし、重い端末では今の解像度まで自動で下げる動的解像度と一緒に出す**。
  - 0.5 MP 固定だけだと安い機種で 60fps を割るおそれがある;
  - 安全側の代案は `LOW_PIXELS = 0.33`（見積もりで A36 級 17 ms）。
- オーナーが選ぶまで取り込まない。

## 小さな直し（次のパッチで）
- 戦闘機の衝突防止灯（`beacon` 材質）が光らない。
  - 原因: `tools/blender/jets/f15.py` 76 行目が `strength=0.0` で、GLB の emissive が黒。
  - 案（実行時）: `render/JetModel.ts` の `lamp()` で、glow が黒なら基本色（`m.color`）を使う。色の値だけなのでシェーダーは作り直しにならない。
  - 確かめ方: エドワーズで f15j の画像と gpu-errors。
- 戦車まわりの改善案（各モデル担当の提案）:
  - `handmask.py` の GrabCut に乱数の種を入れる;
  - tank-check は撃つ前にポーズを仕掛ける;
  - 超信地旋回の確認は平地で;
  - M1A2 の装填手の防盾の窓を軽くする。

## Claude Code のセッションが終わると止まるもの
- プレビュー :4179（fx3d の `frontend/dist`）と :4184（`~/.local/opt/quality/dist-debug`）。どちらも `API_PROXY=http://127.0.0.1:9` で立て直せる。
- 上の 2 本のチェック用スクリプト。止まっていれば手で流し直す。テスト用スタックは `~/.local/opt/wt/stack.sh fx3d 8090 80 down` で消す。
- 本番スタック（compose プロジェクト `touge-nocturne`）と cloudflared は関係なく動き続ける。

## 守ること（抜粋。詳しくは CLAUDE.md）
- **秘密:**
  - `.env` の鍵・アドレス（`LLM_API_*`、`AUTHENTIK_*`、トンネルのトークン）は、表示・コミット・ブラウザへの送信をしない;
  - `.env` は編集しない;
  - 公開ホスト名やメンバー名を書かない。
- **プレビューとテスト:**
  - `vite preview` は必ず `API_PROXY=http://127.0.0.1:9` を付けて動かす（本番 API に記録を送らないため）;
  - テストは `stack.sh` の隔離スタックで行い、本番では行わない。
- **GPU と Blender:**
  - GPU の Chrome は `~/.local/opt/quality/gpurun.sh` 経由で使う（ロックを共有している）;
  - Blender は `~/.local/opt/carfit/blender.sh` 経由で使う;
  - Blender と Chrome を同時に動かさない;
  - 重い作業の前に `free -m` で 2.5 GB 以上空いていることを確かめる。
- **プロセスとコミット:**
  - 自分のコマンド行に含まれる文字列で `pkill -f` しない;
  - `git add -A` はしない（`docs/spec/` と `.claude/` は追跡しない）;
  - `frontend/tsconfig.tsbuildinfo` はコミットしない。
- **版と反映:**
  - プレイヤーに見える反映ごとに版を上げる（`frontend/package.json`、`package-lock.json` の 2 か所、`backend/config/game.php` の 108 行目）;
  - DB を移行する前にはダンプを取る。
- **模型:**
  - 3D モデルはすべて自作;
  - 新しい模型はオーナーがシートを見てから取り込む;
  - 写真の画素はコミットしない。
- **報告:** 未検証のものを検証済みと書かない。

## その後（別ハーネスが追記する）
- 2026-11-20 / v2.8.0 / `ccr-de1f3a33-58aazj` (`ad458fc`) / 戦車 5 両公開: T-14 の `tank-check.cjs` 再実行（`tc-t14c.log`: 夜・夜明け全手順 ok、0 件）と `~/.local/opt/wt/v280/` の全画像を確認し、`PROGRESS.md`・`HANDOVER.md` 更新、`course-proposal` を `ccr-de1f3a33-58aazj` にマージ、`docker compose up -d --build` で本番反映（`index-BmLIhppp.js`、`/api/content` version `2.8.0`・車両 27 台、`/api/tracks/oboro-downhill/leaderboard` 200、`php artisan llm:check` 全モデル listed を確認）、GitHub へ push 済み。
- 2026-11-20 / v2.8.1 / `ccr-de1f3a33-58aazj` (`195c76e`) / スマホ車両選択の見切れ修正（`phone-framing` `bf054c2`）＋小修正一式（`small-fixes-281` `cbcbe88`）を統合・公開: ①スマホ車両選択 `Game.fitGarage`（`camera/garageFit.ts`）にジオメトリ別遅延フラット BVH・地点別 `garageOccluders` キャッシュ等を導入しコールド計算時間を全車両 `< 22 ms`（1x、E5 `1239→13.9 ms`、L0 `1471→12.9 ms`、ゴキブリ `1309→21.7 ms`）へ短縮、スマホ見切れ `82/98→0/98`・戦車 `25/25→0/25`・PC 1080p/720p 差分 0・E2E `mobile.spec.ts` 通過 ②戦闘機 `beacon` 黒 emissive 時の `m.color` フォールバック（Edwards 夜間で赤点滅確認、単体テスト追加）③M1A2 防盾等の軽量化で `m1a2.glb` を `1,479,112 B`（1.5 MB 予算内、ゲート IoU 0.911 維持）へ縮小 ④平地での超信地旋回計測・単体テスト追加 ⑤`handmask.py` GrabCut 乱数種固定（ビット一致確認）⑥`tank-check.cjs` 2発目リロード中のライバル位置保持（`m1a2`・`t14` とも全手順 ok）。統合ツリーで `tsc`・`vitest` 301 件・`build`（`index-DfU7HPF8.js`）・`gpu-errors.cjs`（WebGPU ×3・WebGL 2・Edwards すべて 0 件）とレース画像を確認し、本番反映（`/api/content` version `2.8.1`・車両 27 台、leaderboard 200、`llm:check` 全 listed）・GitHub push 済み。
- 2026-11-20 / v2.8.2 / `ccr-de1f3a33-58aazj` (`53a197e`) / スマホ画質「低」の解像度上限 0.5 MP ＋ 動的解像度（オーナー選択「1」、`low-resolution` `84f7f5b` + `f7470bc`）を統合・公開: 画質「低」の描画上限を 0.5 MP（下限 0.75 CSS px、上限 0.75×DPR；844×390 DPR 3 スマホで `1040×480`、DPR 1 の PC 等は不変）とし、実時間 45 フレーム中央値 `> 18.5 ms` で `0.75 CSS px`（`633×292`）まで 3 段階で自動降格する `DynamicResolution`（`render/drawingRatio.ts` / `RenderHost.ts`、60 Hz vsync で振動しないヒステリシス・2 回失敗した段のロック付き）を実装。`tsc`・`vitest` 318 件・`build`（`index-CeNSXe0I.js`）・実 GPU `gpu-errors.cjs`（スマホ DPR 3 `low` WebGPU/WebGL 2・通常 WebGPU ×3/WebGL 2 すべて 0 件）および負荷プローブ（`1040×480 → 881×407 → 746×345 → 633×292` 自動降格と無振動保持）を確認し、本番反映（`/api/content` version `2.8.2`・車両 27 台、leaderboard 200、`llm:check` 全 listed）・GitHub push 済み。
- 2026-11-20 / v2.8.3 / `ccr-de1f3a33-58aazj` / オーナー報告 2 件の修正・公開: ①「車両一覧」（`CarsScreen`）で戦闘機（`f15j` / `f15c` / `su47`、`torque: [[0, 0]]`）を表示した際、`peakPowerKw`（`game/vehicle/stats.ts`）が `t[1][0]` を参照して `TypeError` を投げ画面全体が真っ暗になる不具合を修正（`t.length < 2` で早期 return、`picker.test.ts` に全 27 台の `peakPowerKw` 検査追加）②戦車プレイ中に `Esc` でポーズメニューを開いた際、照準 HUD（`.gun-hud`）が最前面に残る不具合を修正（`GunSight.tsx` で `.paused` クラスを切り替え、`hud.css` で `.gun-hud.paused { display: none; }`・`.pause { z-index: 10; }`、`tank-check.cjs` に `gunHidden` 検査追加）。`tsc`・`vitest` 318 件・`build`（`index-C9n7zMOC.js`）・実 GPU での車両一覧全 27 台送り（戦闘機 3 機の画面画像確認）＋戦車ポーズ画像確認・`gpu-errors.cjs` 0 件・`tank-check.cjs`（`type10` 全手順 ok、0 件）を確認し、本番反映・GitHub push。
