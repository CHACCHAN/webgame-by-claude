# TOUGE NOCTURNE ― 朧峠

夜の峠を駆け下りる、ブラウザ向け 3D ダウンヒルレースゲーム。
架空の峠「朧峠」で、タイムアタック・AI ライバルとのバトル・ゴーストバトルが遊べます。
オンラインランキングとゴーストデータは Laravel + PostgreSQL のバックエンドが管理します。

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
- `backend/` — PHP 8.3 / Laravel 13 API（プレイヤー、走行記録、ランキング、ゴースト）
- `docker/` — PHP-FPM と nginx の Dockerfile
- `e2e/` — Playwright E2E テスト
- `docs/` — 設計（PLAN）、進捗（PROGRESS）、素材台帳（ASSETS）

## 動作環境・性能について

PC の Chrome / Edge / Firefox の最新版を対象とし、1080p・60fps を目標にしています。
開発に使ったクラウド VM には GPU がないため、実 GPU でのフレームレートは開発時点では計測できていません。
重い場合は「設定 → グラフィック品質 / 解像度スケール」を下げてください。

## ライセンス・クレジット

コース・車両・キャラクター・テクスチャ・効果音はすべて本プロジェクトのオリジナル（プロシージャル生成）です。
使用フォントやライブラリのライセンスは [docs/ASSETS.md](docs/ASSETS.md) を参照してください。
