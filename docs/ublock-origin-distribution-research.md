# uBlock Origin 配布フィルター調査メモ

調査日: 2026-04-29

## 目的

`uBlockOrigin/uAssets` で公開されているフィルター群のうち、このリポジトリで取り込み候補にしたい `uBlock filters – Ads` と `mobile` について、実際の配布元 URL と配布上の扱いを確認する。

主な確認対象は次の 2 点。

- `uBlock filters – Ads` の正式な配布元はどこか
- `filters-mobile.txt` は独立配布物なのか、`Ads` の補助リストなのか

---

## 結論

### `uBlock filters – Ads`

`uBlock filters – Ads` は、uBO 本体リポジトリの `assets/assets.json` に `ublock-filters` として定義されている既定リストである。

一次的に追うべき配布元 URL:

- `https://ublockorigin.github.io/uAssets/filters/filters.txt`

同じエントリには CDN 配布先や同梱ファイルも定義されているが、このリポジトリで自動取得対象にするなら、まずは上記の `uAssets` 配布 URL を一次入力にするのが自然。

### `mobile`

`mobile` に対応するソースファイルは `uAssets/filters/filters-mobile.txt` で、ファイル冒頭のタイトルは `uBlock filters – Mobile` になっている。

一次的に追うべき配布元 URL:

- `https://ublockorigin.github.io/uAssets/filters/filters-mobile.txt`

ただし、uBO 本体の `assets/assets.json` では `uBlock filters – Mobile` という独立した既定リスト定義は確認できなかった。`filters.txt` の末尾で `!#if env_mobile` 条件付きで `filters-mobile.txt` が `include` されており、配布上は `Ads` のモバイル向け補助リストとして扱われていると見るのが妥当。

---

## 確認結果の整理

### `assets/assets.json` 側

確認できた内容:

- `ublock-filters` というエントリがある
- `title` は `uBlock filters – Ads`
- `contentURL` の先頭は `https://ublockorigin.github.io/uAssets/filters/filters.txt`
- `supportURL` は `https://github.com/uBlockOrigin/uAssets`

このため、`uBlock filters – Ads` は `filters.txt` を配布物として参照していると判断できる。

### `filters.txt` 側

`filters.txt` 末尾には次の構造がある。

- 年次ファイル群の `include`
- `ubo-link-shorteners.txt` の `include`
- `!#if env_mobile` 条件付きで `filters-mobile.txt` を `include`

つまり `filters-mobile.txt` は、ソースファイルとしては独立している一方で、uBO 側の組み込み配布では `env_mobile` 条件で `Ads` リストに合流する構造になっている。

### `filters-mobile.txt` 側

確認できた内容:

- ファイルタイトルは `uBlock filters – Mobile`
- `Homepage` は `https://github.com/uBlockOrigin/uAssets`
- 単独ファイルとして直接取得できる

したがって、このリポジトリの取得処理では `filters-mobile.txt` を独立 URL として扱って問題ない。

---

## このリポジトリへの反映方針

現時点では、取得候補 URL として次の 2 本を持つのがよい。

```text
https://ublockorigin.github.io/uAssets/filters/filters.txt
https://ublockorigin.github.io/uAssets/filters/filters-mobile.txt
```

実装上の解釈は次のとおり。

- `filters.txt` は `uBlock filters – Ads` の正式な配布物として扱う
- `filters-mobile.txt` は単独取得可能なソースとして扱う
- ただしメタデータ上は `Ads` と対等な独立既定リストではなく、`Ads` に対する mobile 条件付き補助入力として扱う

---

## 実装設計

### なぜ uBO 専用実装が必要か

AdGuard Japanese Filter 向けのように「セクション単位で取得して、そのまま行単位パースする」方式は、uBO の配布物にはそのまま適用しにくい。

理由:

- `filters.txt` 自体に `!#include` が残っている
- `filters.txt` と `filters-mobile.txt` の両方に `!#if` / `!#else` / `!#endif` が残っている
- `mobile` は単独リストというより `Ads` に合流する条件付き入力として扱われている

このため、uBO は AdGuard と同じ汎用 fetch/parse ではなく、専用の `fetch -> flatten -> parse` パイプラインに分ける。

### パイプライン

#### 1. fetch

実配布 URL からルートファイルを取得し、`!#include` を辿って依存ファイルも一緒に取得する。

出力先:

- `sources/ublock-origin/raw/*.txt`
- `sources/ublock-origin/manifest.json`

取得対象のルート:

- `ads` -> `filters.txt`
- `mobile` -> `filters-mobile.txt`

#### 2. flatten

取得済みの raw ファイル群に対して、`!#include` と条件分岐を展開して、パース用のフラットテキストを生成する。

生成するプロファイル:

- `ads`
  - ルート: `filters.txt`
  - `env_mobile=false`
- `mobile-effective`
  - ルート: `filters.txt`
  - `env_mobile=true`
- `mobile-standalone`
  - ルート: `filters-mobile.txt`
  - `env_mobile=true`

初期実装で使う主な define:

- `env_mobile`
- `env_safari`
- `env_chromium`
- `env_firefox`
- `cap_html_filtering`
- `ext_ubol`

未知のシンボルは `false` 扱いにし、manifest に記録する。

出力先:

- `sources/ublock-origin/flat/ads.txt`
- `sources/ublock-origin/flat/mobile-effective.txt`
- `sources/ublock-origin/flat/mobile-standalone.txt`
- `sources/ublock-origin/flat/manifest.json`

#### 3. parse

flatten 済みテキストを Safari Content Blocker 向け JSON に変換する。

処理対象:

- `ads.txt`
- `mobile-effective.txt`

最終出力:

- `dist/ublock-ads-block-rules.json`
- `dist/ublock-ads-block-rules-disabled.json`
- `dist/ublock-ads-cosmetic-rules.json`
- `dist/ublock-mobile-block-rules.json`
- `dist/ublock-mobile-block-rules-disabled.json`
- `dist/ublock-mobile-cosmetic-rules.json`
- `dist/ublock-origin-summary.json`

### mobile の扱い

`mobile` は `filters-mobile.txt` 単体をそのまま最終配布物にするのではなく、`mobile-effective` から `ads` と重複するルールを差し引いた差分リストとして出力する。

つまり:

- `ads` = `filters.txt` を `env_mobile=false` で展開した結果
- `mobile-effective` = `filters.txt` を `env_mobile=true` で展開した結果
- `mobile` 出力 = `mobile-effective - ads`

この形にしておくと、アプリ側で `Ads + mobile` を同時に有効化しても重複を増やしにくい。

### JSON 変換ルール

初期実装では、安全側に寄せて次だけを受理する。

- `||domain^`
- `||domain/path`
- `/regex/` のうち `|` を含まないもの
- 単純な URL literal / `*` パターン
- `##selector`
- `domain##selector`

### procedural cosmetic の扱い

uBO の cosmetic ルールには、単純な CSS selector ではない procedural cosmetic が含まれる。

例:

- `:remove-attr(...)`
- `:remove-class(...)`
- `:upward(...)`
- `:xpath(...)`
- `:style(...)`
- `:others(...)`
- `:has-text(...)`

これらは「要素を CSS selector で隠す」だけではなく、属性変更、祖先探索、XPath 評価、style の直接適用などを伴う uBO 独自拡張である。

このリポジトリの現在の出力モデルは、Safari Content Blocker 向けの単純な block rule と cosmetic rule だけであり、cosmetic 側も `selector + domains` 形式しか持たない。したがって procedural cosmetic をそのまま JSON に入れても、次の問題がある。

- Safari 側で有効な CSS selector として解釈できない可能性が高い
- uBO 本来の意味を保持できず、意図しない挙動になる可能性がある
- 属性変更や style 適用を「単なる selector 文字列」として保存しても再現できない

このため、現時点では procedural cosmetic はサポート外として扱い、`unsupported_cosmetic_selector` としてスキップする。

初期実装でスキップするもの:

- `@@` allowlist
- `+js(` や `scriptlet(` を含むルール
- `#?#` / `#$#` / `#%#`
- `replace=` / `redirect=` を含む modifier 付きルール
- `domain=` や各種リソース型 modifier を含むルール
- `:has(` など Safari Content Blocker にそのまま落としにくい拡張 selector
- `:remove-attr(` / `:remove-class(` を含む procedural cosmetic

### 実装ファイル

この設計に対応するスクリプトは次のとおり。

- `scripts/ublock_origin_common.py`
- `scripts/fetch_ublock_origin_filters.py`
- `scripts/flatten_ublock_origin_filters.py`
- `scripts/parse_ublock_origin_filters.py`

---

## 補足

ローカルの [uBlock-filters.txt](/Users/be/aiwork/ios-web-blocker-filter/uBlock-filters.txt) には GitHub の `blob` URL が列挙されているが、自動取得や CI を考えると、実際に配布されている `ublockorigin.github.io/uAssets/filters/*.txt` を一次入力に寄せた方が扱いやすい。
