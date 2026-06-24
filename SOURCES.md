# Source Inventory

Ranked by usefulness for expanding `data/clean/baby_names_master.csv`.

| Rank | Source | Coverage | Usefulness | Notes |
| --- | --- | --- | --- | --- |
| 1 | BabyCenter Australia top baby names pages | Australia 2008-2025 | Best app source | Imported 100 girls and 100 boys per year using `scripts/fetch_babycenter.py`. Rank-only, no birth counts. |
| 2 | Guardian Australia compiled baby-name article | Australia, state/territory records, historical coverage into the 1940s | Broadest locator found | States there is no national dataset; most jurisdictions publish top-100 lists; counts are incomplete for some states/years. |
| 3 | State/territory registry government statistics links | QLD, ACT, NT, SA, VIC, WA | Highest authority | Several current links are archived or page/table based. Best next step is extracting archived government tables into raw CSV files. |
| 4 | Queensland 2023 registry release via Guardian | QLD 2023 | Counts for rank 1, top names | Includes distinct-name counts and birth totals. |
| 5 | Victoria 2023 registry release via Guardian | VIC 2023 | Counts for rank 1, top-five/top-100 notes | Useful for rank rows and top-100 coverage notes. |
| 6 | NSW 2023 registry release via news.com.au/Daily Telegraph | NSW 2023 | Top 10/top-100 notes | Count data not available in the found page. |
| 7 | Queensland 2024 registry release via Courier-Mail | QLD 2024 | Top 10, counts for rank 1 | Useful recent update. |
| 8 | Northern Territory 2025 Attorney-General data via Courier-Mail | NT 2025 | Multiple exact counts | Small dataset but strong count quality. |
| 9 | 7News/McCrindle Australia 2024 national report | Australia 2024 | National ranks | Rank-only national reference; kept separate from calculated Australia totals. |
| 10 | News.com.au/McCrindle Australia 2025 national report | Australia 2025 | National ranks | Top 10 boys and girls imported as the primary 2025 national ranking source. BabyCenter fills after the published top 10. |

Important rule used in the cleaned data: absence from a published top list is marked as unavailable. It is never treated as zero births.
