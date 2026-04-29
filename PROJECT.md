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
sources/            取り込み元フィルターの URL リスト（1行1URL）
scripts/
  convert_abp_to_preset.py   ABP → JSON 変換スクリプト
  fetch_sources.py           sources/ の URL からフィルターを取得するスクリプト
.github/
  workflows/
    update-filters.yml       週次で変換・dist/ を更新する CI
dist/               変換済み JSON（GitHub Pages で公開）
  easylist-block-rules.json
  easylist-cosmetic-rules.json
  adguard-jp-block-rules.json
  adguard-jp-cosmetic-rules.json
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
- **EasyList** — https://easylist.to/easylist/easylist.txt
- **EasyPrivacy** — https://easylist.to/easylist/easyprivacy.txt
- **URLhaus malware filter** — https://gitlab.com/malware-filter/urlhaus-filter
- **AdGuard Japanese filter** — https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/

---

## アプリとの連携

このリポジトリの出力 URL をアプリ（iOS-web-blocker）の「リモートソース」として登録することで、最新フィルターを手動取り込みできる。

アプリ側の実装計画は [iOS-web-blocker/PROJECT.md](https://github.com/amandaradara55/iOS-web-blocker/blob/main/PROJECT.md) の「リモートフィルターリスト対応方針 Phase 2・3」を参照。

---

## 実装順

1. `scripts/convert_abp_to_preset.py` の作成（ABP → JSON 変換）
2. `sources/` の URL リスト整備
3. `scripts/fetch_sources.py` の作成（フィルター取得）
4. `dist/` への出力とローカル動作確認
5. GitHub Actions ワークフロー（週次自動更新）の作成
6. GitHub Pages での公開設定
