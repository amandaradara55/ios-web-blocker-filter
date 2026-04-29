# AdGuard Japanese Filter 調査メモ

調査日: 2026-04-29

## 目的

`AdguardTeam/AdguardFilters` の `JapaneseFilter` を、このリポジトリで Safari Content Blocker 向け JSON に変換する前提で調査した内容をまとめる。

主な確認対象は次の 2 点。

- 変換元として `AdguardFilters` と `FiltersRegistry` のどちらを採用するべきか
- `JapaneseFilter/sections/*.txt` の各ファイルがどの役割を持っているか

---

## 結論

### 変換元として優先すべきもの

一次入力は `AdguardTeam/AdguardFilters/JapaneseFilter/sections/*` を採用するのがよい。

理由:

- `AdguardFilters` はフィルター作者が直接編集するソースリポジトリである
- `JapaneseFilter` はセクションごとに役割分担されており、Safari で扱えるルールと扱えないルールを分離しやすい
- `FiltersRegistry` は配布用・互換性調整済みの成果物寄りであり、AdGuard 独自のビルド都合や前処理結果を含む可能性がある
- Safari Content Blocker 向け変換では、AdGuard 向けの配布最適化よりも、生のルールを自前方針で選別できることの方が重要

### `FiltersRegistry` の扱い

`FiltersRegistry` は主入力ではなく、補助用途に留める。

用途:

- `JapaneseFilter` の配布結果が 1 ファイルに束ねられた形の確認
- 件数比較やスモークテスト時の参照
- 将来的に AdGuard 側の配布結果との差分確認を行うための参照

---

## リポジトリの役割整理

### `AdguardTeam/AdguardFilters`

- AdGuard の各フィルター群のソース置き場
- ルールはテキストベースで管理される
- `JapaneseFilter` は `sections/` 配下に役割ごとに分割されている
- Safari 向け専用の中間形式ではなく、ABP 互換 + AdGuard 独自拡張を含むルールソースである

### `AdguardTeam/FiltersRegistry`

- 既知のフィルター購読を AdGuard 向け互換性のために変換・再配布するレジストリ
- 生成済みの `filter.txt` を中心に配布用途で使われる
- フィルター単位のメタデータやビルド成果物、プラットフォーム別最適化物がある
- 入力元として使うと、AdGuard 独自のビルド事情も一緒に背負うことになる

---

## `JapaneseFilter/sections` の構造

現時点で確認できた主要ファイルは次のとおり。

| ファイル | 主な役割 | 含まれるルールの傾向 | 初期実装での扱い |
|---|---|---|---|
| `adservers.txt` | 第三者広告ドメインのブロック | `||domain^` 系のフルドメイン中心 | 採用 |
| `adservers_firstparty.txt` | 非広告サイト配下の広告用サブドメインのブロック | ドメイン・サブドメイン中心 | 採用 |
| `general_url.txt` | 汎用 URL ブロック | パス・URL パターン・一部 `$document` | 条件付き採用 |
| `general_elemhide.txt` | 汎用 cosmetic ルール | `##selector` 系の一般要素非表示 | 採用 |
| `general_extensions.txt` | AdGuard の advanced rules | 拡張 CSS、scriptlet、HTML filtering、JS | 初期実装では除外 |
| `specific.txt` | サイト個別の広告対策 | cosmetic とネットワーク系が混在 | 条件付き採用 |
| `allowlist.txt` | 誤爆修正・解除 | `@@` や例外ルール | 初期実装では保留 |
| `antiadblock.txt` | ad reinjection / anti-adblock 対策 | 回避検知、再挿入対策、解除系を含む | 初期実装では保留 |

---

## 各ファイルの詳細メモ

### `adservers.txt`

- third-party の広告ネットワーク用ドメインを置く前提
- URL 断片ではなく、完全なドメインまたはサブドメイン単位のルールが中心
- このリポジトリの `FQDN exact` 変換に最も素直に落とし込みやすい

実装上の扱い:

- `||domain^`
- `||sub.domain.example^`
- `||domain^$third-party`

上記のような単純ドメインブロックを中心に受理する。

### `adservers_firstparty.txt`

- 広告専業ドメインではないサイト群の中にある広告配信用サブドメイン向け
- `adservers.txt` と同様にドメイン単位の扱いが多い
- `third-party` に依存しない単純なドメインブロックへ落とし込みやすい

実装上の扱い:

- `adservers.txt` と同じパーサで処理する
- first-party / third-party の意味は Safari 側では保持せず、ドメインブロックとして扱う

### `general_url.txt`

- 汎用の URL ブロックルールを置く場所
- ドメインだけではなく、パス断片や URL パターンが多い
- 広告 URL だけでなく、malware / phishing の `$document` ルールも含まれる

実装上の注意:

- 単純なパターンは URL regex または部分一致ルールへ変換候補になる
- Safari の `url-filter` で安全に表現できないものはスキップする
- `|` を含む複雑な disjunction や、Safari で危険な正規表現は除外する
- リソース型オプションや AdGuard 独自オプション付きは原則スキップする

### `general_elemhide.txt`

- 汎用の要素非表示ルールを置く場所
- 基本は `##selector` のような generic cosmetic rule
- Safari 向け cosmetic 出力に比較的そのまま変換しやすい

実装上の注意:

- 単純な CSS selector を優先して採用する
- セレクタが極端に複雑な場合や、Safari 側で表現しづらいものはスキップ候補にする
- 汎用ルールなので、出力時の `domains` は空配列または未指定扱いを想定する

### `general_extensions.txt`

- advanced rules 用の置き場
- 拡張 CSS、scriptlet、HTML filtering (`$$`)、JS ルールなどが対象
- AdGuard 独自拡張に強く依存する

このリポジトリとの相性:

- 現在の `block` / `cosmetic` の 2 種類だけでは表現しきれない
- Safari Content Blocker の制約にも合わないケースが多い
- 初期実装では取り込まず、後で別系統の検討対象にするのが妥当

### `specific.txt`

- サイト個別のルール置き場
- 1 ファイルの中に複数タイプのルールが混在する
- 典型的には次のようなものが同居する

  - `domain##selector`
  - `||domain/path`
  - URL パターン系のブロック

重要な判断:

- `specific.txt` は「specific 用の専用パーサ」を作るのではなく、行ごとにルール種別判定する
- ファイル名だけを根拠に cosmetic 扱い・block 扱いへ寄せない

### `allowlist.txt`

- 誤爆や機能破壊を防ぐための解除ルール
- 例外、除外、許可の役割を持つ
- `@@` 系や、ドメイン限定の例外が中心

このリポジトリとの相性:

- 現在の出力モデルには allowlist / unblock 相当の型がない
- 単純に無視すると、本来 AdGuard 側で緩和される誤爆が残る

方針:

- 初期実装では保留
- 将来的に例外ルール用の別モデルを追加するかを検討する

### `antiadblock.txt`

- anti-adblock 対策や ad reinjection 対策向け
- 単純な広告ブロックよりも、回避スクリプト・検知スクリプト・再挿入抑止の意味合いが強い
- 例外や高度ルールが混ざりやすい

このリポジトリとの相性:

- Safari Content Blocker の単純 block/cosmetic モデルでは吸収しにくい
- `general_extensions.txt` と同様、初期実装の対象外にした方が安全

---

## 実装方針への反映

### 1. 取得単位

取得は `JapaneseFilter/sections/*.txt` を個別ファイルとして行う。

理由:

- 役割ごとにログや件数を取りやすい
- どのセクションでどれだけスキップされたか追跡しやすい
- 将来的にセクション単位で採用 / 非採用を切り替えやすい

### 2. 解析単位

解析はファイル単位ではなく行単位で行う。

理由:

- `specific.txt` のようにルール型が混在するファイルがある
- 同じセクションでも、Safari 互換のある行とない行が混ざる

### 3. 初期実装で扱う対象

まずは次を対象にする。

- `adservers.txt`
- `adservers_firstparty.txt`
- `general_url.txt`
- `general_elemhide.txt`
- `specific.txt` のうち Safari 変換可能な行

### 4. 初期実装で保留する対象

次は保留する。

- `general_extensions.txt`
- `allowlist.txt`
- `antiadblock.txt`

保留理由:

- 現行の JSON モデルに乗らない
- AdGuard 独自の意味が強い
- Safari Content Blocker での再現性が低い

---

## 実装状況

2026-04-29 時点で、このメモに基づく専用スクリプト実装を作成済み。

### 実装済みスクリプト

- `scripts/fetch_adguard_japanese_filter.py`
  - `AdguardFilters/JapaneseFilter/sections/*.txt` を直接取得する
  - 取得結果は `sources/adguard-japanese/` に保存する
  - `sources/adguard-japanese/manifest.json` に取得元 URL・行数・ハッシュを記録する
- `scripts/parse_adguard_japanese_filter.py`
  - 取得済み `sections/*.txt` を行単位で解析する
  - `dist/adguard-japanese-block-rules.json`
  - `dist/adguard-japanese-block-rules-disabled.json`
  - `dist/adguard-japanese-cosmetic-rules.json`
  - `dist/adguard-japanese-summary.json`
  を出力する

### 現在の parse 方針

- 通常出力に含める対象
  - `adservers.txt`
  - `adservers_firstparty.txt`
  - `general_elemhide.txt`
  - `general_url.txt`
  - `specific.txt` のうち変換可能な行
- 既定で出力対象から除外するセクション
  - `allowlist.txt`
  - `antiadblock.txt`
  - `general_extensions.txt`
- 広すぎる generic substring ルールのうち、`.com/Zen?` と `.jp/Zen?` は通常 block に含めず、disabled block JSON に quarantine する

### 実装済みの変換ルール

- `||domain^` / `||domain^$third-party` を FQDN exact block として出力する
- `||domain/path` を host 境界付き regex block として出力する
- 単純な `/regex/` を URL regex block として出力する
- 単純な `##selector` / `domain##selector` を cosmetic rule として出力する
- `:style(` や `:matches-media(` を含む AdGuard 独自拡張 selector は出力しない

### 2026-04-29 時点の出力結果

`dist/adguard-japanese-summary.json` の結果:

| 項目 | 件数 |
|---|---:|
| block rules | 1156 |
| disabled block rules | 2 |
| cosmetic rules | 7135 |

セクション別の要点:

| セクション | block | disabled block | cosmetic | 補足 |
|---|---:|---:|---:|---|
| `adservers.txt` | 335 | 0 | 0 | `unsupported_modifier` が 45 |
| `adservers_firstparty.txt` | 20 | 0 | 0 | 全件採用 |
| `general_elemhide.txt` | 0 | 0 | 147 | `unsupported_domain_scope` が 4 |
| `general_url.txt` | 45 | 2 | 0 | `.com/Zen?` / `.jp/Zen?` を quarantine |
| `specific.txt` | 756 | 0 | 6988 | advanced / unsupported selector / modifier を多く含む |
| `allowlist.txt` | 0 | 0 | 0 | `excluded_section` |
| `antiadblock.txt` | 0 | 0 | 0 | `excluded_section` |
| `general_extensions.txt` | 0 | 0 | 0 | `excluded_section` |

### 現時点で残っている課題

- `general_url.txt` の generic substring ルールは、`.com/Zen?` / `.jp/Zen?` 以外にも広く当たりうるものがある
- `specific.txt` に含まれる AdGuard 拡張 selector の判定は、さらに厳密化の余地がある
- allowlist / antiadblock / advanced rules を将来どう表現するかは未決定
- まだ AdGuard JapaneseFilter 専用実装であり、EasyList や uBlock 向けの汎用 fetch/parse には広げていない

---

## 変換ルールの具体的な考え方

### ブロックルールとして採用しやすいもの

- `||domain^`
- `||domain^$third-party`
- `||sub.domain.example^`
- 比較的単純な `/path/fragment`
- 単純な URL 正規表現

### cosmetic ルールとして採用しやすいもの

- `##selector`
- `domain##selector`

### 初期実装でスキップすべきもの

- `#?#`
- `#%#`
- `#$#`
- `$$`
- scriptlet
- JS ルール
- リソース型オプションに強く依存するネットワークルール
- denyallow などの高度オプション
- allowlist / exception ルール

---

## スクリプト設計上のメモ

### fetch 側

- セクション URL 一覧を固定で持つ
- 取得時に元ファイル名を保持する
- 保存時は `adguard-japanese/<section-name>.txt` のように整理すると追跡しやすい

### parse 側

- コメント行 (`!`) と空行を除去する
- 1 行ごとに rule kind を判定する
- 判定結果は最低でも次に分類する

  - `block_fqdn`
  - `block_url`
  - `cosmetic_generic`
  - `cosmetic_domain_specific`
  - `allowlist`
  - `advanced`
  - `unsupported`

- スキップ時は理由を集計できるようにする

### 出力側

- source 名には `adguard-japanese:<section-name>` のような情報を残す
- ID 生成シードにも元セクション名を含める
- 変換件数とスキップ件数をセクション別に出力できるようにする

---

## 現時点の推奨方針

1. `AdguardFilters/JapaneseFilter/sections/*` を一次入力にする
2. `FiltersRegistry/filter_7_Japanese/filter.txt` は参照専用にする
3. 初版では block と cosmetic へ落とせるルールだけを処理する
4. allowlist / antiadblock / advanced rules は後続フェーズに分離する
5. パーサはセクション依存ではなく、最終的に行ベースの判定へ寄せる
6. 広すぎる generic substring ルールは通常出力に入れず、必要なら quarantine 出力で保留する

---

## 参考 URL

### AdGuard 側リポジトリ

- https://github.com/AdguardTeam/AdguardFilters
- https://github.com/AdguardTeam/AdguardFilters/tree/master/JapaneseFilter
- https://github.com/AdguardTeam/AdguardFilters/tree/master/JapaneseFilter/sections
- https://github.com/AdguardTeam/FiltersRegistry
- https://github.com/AdguardTeam/FiltersRegistry/tree/master/filters/filter_7_Japanese

### `JapaneseFilter/sections`

- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/adservers.txt
- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/adservers_firstparty.txt
- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/allowlist.txt
- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/antiadblock.txt
- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/general_elemhide.txt
- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/general_extensions.txt
- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/general_url.txt
- https://github.com/AdguardTeam/AdguardFilters/blob/master/JapaneseFilter/sections/specific.txt

### 参考メモ

- AdGuard の文法は ABP 互換をベースにしつつ、AdGuard 独自拡張を含む
- Safari Content Blocker で再現できるのはその一部に限られる
- そのため、このリポジトリでは「元フィルターを丸ごと再現する」のではなく、「Safari で安全に変換できる部分だけを抽出する」前提で設計する
