# EasyList 配布フィルター調査メモ

調査日: 2026-04-29

## 目的

`EasyList` 系フィルターのうち、このリポジトリでまず取り込みたい次の 2 つについて、実際の配布元 URL と自動取得元としての妥当性を確認する。

- `https://easylist.to/easylist/easylist.txt`
- `https://easylist.to/easylist/easyprivacy.txt`

確認したい論点は次の 2 点。

- 上記 URL は公式な配布物か
- 自動化の一次取得元として `easylist.to` を採用してよいか

---

## 結論

### `easylist.txt`

`https://easylist.to/easylist/easylist.txt` は、EasyList の公式配布物として扱ってよい。

判断理由:

- EasyList の公式サイトは `https://easylist.to/`
- `easylist.txt` 自身のヘッダーに `Homepage: https://easylist.to/`、`Licence: https://easylist.to/pages/licence.html`、`GitHub issues: https://github.com/easylist/easylist/issues` が入っている
- ファイル内に `Commit:` が埋め込まれており、配布物が GitHub 上の `easylist/easylist` リポジトリと連動して生成されていることが分かる

### `easyprivacy.txt`

`https://easylist.to/easylist/easyprivacy.txt` も、EasyList プロジェクト配下の公式配布物として扱ってよい。

判断理由:

- EasyList サイトとライセンス表記は EasyList / EasyPrivacy を含むリポジトリ全体を `https://github.com/easylist` と結び付けている
- GitHub 上の `easylist/easylist` リポジトリには `easyprivacy.template` と `easyprivacy/` 配下のソースがあり、EasyPrivacy が同じ配布パイプラインで生成されていることを確認できる
- 実運用上も `easyprivacy.txt` は一般的に EasyPrivacy の購読 URL として参照されている

### このリポジトリでの採用方針

一次取得元としては、次の 2 本をそのまま使うのが妥当。

```text
https://easylist.to/easylist/easylist.txt
https://easylist.to/easylist/easyprivacy.txt
```

補足:

- GitHub リポジトリは「ソース断片・テンプレート・生成元の監査先」として使う
- 実際の自動取得は、最終配布形になっている `easylist.to/easylist/*.txt` を使う
- `uBO` のように `include` 展開の前処理は不要で、`fetch -> parse` の 2 段で扱える

---

## 確認結果の整理

### `easylist.to` 側

確認できた内容:

- `easylist.txt` は ABP 形式の完成済み配布ファイルとして公開されている
- ヘッダーに `Version` / `Last modified` / `Expires` / `Commit` が含まれる
- `Homepage` / `Licence` / `GitHub issues` / `GitHub pull requests` が EasyList の公式導線として記載されている

このため、`easylist.to` は単なる紹介ページではなく、完成済み購読ファイルの正式な配布面として見てよい。

### GitHub `easylist/easylist` 側

確認できた内容:

- `easylist.template`
- `easyprivacy.template`
- `template_header.txt`
- `easylist/` 配下のセクションファイル群
- `easyprivacy/` 配下のセクションファイル群

つまり GitHub 側は最終配布テキストそのものではなく、配布物を構成するソース群を持つ一次開発リポジトリである。

この構造から、実装上の扱いは次のように分けるのが自然。

- 配布取得先: `easylist.to/easylist/*.txt`
- 出自確認先: `github.com/easylist/easylist`

---

## 実装設計

### なぜ `easylist.to` を直接取るのか

GitHub リポジトリを直接つぎはぎして最終ファイルを再構築することも不可能ではないが、このリポジトリの目的から見ると利点が薄い。

理由:

- 取り込みたいのは「利用者が実際に購読する完成済み配布物」
- `easylist.to` 版には更新時刻・期限・コミット情報が埋め込まれている
- `include` やテンプレート結合の再実装をこちらで持つ必要がない

したがって、初期実装は `fetch -> parse` の単純構成で十分。

### 取得対象

初期実装では次の 2 リストだけを扱う。

- `easylist`
- `easyprivacy`

出力先はリストごとに分ける。

- `dist/easylist-block-rules.json`
- `dist/easylist-block-rules-disabled.json`
- `dist/easylist-cosmetic-rules.json`
- `dist/easyprivacy-block-rules.json`
- `dist/easyprivacy-block-rules-disabled.json`
- `dist/easyprivacy-cosmetic-rules.json`
- `dist/easylist-summary.json`

### JSON 変換ルール

初期実装では既存の AdGuard / uBO と同様、安全側に寄せて次だけを受理する。

- `||domain^`
- `||domain/path`
- `/regex/` のうち `|` を含まないもの
- 単純な literal / `*` ベースの URL パターン
- `##selector`
- `domain##selector`

スキップ対象:

- `@@` allowlist
- `#?#` / `#$#` / `#%#`
- `+js(` / `scriptlet(`
- `domain=` やリソース種別などの複雑な modifier
- Safari Content Blocker に直接落としにくい拡張 selector

---

## 補足

EasyList / EasyPrivacy はルール数が多く、Safari 向けにそのままフル変換できるわけではない。したがって「どこから取るか」と「何を Safari 向けに採用するか」は分けて考える必要がある。

今回の調査対象は前者であり、取得元としては `easylist.to/easylist/easylist.txt` と `easylist.to/easylist/easyprivacy.txt` を採用して問題ない、という整理でよい。
