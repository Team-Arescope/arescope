# Gale crater elevation sources

The two checked-in fixtures contain archived measurements. Quest room scans use
their own local coordinate system and are displayed in a separate overlay.

## MOLA regional grid

- Credit: NASA / MGS MOLA Science Team / Goddard Space Flight Center;
  NASA PDS Geosciences Node.
- Product: **MEGT90N000FB.IMG**, MEGDR version 2.0, 32 pixels per degree.
- [PDS product](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg032/megt90n000fb.img)
  and [detached label](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg032/megt90n000fb.lbl).
- 65 × 65 exact samples, starting at zero-based row 3020, column 4364.
  Signed big-endian int16 elevations in metres above the product's areoid.
- Approximately 118 × 119 km; east spacing 1844.04 m, south spacing 1852.23 m.
  Coordinates are a local equirectangular approximation centred on
  5.390625° S, 137.390625° E.
- Observation gaps and interpolation in the original product limit effective
  resolution. This regional grid does not resolve walking-scale obstacles.

## HiRISE local grid

- Credit: NASA / JPL / University of Arizona / USGS.
- Product: **DTEEC_001488_1750_001752_1750_U02**, MRO-M-HIRISE-5-DTM-V1.0.
- [Product catalog](https://www.uahirise.org/dtm/dtm.php?ID=PSP_001488_1750)
  and [primary PDS image](https://hirise-pds.lpl.arizona.edu/PDS/DTM/PSP/ORB_001400_001499/PSP_001488_1750_PSP_001752_1750/DTEEC_001488_1750_001752_1750_U02.IMG).
- 129 × 129 display samples from a 1025 × 1025 native crop, stride 8,
  beginning at zero-based row 6175, column 2855. Little-endian float32 heights.
- Native spacing 1.0117467945795 m; display spacing 8.093974356636 m;
  extent 1036.028717649408 m. No invented height samples, smoothing or filling.
  Stride sampling can alias fine features.
- Heights reference the source's Mars 2000 equipotential datum. Local x is east
  and z is south; y is elevation in metres.

## Provenance and display

The original LAB's public JSON fixtures were retrieved on 2026-11-14 from
[the MOLA fixture](https://arescope.mrfenek.eu.cc/static/data/mola-gale.json) and
[the HiRISE fixture](https://arescope.mrfenek.eu.cc/static/data/hirise-gale.json).
Product identifiers, crop offsets, range checksums and original coordinates are
preserved in each fixture. Obsolete simulation descriptions were removed.
`tools/verify_terrain.py` checks all 20,866 heights against byte ranges from the
primary PDS products, including the recorded raw SHA-256 hashes.

The renderer centres and uniformly normalizes the coordinates before applying
the visible elevation scale. Source data and downloads keep their original units.
Polygonal Grid adds both diagonals to each cell; Minimal Grid uses only the two
grid axes. Bilinearly interpolated cell centres keep both diagonals on the same
rendered surface; these centres add no measured detail. A filled depth pass hides
edges behind slopes. These are visualization
fixtures, not navigation products.

Manrope and DM Mono are bundled under the SIL Open Font License; see
`static/fonts/Manrope-OFL.txt` and `static/fonts/DMMono-OFL.txt`. Inline Lucide
icons use the ISC license; see `static/docs/lucide-license.txt`.

UI polish practices were informed by the unslop pass by Damir Sokolovsky
(CC BY 4.0), as described in the project's reference archive.
