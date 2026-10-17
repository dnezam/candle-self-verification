## Candle Self-Verification

Coordination repository for work on replaying the proof of correctness of
Candle's machine-code implementation in Candle.

[Historical pipeline preparation](docs/historical-baseline.md) pins the producer,
converter, reader and bootstrap sources and provides a checked preparation
command. **The end-to-end replay baseline is not yet reproduced:** the pinned
HOL build is blocked by holbuild's historical-version support. Preparation does
not claim any replayed theorem or compatibility with current HOL projects.
