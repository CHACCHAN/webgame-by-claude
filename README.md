# TOUGE NOCTURNE ― 朧峠

夜の峠を駆け下りる、ブラウザ向け 3D ダウンヒルレースゲーム。
港町を見下ろす「朧峠」、月を映すカルデラ湖へ下る「霧降湖」、風車の稜線を駆ける「天狼スカイライン」の
3 つの架空の峠で、タイムアタック・AI ライバルとのバトル・ゴーストバトル、最大 3 人のオンライン対戦が遊べます。
オンラインランキング・ゴーストデータ・対戦ルームは Laravel + PostgreSQL のバックエンドが管理します。

## 起動方法

必要なもの: Docker（Compose v2 以降）

```bash
docker compose up --build
```

ブラウザで http://localhost:8080 を開いてください（初回ビルドは数分かかります）。
データベースのマイグレーションと初期データ（CPU ライバルの記録とゴースト）は起動時に自動で適用されます。

| 用途 | コマンド |
|---|---|
| 停止 | `docker compose down`（記録を消すなら `-v`） |
| 開発（Vite HMR） | `docker compose --profile dev up` → http://localhost:5173 |
| バックエンドのテスト | `docker compose --profile test run --rm backend-test` |
| E2E テスト（スタック起動中に） | `docker compose --profile test run --rm e2e` |

ポートやパスワードを変える場合は `.env.example` を `.env` にコピーして編集してください。
TLS を検査するプロキシの内側でビルドする場合は、そのプロキシの CA 証明書を `docker/certs/*.crt` に置いてください。

## オンライン対戦（最大 3 人）

1. メインメニューの「ONLINE BATTLE」で走り屋ネームと車を選びます。
2. 1 人がコースを選んで「ルームを作成」し、表示された 4 文字のルームコードを友達に伝えます。
3. ほかの人は同じ画面でコードを入力して「参加」します（最大 3 人）。
4. 全員そろったらホストが「レース開始」。サーバーが決めた同じ時刻に全員のシグナルが青になります。
5. ゴールした順にタイムが並び、ホストは「もう一度走る」で同じメンバーと再戦できます。

- 車同士には当たり判定があります（AI ライバル戦も同じ）。ぶつけ合い・幅寄せでの押し合いができ、接触すると衝撃音とカメラの揺れが出ます。
  ほかのプレイヤーの車は、通信で届いた位置へ向かって走る「代役の車体」として自分の画面の物理世界にいるため、
  押せば押し返され、少しずれてもすぐ元の走行ラインに戻ります（相手の画面では相手自身の車が正です）。
  コース復帰の直後や大きくワープした車は 1.5 秒ほど半透明扱い（すり抜け）になり、重なったまま弾き飛ばされることはありません。
- 通信は Laravel Reverb（WebSocket、Pusher プロトコル）。Reverb は `app` コンテナ内で起動し、nginx が `/app/` を中継します。
  鍵はコンテナ起動ごとに自動生成され、リポジトリには含まれません。WebSocket が使えない場合もロビーと結果はポーリングで同期します。
- 同じネットワークの別の PC からは `http://<起動した PC の IP>:8080` で参加できます。インターネット越しに遊ぶには、
  下の Cloudflare Tunnel を使います。

## 外部公開（Cloudflare Tunnel）

ポート開放なしで、Cloudflare で管理している自分のドメインから公開できます。

1. Cloudflare ダッシュボード（Networking → Tunnels）でトンネルを作成し、Docker 用コマンドに含まれるトークンをコピーする。
2. 同じトンネルに Published application のルートを追加する（例: `touge.example.com`）。サービス URL は `http://web:80`。
3. `.env` にトークンと公開 URL を書く（`.env` は Git の管理外です。トークンはコミットしないでください）。

   ```bash
   COMPOSE_PROFILES=tunnel
   CLOUDFLARE_TUNNEL_TOKEN=<トークン>
   APP_URL=https://touge.example.com
   ```

4. 起動する。`COMPOSE_PROFILES=tunnel` により `cloudflared` も一緒に起動します。

   ```bash
   docker compose up -d --build
   ```

`--profile dev` や `--profile test` を付けた起動では `cloudflared` は起動しません。

TLS は Cloudflare が終端し、オンライン対戦の WebSocket も同じホスト名の `wss://` で通ります。

## 操作方法

| 操作 | キーボード | ゲームパッド |
|---|---|---|
| アクセル / ブレーキ・バック | W / S（↑ / ↓） | RT / LT |
| ステアリング | A / D（← / →） | 左スティック |
| サイドブレーキ | Space | B / RB |
| シフト（MT 時） | E / Q | Y / LB |
| カメラ切替 | C | 十字キー↑ |
| コース復帰 | R | Back |
| ポーズ | Esc / P | Start |

## 構成

- `frontend/` — React 19 + TypeScript + three.js / React Three Fiber + Rapier 物理（Vite）
- `backend/` — PHP 8.3 / Laravel 13 API（プレイヤー、走行記録、ランキング、ゴースト、対戦ルーム）+ Laravel Reverb（WebSocket）
- `docker/` — PHP-FPM と nginx の Dockerfile
- `e2e/` — Playwright E2E テスト
- `docs/` — 設計（PLAN）、進捗（PROGRESS）、素材台帳（ASSETS）

## 開発者向けツール（`frontend/` で実行）

| コマンド | 内容 |
|---|---|
| `npm test` | ユニットテスト（コース形状・ゴーストの圧縮・車両挙動・AI の完走） |
| `npm run sim` | AI ドライバーで全車種・全難易度をヘッドレス走行させ、タイムと事故を集計 |
| `npx tsx tools/sim-duel.ts [車:難易度] [車:難易度]` | 当たり判定ありで AI 2 台を同じコースで競わせ、接触回数・最大衝撃・完走を確認（`COURSE=` でコース指定） |
| `npm run handling` | 加速・制動・旋回・ドリフト保持などの操縦性テスト |
| `npm run seed:bots` | CPU ドライバーの記録とゴーストを生成（Laravel のシーダーが読み込む） |
| `npm run assets:cars` | 車両モデルを GLB に書き出し、glTF-Transform で最適化（`vite preview` 起動中に実行） |

デバッグ用 URL パラメータ：`?autodrive=1`（AI が自車を運転）、`?timescale=4`（時間を加速）。

## 動作環境・性能について

PC の Chrome / Edge / Firefox の最新版を対象とし、1080p・60fps を目標にしています。
開発に使ったクラウド VM には GPU がないため、実 GPU でのフレームレートは開発時点では計測できていません。
重い場合は「設定 → グラフィック品質 / 解像度スケール」を下げてください。

## ライセンス・クレジット

コース・車両・地形・効果音は本プロジェクトのオリジナル（プロシージャル生成）です。路面・地面・岩・コンクリートの
写真テクスチャは ambientCG（CC0）、BGM・ライバル肖像・キービジュアル・ロード動画はオーナー様が生成 AI で制作したものです。
使用フォントやライブラリのライセンスは [docs/ASSETS.md](docs/ASSETS.md) を参照してください。
