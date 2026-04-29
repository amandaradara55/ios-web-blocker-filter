# アプリ取り込み用配布物対応表

更新日: 2026-04-29

## 目的

`dist/` に生成される JSON のうち、iOS アプリがそのまま取り込み対象にしてよい配布物だけを整理する。

あわせて、`dist/` に存在していてもアプリ入力としては使わない JSON について、除外理由を明記する。

---

## アプリが使う JSON

アプリが直接取り込む対象は、現状では次の 2 系統のみ。

- `*-block-rules.json`
- `*-cosmetic-rules.json`

これらは `PROJECT.md` に記載している `BundledRulePreset.json` / `BundledCosmeticPreset.json` と同じ形式を前提にしている。

---

## 取得元 URL と結果 JSON の対応

| 取得元 URL | ソース名 | 結果 JSON | 備考 |
|---|---|---|---|
| `https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/adservers.txt` | AdGuard Japanese Filter | `dist/adguard-japanese-block-rules.json` | ドメイン・URL 系 block ルール入力 |
| `https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/adservers_firstparty.txt` | AdGuard Japanese Filter | `dist/adguard-japanese-block-rules.json` | first-party 系 block ルール入力 |
| `https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/general_url.txt` | AdGuard Japanese Filter | `dist/adguard-japanese-block-rules.json` | 一般 URL block ルール入力 |
| `https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/general_elemhide.txt` | AdGuard Japanese Filter | `dist/adguard-japanese-cosmetic-rules.json` | 一般 cosmetic ルール入力 |
| `https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/specific.txt` | AdGuard Japanese Filter | `dist/adguard-japanese-block-rules.json`, `dist/adguard-japanese-cosmetic-rules.json` | block / cosmetic の両方を含む |
| `https://easylist.to/easylist/easylist.txt` | EasyList | `dist/easylist-block-rules.json`, `dist/easylist-cosmetic-rules.json` | 完成済み配布物を直接 parse |
| `https://easylist.to/easylist/easyprivacy.txt` | EasyPrivacy | `dist/easyprivacy-block-rules.json`, `dist/easyprivacy-cosmetic-rules.json` | 完成済み配布物を直接 parse |
| `https://ublockorigin.github.io/uAssets/filters/filters.txt` | uBlock Origin Ads | `dist/ublock-ads-block-rules.json`, `dist/ublock-ads-cosmetic-rules.json` | `ads` プロファイルの入力 |
| `https://ublockorigin.github.io/uAssets/filters/filters.txt` | uBlock Origin Mobile effective | `dist/ublock-mobile-block-rules.json`, `dist/ublock-mobile-cosmetic-rules.json` | `env_mobile=true` 展開の親入力 |
| `https://ublockorigin.github.io/uAssets/filters/filters-mobile.txt` | uBlock Origin Mobile effective | `dist/ublock-mobile-block-rules.json`, `dist/ublock-mobile-cosmetic-rules.json` | mobile 差分生成に使う補助入力 |

---

## アプリが使わない JSON と除外理由

### disabled 系

| JSON | 除外理由 |
|---|---|
| `dist/adguard-japanese-block-rules-disabled.json` | quarantine 用の無効化ルール保管先であり、アプリの通常配布物ではない |
| `dist/easylist-block-rules-disabled.json` | 現状は中身が空で、将来の quarantine 用予約出力に近い |
| `dist/easyprivacy-block-rules-disabled.json` | 現状は中身が空で、将来の quarantine 用予約出力に近い |
| `dist/ublock-ads-block-rules-disabled.json` | quarantine または無効化ルールの保管先であり、通常配布物ではない |
| `dist/ublock-mobile-block-rules-disabled.json` | quarantine または無効化ルールの保管先であり、通常配布物ではない |

`disabled` 系は、アプリに「候補として見せる配布フィルター」ではなく、変換時に危険・過剰・保留と判断した rule を退避するための補助成果物である。

### summary 系

| JSON | 除外理由 |
|---|---|
| `dist/adguard-japanese-summary.json` | 変換件数・skip 理由の集計であり、ルール本体ではない |
| `dist/easylist-summary.json` | 変換件数・skip 理由の集計であり、ルール本体ではない |
| `dist/ublock-origin-summary.json` | 変換件数・skip 理由の集計であり、ルール本体ではない |

`summary` 系はデバッグ・監査・CI 確認用のメタデータであり、アプリの rule preset / cosmetic preset デコーダでは利用しない。

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

アプリ側の配布候補一覧を作る場合は、この文書にある `結果 JSON` だけを候補に含める。

少なくとも現時点では、次は候補から除外すること。

- `*-block-rules-disabled.json`
- `*-summary.json`

将来アプリが「無効化候補の確認」や「変換統計の表示」を行う仕様にならない限り、これらを配布選択 UI に出す必要はない。
