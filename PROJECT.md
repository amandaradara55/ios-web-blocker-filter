# ios-web-blocker-filter

## 目的

[iOS-web-blocker](https://github.com/amandaradara55/iOS-web-blocker) アプリが利用する、Safari Content Blocker 向け変換済みフィルタールールを生成・公開するリポジトリ。

公開されている ABP（AdBlock Plus）互換フィルターリスト（EasyList・uBlock Origin・AdGuard 等）を取り込み、アプリが直接読み込める JSON 形式に変換して GitHub Pages として配信する。

---

## このリポジトリが解決する問題

- ABP 互換フィルターはそのままでは Safari Content Blocker で使えない
- フィルターの変換・更新処理をモバイルアプリ上で行うのは重すぎる
- 変換済み JSON をアプリ本体リポジトリに含めると履歴が肥大化する

変換はこのリポジトリの CI（GitHub Actions）が担い、アプリは公開 URL から JSON を取得するだけにする。

---

## 出力フォーマット

アプリ本体の `BundledRulePreset.json` / `BundledCosmeticPreset.json` と同じ形式を使う。
アプリ側に新しいデコーダーが不要になる。

### ブロックルール（`dist/*-block-rules.json`）

```json
[
  {
    "id": "uuid-v5-stable",
    "name": "ads.example.com",
    "scope": "fqdn",
    "matchKind": "literal",
    "literalOperator": "exact",
    "pattern": "ads.example.com",
    "isEnabled": true,
    "rank": 0,
    "action": "block",
    "note": ""
  }
]
```

### 非表示ルール（`dist/*-cosmetic-rules.json`）

```json
[
  {
    "id": "uuid-v5-stable",
    "name": "#banner",
    "selector": "#banner",
    "domains": ["example.com"],
    "isEnabled": true,
    "rank": 0,
    "note": ""
  }
]
```

---

## リポジトリ構成

```
docs/               調査メモ・設計メモ
  adguard-japanese-filter-research.md
  ublock-origin-distribution-research.md
sources/            取り込み元フィルターの URL リスト・取得済みソース
  adguard-japanese/ AdGuard JapaneseFilter の取得結果
  ublock-origin/    uBlock Origin 配布物の raw/flat 取得結果
scripts/
  adguard_japanese_filter_common.py
  fetch_adguard_japanese_filter.py   AdGuard JapaneseFilter の sections を取得
  parse_adguard_japanese_filter.py   取得済み sections を JSON へ変換
  ublock_origin_common.py
  fetch_ublock_origin_filters.py     uBO 配布物と include 依存を取得
  flatten_ublock_origin_filters.py   uBO 配布物の include / if を展開
  parse_ublock_origin_filters.py     flatten 済み uBO ルールを JSON へ変換
.github/
  workflows/
    update-filters.yml       週次で変換・dist/ を更新する CI
dist/               変換済み JSON（GitHub Pages で公開）
  easylist-block-rules.json
  easylist-cosmetic-rules.json
  adguard-japanese-block-rules.json
  adguard-japanese-block-rules-disabled.json
  adguard-japanese-cosmetic-rules.json
  adguard-japanese-summary.json
  ...
```

---

## 変換ポリシー

Safari Content Blocker で表現できるパターンのみ変換し、対応外はスキップする。

| ABP パターン | 変換先 |
|---|---|
| `\|\|domain^` | FQDN exact ブロック |
| `\|\|domain^$third-party` | FQDN exact ブロック（third-party オプションは無視） |
| `/pattern/` | URL regex ブロック |
| `domain##selector` | 非表示ルール（CosmeticRule） |
| `$script`・`$image` 等のリソース限定オプション | スキップ |
| `#?#`・`#%#`・`#$#`・`[$path=]` | スキップ |

### Safari の制約

- ルール上限：**150,000 件**（複数リストを組み合わせる場合は優先度付けが必要）
- `url-filter` は正規表現。`|`（disjunction）を含む表現は不許可
- `if-domain` はドメインリストのみ（パス情報は持てない）

### ID の生成

UUID v5 を使い、`フィルターソース名 + パターン内容` からシードを生成する。同じ入力からは常に同じ ID が生成されるため、再実行しても差分が安定する。

---

## 参照フィルターリスト

詳細は `sources/` ディレクトリを参照。主な候補：

- **uBlock Origin filters** — https://github.com/uBlockOrigin/uAssets/tree/master/filters
  - 配布調査メモ: `docs/ublock-origin-distribution-research.md`
  - 実装は専用の `fetch -> flatten -> parse` パイプラインで扱う
- **EasyList** — https://easylist.to/easylist/easylist.txt
- **EasyPrivacy** — https://easylist.to/easylist/easyprivacy.txt
- **URLhaus malware filter** — https://gitlab.com/malware-filter/urlhaus-filter
- **AdGuard Japanese filter** — https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/

AdGuard Japanese Filter の構造調査と、`AdguardFilters` / `FiltersRegistry` のどちらを一次入力にするべきかの判断は `docs/adguard-japanese-filter-research.md` に記録する。

---

## 調査メモ

- AdGuard Japanese Filter の調査結果: `docs/adguard-japanese-filter-research.md`
- uBlock Origin 配布フィルターの調査結果: `docs/ublock-origin-distribution-research.md`
- 実装方針を更新する際は、まずこのメモを参照して「採用するセクション」「保留するセクション」「行単位での変換判定方針」を確認する
- 専用スクリプト: `scripts/fetch_adguard_japanese_filter.py` / `scripts/parse_adguard_japanese_filter.py`
- uBO は `scripts/fetch_ublock_origin_filters.py` / `scripts/flatten_ublock_origin_filters.py` / `scripts/parse_ublock_origin_filters.py` の 3 段で扱う
- uBO の procedural cosmetic（`remove-attr` / `remove-class` / `upward` / `xpath` / `style` など）は現状サポート外とし、`unsupported_cosmetic_selector` として弾く
- `scripts/parse_adguard_japanese_filter.py` は既定で `allowlist.txt` / `antiadblock.txt` / `general_extensions.txt` を出力対象から除外する
- `.com/Zen?` / `.jp/Zen?` は通常 block 出力に入れず、disabled block JSON に quarantine する

---

## 現在の状況

2026-04-29 時点で、AdGuard Japanese Filter 専用の取得・変換パイプラインと、uBlock Origin 配布物向けの専用 `fetch -> flatten -> parse` スクリプトは実装済み。

- 取得済みソース: `sources/adguard-japanese/*`
- 取得メタデータ: `sources/adguard-japanese/manifest.json`
- 変換結果: `dist/adguard-japanese-*.json`
- 変換集計: `dist/adguard-japanese-summary.json`
- uBO 用スクリプト: `scripts/fetch_ublock_origin_filters.py` / `scripts/flatten_ublock_origin_filters.py` / `scripts/parse_ublock_origin_filters.py`

最新の変換結果:

- block rules: 1156
- disabled block rules: 2
- cosmetic rules: 7135

現在の到達点:

- AdGuard Japanese Filter の `sections/*.txt` を直接取得できる
- `allowlist.txt` / `antiadblock.txt` / `general_extensions.txt` を既定で除外した parse ができる
- `.com/Zen?` / `.jp/Zen?` を quarantine 用の disabled block JSON に分離できる
- 実データを取得して `dist/` に出力済み
- uBO 配布物について、実配布 URL 前提の fetch / flatten / parse スクリプトを用意済み

未完了の主な項目:

- EasyList など他ソース向けの専用または汎用 fetch/parse
- 汎用 `convert_abp_to_preset.py` / `fetch_sources.py`
- GitHub Actions による定期更新
- GitHub Pages の公開設定

---

## アプリとの連携

このリポジトリの出力 URL をアプリ（iOS-web-blocker）の「リモートソース」として登録することで、最新フィルターを手動取り込みできる。

アプリ側の実装計画は [iOS-web-blocker/PROJECT.md](https://github.com/amandaradara55/iOS-web-blocker/blob/main/PROJECT.md) の「リモートフィルターリスト対応方針 Phase 2・3」を参照。

---

## 実装順

1. `[一部完了]` AdGuard Japanese Filter 専用の fetch/parse は実装済み。汎用 `scripts/convert_abp_to_preset.py` は未実装
2. `[一部完了]` AdGuard Japanese Filter の取得元はコード化済み。汎用 `sources/` URL リスト整備は未完了
3. `[一部完了]` `scripts/fetch_adguard_japanese_filter.py` は実装済み。汎用 `scripts/fetch_sources.py` は未実装
4. `[進行中]` AdGuard Japanese Filter については `dist/` への出力とローカル確認まで完了。他ソースは未着手
5. `[未着手]` GitHub Actions ワークフロー（週次自動更新）の作成
6. `[未着手]` GitHub Pages での公開設定
