$ ============================================================
$ MAT_063 — *MAT_CRUSHABLE_FOAM
$ TODO: card layout + parameters not yet authored.
$ Reference: lsdyna/mat_063.pdf
$ Targeted use: simpler crushable foam baseline (no pressure-yield surface,
$ unlike MAT_075). Often used as the "first model to try" before moving to
$ MAT_075 / 083 / 144 for richer foam behaviour.
$
$ Required cards (per Vol II): MAT_CRUSHABLE_FOAM with LCID for stress vs strain,
$ optional rate-dependent damping, tension cutoff.
$
$ Status: SKELETON — author full card before queuing.
$ ============================================================
$ *MAT_CRUSHABLE_FOAM
$ ...
