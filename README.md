## Candle Self-Verification

Coordination repository for work on replaying the proof of correctness of
Candle's machine-code implementation in Candle.

[The historical proof-trace baseline](docs/historical-baseline.md) pins and
builds a small HOL-to-Candle pipeline, checks the resulting theorem values in
fresh replay sessions, and records commands and artifact hashes. Current HOL
compatibility and full Candle self-verification are separate work.
