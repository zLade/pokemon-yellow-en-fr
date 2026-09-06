# Pokémon Yellow NJ046 — English Fidelity 2.0.2

Current English release. This directory distributes the IPS patch only; no complete ROM is tracked by Git.

Version 2.0.2 retains the complete certified 2.0.1 localization and adds the corrected NES pitch table.

Apply `Pokemon_Yellow_NJ046_EN_v2.0.2.ips` to a clean copy of `yellow.nes`:

- size: `2,097,168` bytes;
- SHA-256: `69520103102677b33b47c15fae804dc1a742347a9ee1b02a9195e795eb6e431b`;
- mapper: iNES mapper 163.

Resulting ROM: SHA-256 `703662c3739884513bf6493b748743eff0933b2479dc21644433699891f9d0f3`.

Validation: two independent IPS round trips, changes confined to the expected 69 pitch-table bytes, 1,912/1,912 pointers, preserved mapper-163 contract and a passing Mesen 2.2.1 Dendy boot probe.
