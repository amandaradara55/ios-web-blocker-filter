# ios-web-blocker-filter

## 目的

[iOS-web-blocker](https://github.com/amandaradara55/iOS-web-blocker) アプリが利用する、Safari Content Blocker 向け変換済みフィルタールールを生成・公開するリポジトリ。

公開されている ABP（AdBlock Plus）互換フィルターリスト（EasyList・uBlock Origin・AdGuard 等）を取り込み、アプリが直接読み込める JSON 形式に変換して GitHub Pages として配信する。

---

## このリポジトリが解決する問題

- ABP 互換フィルターはそのままでは Safari Content Blocker で使えない
- フィルターの変換・更新処理をモバイルアプリ上で行うのは重すぎる
- 変換済み JSON をアプリ本体リポジトリに含めると履歴が肥大化する

変換はこのリポジトリの CI（GitHub Actions）が担い、生成物は **`gh-pages` ブランチ** から配信し、アプリは公開 URL から JSON を取得するだけにする。

---

## 出力フォーマット

アプリが直接取り込む主配布物は、`dist/<filter-name>.json` の統合 JSON とする。
トップレベルはオブジェクトで、`block-rules` と `cosmetic-rules` を同居させる。

この形式にした理由は次の 2 点。

- iOS アプリ側で `1フィルターリスト = 1URL` の管理にしたい
- 将来の拡張に備えて、トップレベルにスキーマバージョンを持たせたい

出力対象の例:

```text
dist/
  adguard-japanese.json
  easylist.json
  easyprivacy.json
  ublock-ads.json
  ublock-mobile.json
```

```json
{
  "web-block-filter-version": "1.0",
  "block-rules": [
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
  ],
  "cosmetic-rules": [
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
}
```

`block-rules` / `cosmetic-rules` の各要素の内部フォーマットは従来の rule 配列と同一だが、配布物としては統合 JSON のみを生成する。

トップレベルのフィールド仕様:

| フィールド | 型 | 説明 |
|---|---|---|
| `web-block-filter-version` | string | スキーマバージョン。現在は `"1.0"` 固定 |
| `block-rules` | array | ネットワークブロックルール配列。空の場合は `[]` |
| `cosmetic-rules` | array | CSS 要素非表示ルール配列。空の場合は `[]` |

補足:

- `block-rules` と `cosmetic-rules` の各要素の内部フォーマットは変更しない
- cosmetic がないフィルターでも `cosmetic-rules` は `[]` を出す
- アプリ側はこの形式に合わせて、リモートソースを URL 1 本で扱う想定

---

## リポジトリ構成

```
docs/               調査メモ・設計メモ
  adguard-japanese-filter-research.md
  easylist-distribution-research.md
  ublock-origin-distribution-research.md
sources/            スクリプト実行時に使う中間出力のローカルキャッシュ置き場（Git ではプレースホルダのみ管理）
  adguard-japanese/ AdGuard JapaneseFilter の一時取得先
  easylist/         EasyList / EasyPrivacy の一時取得先
  ublock-origin/    uBlock Origin 配布物の raw/flat 一時出力先
scripts/
  adguard_japanese_filter_common.py
  easylist_common.py
  fetch_easylist_filters.py         EasyList / EasyPrivacy の完成済み配布物を取得
  parse_easylist_filters.py         取得済み EasyList / EasyPrivacy を JSON へ変換
  fetch_adguard_japanese_filter.py   AdGuard JapaneseFilter の sections を取得
  parse_adguard_japanese_filter.py   取得済み sections を JSON へ変換
  ublock_origin_common.py
  fetch_ublock_origin_filters.py     uBO 配布物と include 依存を取得
  flatten_ublock_origin_filters.py   uBO 配布物の include / if を展開
  parse_ublock_origin_filters.py     flatten 済み uBO ルールを JSON へ変換
.github/
  workflows/
    update-filters.yml       週次で生成物を `gh-pages` ブランチへ publish する CI
dist/               ローカル生成確認用の作業ディレクトリ（main ではプレースホルダのみ管理）
```

GitHub Actions / Pages 上では次の 2 段で動く。

- `Update Filters` workflow (`main`)
  - フィルター取得・変換を行い、生成物を `gh-pages` に publish する
- `pages build and deployment` (`gh-pages`)
  - `gh-pages` へ push された内容を GitHub Pages として公開する

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

### regex 制約の検証方針

`url-filter` の unsupported syntax は、公開ドキュメントだけでは網羅表を確認しづらい。したがって、パーサの静的 ban だけに依存せず、WebKit 自身の `WKContentRuleListStore.compileContentRuleList(...)` で compile 可否を検証する。

- `scripts/check_webkit_content_blocker_rules.swift` は統合 JSON の `block-rules` から `matchKind == "regex"` の rule を取り出し、`WKContentRuleList` の最小 JSON に変換して compile する補助スクリプト
- 失敗時は batch を二分探索して、どの regex が reject されたかを特定する
- 使い方の例: `swift scripts/check_webkit_content_blocker_rules.swift --input dist/easylist.json --output /tmp/easylist-webkit-report.json --batch-size 512`
- 単発検証の例: `swift scripts/check_webkit_content_blocker_rules.swift --batch-size 1 --regex '\\babc' --regex '(?=abc)' --regex '(?i)abc'`

2026-04-30 に実施した compile 検証結果:

- `dist/adguard-japanese.json`: regex 758 件中 758 件通過
- `dist/easylist.json`: regex 1474 件中 1474 件通過
- `dist/easyprivacy.json`: regex 4170 件中 4170 件通過
- `dist/ublock-ads.json`: regex 486 件中 486 件通過

この時点で確認できた重要事項:

- reject を確認: `\b` / `\B`
- reject を確認: lookahead / lookbehind
- reject を確認: inline flags `(?i)` `(?m)` `(?s)` `(?x)` `(?u)` `(?-i)`
- reject を確認: named backreference `\k<...>`
- compile 通過を確認: `\p{...}` / `\P{...}`
- compile 通過を確認: capture group `(abc)` / non-capturing group `(?:abc)`
- compile 通過を確認: 数値 backreference の検体 `([a-z]+)\1`
- 今回の既存ルール検証で新たに reject を確認: `{n}` および `{m,n}` 量指定

既存ルールで実際に reject された regex は次の系統だった:

- EasyList: `(https?:\/\/)104\.154\..{100,}` など `.{100,}` を含む 9 件
- uBlock Ads: `^https?:\/\/.*\/easylist\/[0-9]{5}` の 1 件

したがって、現時点では `\b` / `\B`・lookaround・inline flags は hard ban 維持が妥当であり、`\p{}` / `\P{}` と backreference 全体を一律 hard ban とみなす根拠は弱い。一方で、`{n}` / `{m,n}` は compile reject が確認されたため、静的チェック対象として再評価が必要。

### ID の生成

UUID v5 を使い、`フィルターソース名 + パターン内容` からシードを生成する。同じ入力からは常に同じ ID が生成されるため、再実行しても差分が安定する。

---

## 参照フィルターリスト

取得元 URL の詳細は調査メモと各スクリプトを参照。`sources/` はローカル中間出力用ディレクトリとして扱う。主な候補：

- **uBlock Origin filters** — https://github.com/uBlockOrigin/uAssets/tree/master/filters
  - 配布調査メモ: `docs/ublock-origin-distribution-research.md`
  - 実装は専用の `fetch -> flatten -> parse` パイプラインで扱う
- **EasyList** — https://easylist.to/easylist/easylist.txt
- **EasyPrivacy** — https://easylist.to/easylist/easyprivacy.txt
  - 配布調査メモ: `docs/easylist-distribution-research.md`
  - 実装は専用の `fetch -> parse` パイプラインで扱う
- **URLhaus malware filter** — https://gitlab.com/malware-filter/urlhaus-filter
- **AdGuard Japanese filter** — https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/

AdGuard Japanese Filter の構造調査と、`AdguardFilters` / `FiltersRegistry` のどちらを一次入力にするべきかの判断は `docs/adguard-japanese-filter-research.md` に記録する。

---

## 調査メモ

- AdGuard Japanese Filter の調査結果: `docs/adguard-japanese-filter-research.md`
- EasyList / EasyPrivacy の調査結果: `docs/easylist-distribution-research.md`
- uBlock Origin 配布フィルターの調査結果: `docs/ublock-origin-distribution-research.md`
- 実装方針を更新する際は、まずこのメモを参照して「採用するセクション」「保留するセクション」「行単位での変換判定方針」を確認する
- 専用スクリプト: `scripts/fetch_adguard_japanese_filter.py` / `scripts/parse_adguard_japanese_filter.py`
- uBO は `scripts/fetch_ublock_origin_filters.py` / `scripts/flatten_ublock_origin_filters.py` / `scripts/parse_ublock_origin_filters.py` の 3 段で扱う
- uBO の procedural cosmetic（`remove-attr` / `remove-class` / `upward` / `xpath` / `style` など）は現状サポート外とし、`unsupported_cosmetic_selector` として弾く
- `scripts/check_webkit_cosmetic_selectors.swift` は WebKit の `document.querySelectorAll()` で統合 JSON の `cosmetic-rules` を総当たり検証する補助スクリプト。Safari / WebKit で「invalid selector」が出た時の切り分けに使う
- 使い方の例: `swift scripts/check_webkit_cosmetic_selectors.swift --input dist/easylist.json --output /tmp/easylist-invalid-selectors.json --batch-size 512`
- このチェッカーは CSS selector 構文の妥当性確認用であり、`WKContentRuleList` 全体の compile 可否を完全再現するものではない
- `scripts/check_webkit_content_blocker_rules.swift` は `WKContentRuleListStore` で block rule の regex を compile 検証する補助スクリプト。regex の静的 ban を見直す時は、まずこのチェッカーの結果を確認する
- `scripts/parse_adguard_japanese_filter.py` は既定で `allowlist.txt` / `antiadblock.txt` / `general_extensions.txt` を出力対象から除外する
- `.com/Zen?` / `.jp/Zen?` は通常 block 出力に入れず、disabled block JSON に quarantine する

---

## 現在の状況

2026-04-29 時点で、現状取り込み対象としている AdGuard Japanese Filter / EasyList / EasyPrivacy / uBlock Origin について、個別の取得・変換パイプラインは実装済み。

配信 branch:

- `main`: scripts / docs / workflow を管理
- `gh-pages`: 生成済み JSON を公開

- ローカル中間出力先: `sources/adguard-japanese/*`
- ローカル取得メタデータ: `sources/adguard-japanese/manifest.json`
- ローカル変換結果: `dist/adguard-japanese.json` / `dist/adguard-japanese-block-rules-disabled.json`
- ローカル変換集計: `dist/adguard-japanese-summary.json`
- EasyList 用スクリプト: `scripts/fetch_easylist_filters.py` / `scripts/parse_easylist_filters.py`
- WebKit cosmetic selector 検証スクリプト: `scripts/check_webkit_cosmetic_selectors.swift`
- EasyList ローカル中間出力先: `sources/easylist/easylist.txt` / `sources/easylist/easyprivacy.txt`
- EasyList ローカル取得メタデータ: `sources/easylist/manifest.json`
- EasyList ローカル変換結果: `dist/easylist.json` / `dist/easyprivacy.json`
- EasyList ローカル変換集計: `dist/easylist-summary.json`
- uBO 用スクリプト: `scripts/fetch_ublock_origin_filters.py` / `scripts/flatten_ublock_origin_filters.py` / `scripts/parse_ublock_origin_filters.py`
- uBO ローカル取得メタデータ: `sources/ublock-origin/manifest.json` / `sources/ublock-origin/flat/manifest.json`
- uBO ローカル変換結果: `dist/ublock-ads.json` / `dist/ublock-mobile.json`
- uBO ローカル変換集計: `dist/ublock-origin-summary.json`
- アプリ向け配布物一覧: `docs/app-consumable-distribution-map.md`

最新の変換結果:

- AdGuard Japanese block rules: 1156
- AdGuard Japanese disabled block rules: 2
- AdGuard Japanese cosmetic rules: 7135
- EasyList block rules: 58031
- EasyList cosmetic rules: 22687
- EasyPrivacy block rules: 53244
- EasyPrivacy cosmetic rules: 2

現在の到達点:

- AdGuard Japanese Filter は `sections/*.txt` を直接取得し、既定除外 section を外した parse までできる
- EasyList / EasyPrivacy は完成済み配布物を直接取得し、`fetch -> parse` で `dist/` へ出力できる
- uBO 配布物は実配布 URL 前提で `fetch -> flatten -> parse` できる
- 取り込み対象として想定しているフィルターはここまでで一通り揃った
- アプリが使う JSON と、補助出力として除外すべき JSON の整理も完了した
- `main` と `gh-pages` の役割分離で、生成物更新が `main` の履歴を汚さない構成に移行した

---

## アプリとの連携

このリポジトリの出力 URL をアプリ（iOS-web-blocker）の「リモートソース」として登録することで、最新フィルターを手動取り込みできる。

アプリ側の実装計画は [iOS-web-blocker/PROJECT.md](https://github.com/amandaradara55/iOS-web-blocker/blob/main/PROJECT.md) の「リモートフィルターリスト対応方針 Phase 2・3」を参照。
