# Gale crater elevation sources

The checked-in views contain archived PDS elevations in metres. Their coordinates
are not stretched to enlarge the region. Quest scans retain a separate local
coordinate frame. Neither archive represents a live Mars camera feed.

## Expanded HiRISE view

- Credit: NASA / JPL / University of Arizona / USGS.
- Product: **DTEEC_001488_1750_001752_1750_U02**, MRO-M-HIRISE-5-DTM-V1.0.
- [Product catalog](https://www.uahirise.org/dtm/dtm.php?ID=PSP_001488_1750)
  and [primary PDS image](https://hirise-pds.lpl.arizona.edu/PDS/DTM/PSP/ORB_001400_001499/PSP_001488_1750_PSP_001752_1750/DTEEC_001488_1750_001752_1750_U02.IMG).
- The source label specifies 13,375 lines, 6,736 samples per line, an attached
  26,944-byte label record, and little-endian float32 heights.
- The display contains **129 rows × 53 columns**, beginning at zero-based native
  row **1759**, column **1473**, sampling every **77th** source row and column.
- Native spacing: **1.0117467945795 m**. Display spacing: **77.9045031826215 m**.
  Extent: **4,051.03 m east–west × 9,971.78 m north–south**, about **40.40 km²**.
- This is the approximately 10 km long valid strip available in this crop, not a
  10 × 10 km square. Every displayed height is an exact source sample. Missing
  source pixels are excluded by choosing a continuous valid rectangle; none are
  interpolated or filled. Stride sampling can alias smaller features.
- Heights reference the Mars 2000 equipotential datum. The source's equirectangular
  projection uses radius 3,396,190 m and centre longitude 137.3° E. Local x is east,
  z is south, and y is elevation. Source pixel offsets and geographic corners are
  recorded in the JSON metadata.
- Metadata records the exact byte range and SHA-256 for each sampled source row,
  plus the original label checksum. Raw source data remain outside the repository.

## Compact MOLA view

- Credit: NASA / MGS MOLA Science Team / Goddard Space Flight Center;
  NASA PDS Geosciences Node.
- Product: **MEGT00N000GB.IMG**, MEGDR version 2.0, **64 pixels per degree**.
  This is the 0–90° S, 0–180° E tile, containing Gale crater.
- [PDS image](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg064/megt00n000gb.img),
  [detached label](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg064/megt00n000gb.lbl),
  and [archive overview](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html).
- **65 × 65 exact samples** starting at zero-based row **277**, column **8755**.
  Signed big-endian int16 elevations above the product's areoid.
- Native step: **922.82 m east–west and 926.12 m north–south**, approximately 1 km.
  Extent: **59.06 × 59.27 km**. Centre: **4.8359375° S, 137.3046875° E**, enclosing
  the expanded HiRISE view.
- This replaces the former 32 pixels/degree, approximately 1.85 km grid with a
  finer native product. Cropping alone would not change source spacing.
- Coordinates use a local equirectangular approximation with radius 3,396,000 m
  and a cos(latitude) longitude correction. The label's native bin size is
  1/64 degree. No extra resampling or generated elevations are introduced.
- Grid spacing is not effective resolving power: the original MOLA product uses
  interpolated values where bins have no observations, and equatorial track gaps
  can reach 12 km. This grid is regional context, not rover navigation ground truth.

## Frozen Guardian benchmark

`data/hirise-gale-benchmark.json` preserves the previous **129 × 129**, approximately
**1.04 km** view byte-for-byte. It uses native row 6175, column 2855, stride 8 and
8.093974356636 m display spacing. Guardian training, adaptation and fixed hold-out
evaluation explicitly use this fixture. Enlarging the displayed/fleet region
does not change the published synthetic benchmark's terrain or measurements.

## Reproduction and display

`tools/update_terrain_regions.py --cache-dir <outside-repository-directory>`
recreates the expanded display fixtures from exact HTTP byte ranges.
`tools/verify_terrain.py` independently checks all **11,062 displayed elevations**
against the PDS bytes and checksums: 6,837 HiRISE and 4,225 MOLA samples.

The renderer centres and uniformly normalizes source coordinates, then applies
the visible elevation scale. Polygonal Grid adds both cell diagonals; Minimal
Grid uses axis edges. Bilinear cell centres support display geometry and do not
add measured detail. Fleet footprints, routes and warning regions are synthetic
overlays on the archive. Coarse orbital samples do not resolve wheel-scale traps.

Manrope and DM Mono are bundled under the SIL Open Font License; see
`static/fonts/Manrope-OFL.txt` and `static/fonts/DMMono-OFL.txt`. Inline Lucide
icons use the ISC license; see `static/docs/lucide-license.txt`.

UI polish practices were informed by the unslop pass by Damir Sokolovsky
(CC BY 4.0), as described in the project's reference archive.
