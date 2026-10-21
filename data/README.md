# Authorised data placement

The source workbooks are confidential course materials and are not distributed in this repository.

Obtain authorised copies from the course, create `data/raw/`, and place these unchanged files there:

- `Mar24_part1.xlsx`
- `Mar24_part2.xlsx`
- `Traffic Accident Database 2024.xlsx`

The build processes all six March alarm sheets and the accident workbook's `Database` sheet. It creates local typed caches and aggregates under `data/processed/`, which Git ignores.

The original briefing, if needed locally, belongs under `docs/`; its PDF is also excluded from Git. Missing data is not replaced with synthetic observations or downloaded from a public source.

Never commit raw workbooks, the private driver mapping, event caches, individual predictions or fitted model files. Generated CAP identifiers are pseudonyms and do not make individual records anonymous.
