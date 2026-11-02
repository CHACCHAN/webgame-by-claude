# 引き継ぎ書（2026-11-02 時点）

次のセッションはまずこのファイル、次に `CLAUDE.md`（構成・コマンド・注意点）、`docs/PROGRESS.md`（作業ログ。検証済み／未検証を区別して記録）を読むこと。
素材の出典・ライセンスは `docs/ASSETS.md`、設計は `docs/PLAN.md`。

## 1. 現在の状態
- ブランチ: `ccr-de1f3a33-58aazj`（ここで開発・コミット・プッシュする。オーナーの明示依頼がない限り PR は作らない）。
- テスト結果:
  - フロント単体テスト（vitest）: 25/25（`97086b3` 時点）
  - E2E（Playwright、Docker 上）: 9/9、約 23 分、オンライン 3 人対戦を含む（`97086b3` 時点）
  - バックエンド（`php artisan test`）: 13/13（2026-11-02 に実行）
- 遊べる内容:
  - コース 3 本: 朧峠、霧降湖、天狼スカイライン
  - 車 6 台:
    - 実車モデル 5 台: RX-7、S15、インプレッサ、スープラ、R34（Sketchfab、CC BY）
    - ハチロクのみ仮の自作車体
  - モード: タイムアタック、AI ライバル戦、ゴーストバトル、オンライン対戦（最大 3 人）
  - Laravel 側: ランキング、ゴースト、対戦ルーム
- オーナーは実 GPU（60fps）で遊んでおり、Cloudflare Tunnel で公開済み（オーナー自身が設定）。

## 2. オーナーからの制約（必ず守る）
- **作業環境**
  - 作業は Claude Code のクラウドセッション内だけで行う。オーナーのローカル PC には接続しない。
  - ローカルの Unity・Blender・GPU サーバーに依存しない。
  - Docker は必須。
- **お金・秘密情報**
  - 有料の外部 API・有料クラウドは使わない／登録しない。
  - API キーや認証情報を Git に入れない。Reverb の鍵はコンテナごとに自動生成する。
  - トークンをチャットに貼らせない（必要なら環境のシークレットへ）。
- **報告の仕方**
  - 未検証のものを「検証済み」と報告しない。
  - 新機能のためにバグを放置しない。
- **外部素材**
  - 依頼するのは外部素材が必要なときと、自力で解決できないときだけ。
  - Sketchfab のモデルは私的利用（身内のみ）。CC BY / CC0 を選び、ゲームから抜き出したモデルは避ける。
  - 素材は ASSETS.md と `CarSpec.model` に帰属表示を必ず書く。
- **進め方**
  - オーナーとのやりとりは日本語。
  - 依頼に対しては、実際に動かして確認してから報告する。

## 3. オーナー待ちのもの
1. **ハチロク（`hayate`）のモデル**
   - 元のリンクは 71.7MB で添付できなかった。軽い候補を 2 つ依頼中（ASSETS.md に URL）:
     - Flamestroke「Toyota Trueno AE86 (Initial D)」
     - Lexyc16「Toyota Corolla AE86 Trueno」
   - 届いたら車の取り込み手順（CLAUDE.md）に従う。
   - トレノはリトラなので `carSpecs.ts` の `hayate` に `popUpLamps: { x, z }` を設定する（RX-7 は `{ x: 0.57, z: 0.5 }`）。
   - 取り込み後に確認すること:
     - ガレージと走行の両方
     - 夜にリトラが開き、明け方に閉じること
     - テールランプ（夜はブレーキなしでも点灯）
     - ランプ素材が車の前後端だけにあること
2. **背景用の 3D 素材**（ASSETS.md「Scenery models proposed」に表）
   - 内容: 街灯、風力発電機、カーブミラー、自販機、鳥居、石灯籠、バス停、コーン。
   - **小物用の読み込み・配置の仕組みはまだ無い**。届いたら新しく作る:
     - glTF を読み込み、InstancedMesh で `TrackScenery.ts` に配置する。
     - 街灯なら、今の箱形の灯具（`buildLampMeshes`）を置き換える。腕の向きは `lampArmYaw`、光源の位置は `Lamp.position` を使う。
     - 風車は天狼の既存の自作風車と差し替える。
   - 帰属表示を ASSETS.md の「in game」に移すこと。

## 4. 実機でしか確かめられない未確認事項（オーナーの確認待ち）
- **光の近くの画面チカチカ**
  - 原因（街灯の光源が斜面・洞門天井に密着していた）は計測で確認し、対策済み。
  - 実機で消えたかは未確認。
- **音**
  - 対象: 接触の衝撃音・こすれ音、アフターファイアの破裂音、エンジン音、コーナー警告音。
  - いずれも耳では未確認。
- **アフターファイアの出方**
  - 実際の運転での頻度・見え方は未確認。
  - 静止状態で 60fps を模擬したスクリーンショットでのみ確認済み。
- 実 GPU での性能計測（フレーム時間、影、ドローコール）は未実施。
  - PROGRESS の「lamp posts are individual meshes」という記述は、街灯がすでに InstancedMesh なので古い可能性がある（要確認）。

## 5. 既知の小さな課題・次の候補
- **S15 の排気の出口**
  - モデルにマフラー名の部品が無いため、後端左右の推定位置から出ている。実物は中央寄り。
  - 直すなら `CarSpec` に排気位置の上書きを足す。
- **排気が出ない車**
  - オンライン対戦の相手車とリプレイの車には排気を出していない（アクセル開度の情報が無いため）。
- **ハチロク（自作）は固定式ライト**
  - トレノなのにリトラではない。モデルが届けば解消する。
- **公開サイト**
  - Cloudflare Access 等でのアクセス制限を推奨（オーナー判断）。
- **その他**
  - 朧峠のキービジュアルの車が実在車に似ている（公開前に差し替え推奨）。
  - タッチ操作は未対応。

## 6. 最近の主な変更（新しい順。詳細は PROGRESS「Session 3」）

### 2 回目のプレイ報告への対応（`cfd1297`、`97086b3`）
- 街灯が道路の外を向いていた → 向きの式を修正（`TrackScenery.lampArmYaw`、テストあり）。
- 光の近くの画面チカチカ → 街灯のリアルタイム光源が斜面・洞門天井に密着して強い光の点を作っていた。
  - 光源を灯具の 0.9m 下へ移動（`Game.ts` の `LAMP_LIGHT_DROP`）。
  - 地形からの距離は全コースで 6.2m 以上に。
- リトラ（RX-7）
  - 夜にポッドがせり上がって点灯し、明け方は格納される（`CarVisual.buildPods`、`CarSpec.popUpLamps`）。
  - バンパーのランプは車幅灯にした。
- テールランプ
  - 夜は常時点灯し、ブレーキでさらに明るくなる。
  - 取り込んだモデルはレンズの画像を通して光る（emissive map）。
  - RX-7 は取り込み直し。S15 は `tailLampGain` で明るさを補正。
- 排気（新規、`fx/Exhaust.ts`）
  - マフラーからの煙と、アクセルを急に戻したときのアフターファイア（炎と破裂音）。
- 取り込んだ車のアンカー
  - 変換時に目印（アンカー）のノードが消えていたので、形状から作り直すようにした（`CarModel.deriveAnchors`）。
  - これで排気の位置とライトの光の帯が正しく出る。
- スープラの内装がテール扱いで赤く光る問題を修正。
- 不正な時間帯の値で画面が真っ黒になる問題を修正（夜に戻す）。

### 実車モデル（`53408a2`、`8e8baf7`）
- 汎用の取り込みツールを作成: `tools/import-cars.cjs`、`tools/car-import.json`、`render/carImport.ts`。
- 取り込みツールの機能:
  - `restyle`: 色の変更、発光を消す
  - `reduce`: 誤差の上限付きで細かい部品を間引く

### 車の当たり判定（`793a100`）
- 実体: ライバルと実体同士で衝突する。オンラインの相手は `net/ProxyCar` の代役の車体として衝突する。
- 演出: 接触時の衝撃音・カメラの揺れ・こすれ音。
- AI の振る舞い:
  - 追突しない。
  - 後ろの車に対してラインを守る。
  - ゴール後は路肩に停車する。
- 検証用ツール: `tools/sim-duel.ts`。

## 7. 環境の立ち上げ（クラウドコンテナは毎回まっさら）
```bash
# Docker（E2E とスタック起動に必要）
nohup dockerd > /tmp/dockerd.log 2>&1 &
cp /root/.ccr/ca-bundle.crt docker/certs/proxy-ca.crt   # TLS を検査するプロキシの CA（gitignore 済み）
docker compose up -d --build && docker compose --profile test run --rm e2e   # E2E 9 件 ≈ 23 分

# フロントの確認
cd frontend && npx tsc -b && npx vite build && npx vitest run
nohup npx vite preview --port 4173 --strictPort > /tmp/preview.log 2>&1 &   # ブラウザ確認と車の取り込みに必要
```
- Playwright は `/opt/node-tools/node_modules/playwright` にある（`PW_MODULE` にこのパスを渡す）。
  `playwright install` はしないこと。
- **ブラウザでの確認**: `node tools/probe.cjs <low|medium> <チェック用スクリプト.cjs> [幅] [高さ]`
  - ゲームを開き、`async (page, { out }) => {}` 形式のスクリプトを実行する。`window.__game` で Game を操作できる。
  - スクリーンショットは `frontend/tools/scratch/`（gitignore 済み）に保存される。
  - よく使う操作:
    - `g.applyTimeOfDay('night'|'rain'|'dawn')`（この 3 つ以外は無い）
    - `g.startRace({ mode: 'time_attack', carId })`
    - `g.countdownT = 0.01`（カウントダウンを飛ばす）
    - `g.autoDrive = true`
    - `g.showGarage(id, color)`
  - URL に `?timescale=8` を付けると時間を早送りできる。
- **ソフトウェア描画は遅い**（SwiftShader、1〜6fps）
  - 見た目の確認は `low` か `medium` で行う。
  - ロジックだけ確認したいときは、スクリプト内で `g.renderer.render = () => {}` として描画を止めると約 60fps で回る。
  - 走行・物理の確認は Node の擬似走行で行う:
    - `npx tsx tools/sim-run.ts`
    - `npx tsx tools/sim-duel.ts`
- **ネットワーク**
  - Sketchfab の検索 API（`api.sketchfab.com/v3/search`）は使えるが、画像とダウンロード（media.sketchfab.com）は不可。
  - そのため候補は API で探し、オーナーにダウンロードを依頼する。
  - 届く zip は 20MB 程度までなら添付できている。
  - 届いたファイルは `/root/.claude/uploads/<セッション>/` にある。それぞれ新しい空フォルダに展開して扱う。
- **車の取り込みでのはまりどころ**（詳細は CLAUDE.md）
  - 取り込んだら `npx vite build` をし直してから確認する（preview は `dist/` を配信しているため）。
  - パターンは「メッシュ名 + 素材名」に対して照合される。
  - 一つの素材が複数の部品で共有されていることがある。マフラーとホイール、内装とテールなどで実際にあった。

## 8. 主なファイルの早見表
| 内容 | ファイル |
|---|---|
| ゲーム全体の制御（フェーズ、物理ループ、効果、街灯の光） | `frontend/src/game/Game.ts` |
| 車の見た目（ライト、リトラ、テール、車体の動き） | `frontend/src/game/render/CarVisual.ts` |
| 車モデルの読み込み・アンカー・自作車体 | `frontend/src/game/render/CarModel.ts` |
| 車の性能値・帰属表示・`popUpLamps`・`tailLampGain` | `frontend/src/game/vehicle/carSpecs.ts` |
| 背景（街灯、ガードレール、洞門、橋、標識） | `frontend/src/game/render/TrackScenery.ts` |
| AI（追突回避・ライン防御・停車） | `frontend/src/game/ai/AIDriver.ts` |
| オンラインの相手車（代役の車体） | `frontend/src/game/net/RemoteRacers.ts`, `ProxyCar.ts` |
| 排気・タイヤスモーク | `frontend/src/game/fx/Exhaust.ts`, `TireEffects.ts` |
| 車の取り込み | `frontend/tools/import-cars.cjs`, `car-import.json`, `src/game/render/carImport.ts` |
