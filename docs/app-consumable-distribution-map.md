# アプリ取り込み用配布物対応表

更新日: 2026-05-01

## 目的

現在の `gh-pages` 配信構成において、iOS アプリがそのまま取り込み対象にしてよい JSON を整理する。

あわせて、公開はされてもアプリ入力としては使わない JSON について、除外理由を明記する。

---

## 配信構成

現在の配信 branch は `gh-pages` である。

- `main`: scripts / docs / workflow を管理する開発用 branch
- `gh-pages`: 配信用 JSON を持つ公開 branch

公開物は `gh-pages` branch の `dist/` 配下に置く。

したがって、アプリが参照する対象パスは次の形式になる。

```text
/dist/<filename>.json
```

## アプリが使う JSON

アプリが直接取り込む対象は、現状では次の統合 JSON である。

- `adguard-japanese.json`
- `easylist.json`
- `easyprivacy.json`
- `ublock-ads.json`
- `ublock-mobile.json`

これらは `PROJECT.md` に記載している統合スキーマを前提にしている。トップレベルは `web-block-filter-version` / `block-rules` / `cosmetic-rules` を持つ。

---

## 公開 JSON ごとの入力対応

| ソース名 | 公開 JSON パス | 入力元 | 備考 |
|---|---|---|---|
| AdGuard Japanese Filter | `/dist/adguard-japanese.json` | `JapaneseFilter/sections/adservers.txt`, `adservers_firstparty.txt`, `general_url.txt`, `general_elemhide.txt`, `specific.txt` | block と cosmetic を 1 ファイルへ統合 |
| EasyList | `/dist/easylist.json` | `https://easylist.to/easylist/easylist.txt` | 完成済み配布物を直接 parse |
| EasyPrivacy | `/dist/easyprivacy.json` | `https://easylist.to/easylist/easyprivacy.txt` | 完成済み配布物を直接 parse |
| uBlock Origin Ads | `/dist/ublock-ads.json` | `https://ublockorigin.github.io/uAssets/filters/filters.txt` | `ads` プロファイルの入力 |
| uBlock Origin Mobile effective | `/dist/ublock-mobile.json` | `https://ublockorigin.github.io/uAssets/filters/filters.txt`, `https://ublockorigin.github.io/uAssets/filters/filters-mobile.txt` | `env_mobile=true` 展開結果と mobile 差分を 1 ファイルへ統合 |

---

## 公開されてもアプリが使わない JSON と除外理由

### disabled 系

| JSON | 除外理由 |
|---|---|
| `dist/adguard-japanese-block-rules-disabled.json` | quarantine 用の無効化ルール保管先であり、アプリの通常配布物ではない |
| `dist/easylist-block-rules-disabled.json` | 現状は中身が空で、将来の quarantine 用予約出力に近い |
| `dist/easyprivacy-block-rules-disabled.json` | 現状は中身が空で、将来の quarantine 用予約出力に近い |
| `dist/ublock-ads-block-rules-disabled.json` | quarantine または無効化ルールの保管先であり、通常配布物ではない |
| `dist/ublock-mobile-block-rules-disabled.json` | quarantine または無効化ルールの保管先であり、通常配布物ではない |

`disabled` 系は、アプリに「候補として見せる配布フィルター」ではなく、変換時に危険・過剰・保留と判断した rule を退避するための補助成果物である。`gh-pages` に置かれていても、アプリの通常候補には含めない。

### summary 系

| JSON | 除外理由 |
|---|---|
| `dist/adguard-japanese-summary.json` | 変換件数・skip 理由の集計であり、ルール本体ではない |
| `dist/easylist-summary.json` | 変換件数・skip 理由の集計であり、ルール本体ではない |
| `dist/ublock-origin-summary.json` | 変換件数・skip 理由の集計であり、ルール本体ではない |

`summary` 系はデバッグ・監査・CI 確認用のメタデータであり、アプリの rule preset / cosmetic preset デコーダでは利用しない。`gh-pages` に置かれていても、アプリの通常候補には含めない。

---

## AdGuard Japanese Filter で入力に含めても出力対象外のもの

AdGuard Japanese Filter では取得しているが、既定 parse では次の section を出力対象から外している。

- `allowlist.txt`
- `antiadblock.txt`
- `general_extensions.txt`

理由:

- `allowlist.txt` は block 解除ルール中心で、現在のアプリ出力モデルに直接対応しない
- `antiadblock.txt` と `general_extensions.txt` は scriptlet / 拡張記法を多く含み、Safari Content Blocker へ安全に落としにくい

このため、上の対応表には載せていない。

---

## 運用メモ

アプリ側の配布候補一覧を作る場合は、この文書にある統合 JSON だけを候補に含める。

少なくとも現時点では、次は候補から除外すること。

- `*-block-rules-disabled.json`
- `*-summary.json`

将来アプリが「無効化候補の確認」や「変換統計の表示」を行う仕様にならない限り、これらを配布選択 UI に出す必要はない。
