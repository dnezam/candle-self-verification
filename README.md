## Candle Self-Verification

Coordination repository for work on replaying the proof of correctness of
Candle's machine-code implementation in Candle.

[The historical proof-trace baseline](docs/historical-baseline.md) pins and
builds a small HOL-to-Candle pipeline, checks the resulting theorem values in
fresh replay sessions, and records commands and artifact hashes.

[The current PFT integration](docs/current-pft.md) checks a pinned current HOL
producer through both HOL and Candle readers, with separate and merged proof
traces. Both harnesses use the same pinned Poly/ML runtime; the historical HOL
and Candle revisions stay fixed. Full Candle self-verification remains separate
work.
