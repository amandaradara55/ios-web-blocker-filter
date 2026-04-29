# ios-web-blocker-filter

Prebuilt Safari Content Blocker rule presets for the `iOS-web-blocker` app.

This repository fetches public filter lists, converts the supported subset of their rules into the app's JSON formats, and publishes the generated artifacts under `dist/`.

## What This Repository Contains

- Conversion scripts for each supported upstream filter source
- Generated `dist/*.json` files intended for app consumption
- Research notes documenting why each upstream distribution URL was selected

The app-consumable outputs are documented in `docs/app-consumable-distribution-map.md`.

## Upstream Sources

This project currently consumes data from the following official upstream distributions:

- AdGuard Japanese Filter
  - Upstream project: `AdguardTeam/AdguardFilters`
  - Distribution path used here: `JapaneseFilter/sections/*.txt`
  - Primary project page: <https://github.com/AdguardTeam/AdguardFilters>

- EasyList
  - Official homepage: <https://easylist.to/>
  - Distribution URL used here: <https://easylist.to/easylist/easylist.txt>
  - Source repository: <https://github.com/easylist/easylist>

- EasyPrivacy
  - Official homepage: <https://easylist.to/>
  - Distribution URL used here: <https://easylist.to/easylist/easyprivacy.txt>
  - Source repository: <https://github.com/easylist/easylist>

- uBlock Origin filter assets
  - Upstream project: `uBlockOrigin/uAssets`
  - Distribution URLs used here:
    - <https://ublockorigin.github.io/uAssets/filters/filters.txt>
    - <https://ublockorigin.github.io/uAssets/filters/filters-mobile.txt>
  - Primary project page: <https://github.com/uBlockOrigin/uAssets>

## Licensing and Attribution

This repository contains code written for this project as well as generated JSON derived from third-party filter lists.

Please review the upstream licenses before redistributing either the original lists or derivative outputs.

- AdGuard Filters
  - The official `AdguardTeam/AdguardFilters` repository is published under GNU GPL v3.0.
  - Source: <https://github.com/AdguardTeam/AdguardFilters/blob/master/LICENSE>

- EasyList / EasyPrivacy
  - The EasyList repository states that its contents are dual-licensed under GNU GPL v3.0-or-later and CC BY-SA 3.0-or-later, unless otherwise noted.
  - The EasyList project also requests attribution to "The EasyList authors" when required.
  - Source: <https://easylist.to/pages/licence.html>

- uBlock Origin uAssets
  - The official `uBlockOrigin/uAssets` repository is published under GNU GPL v3.0.
  - Source: <https://github.com/uBlockOrigin/uAssets/blob/master/LICENSE>

This project does not claim ownership of the upstream filter rules. Credit for those rules belongs to their respective maintainers and contributors.

## Acknowledgements

Thanks to the maintainers and contributors of:

- AdGuard Filters
- EasyList
- EasyPrivacy
- uBlock Origin / uAssets

Their work makes this project possible.

## Notes for Repository Maintenance

- `dist/` contains generated outputs intended for app delivery.
- `sources/` is kept in git only as a placeholder directory skeleton.
- Upstream raw files are treated as fetch-time intermediates, not as long-term tracked repository payload.
- If intermediate fetch outputs are regenerated locally, they should stay untracked and disposable.
