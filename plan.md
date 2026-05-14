1) Proof tracing (Mario) .tr.gz
 ||
 \/
2.1) Conversion into .pft (Ramana)
2.2) Merging into .pft (Ramana)
 ||
 \/
3) Replayer (Daniel) in Candle

Goal:

Replay Candle's machine code soundness proof in Candle

Make this a reusable infrastructure that can replay large files.

===

How to get everyone to run stuff?

- 1) is developed on HOL trknl-master (pieces of it PRed);
      involves CakeML repo and proofs as well
- 2) is developed on HOL replay branch (stay on that branch with occasional cherry-pick)
- 3) is developed on Candle pft branch

(*) Make a git documentation/coordination repo with how to run each part from scratch

  - source of truth for this work, instructions there should be up-to-date

  - (README.md)

  - setup/install scripts and/or instructions to set things up

  - three symlinks to appropriate folders

  - shell scripts for running stuff

  - instructions for how to run each thing separately

===

1) - Dependencies from HOL + HOL examples

  1) Done?
2.1) Done?
2.2) Done?
  3) Done?

=== Milestone 1: reliably reproduce this (Daniel will do this) ===

2.1) - Everything up to basis (TextIOProof)

  1) Done?
2.1) Stuck?
2.2) -
  3) -

=== Milestone 2: Make TextIOProof work (no NoTrace) ===

2.2) - Everything up to compiler/backed/proofs

  1) Done (maybe some skipped)
2.1) ?
2.2) ?
  3) ?

=== Milestone 3: Make compiler/backend/proofs work with no/minimal NoTrace ===

=== Milestone 4: Finish hello world proof with no/minimal NoTrace ===

2.3) - Everything up to compiler/proofs

2.4) - Candle soundness proofs

=== Milestone 5: Finish all of 2) with no/minimal NoTrace ===

- Everything up to compiler/bootstrap/translation

- Everything up to Candle machine code soundness

=== Milestone 6: Done with no/minimal NoTrace ===

=== Milestone 7 (also ongoing): Remove NoTraces ===

===

TODO List

- Daniel does the work for Milestone 1 and pings Mario/Ramana

- Mario is investigating rewriting ml_progLib; can get help from others (then removing NoTrace (Export Proof))

- Ramana look at merging and Milestone 1/2 with Daniel
