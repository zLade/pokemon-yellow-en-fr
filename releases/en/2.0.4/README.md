# Pokémon Yellow NJ046 — English Fidelity 2.0.4

- Quick Attack goes first when only one combatant chooses it. When both choose
  Quick Attack, the game's regular Speed comparison determines the order.
- The player's Ditto can use Transform to copy its opponent's appearance and
  moves, with 5 temporary PP per copied move. Ditto keeps its own stats and
  recovers its original moves when it switches out or the battle ends.

The 332 changed bytes relative to 2.0.3 are all in PRG bank 4.

## Apply the patch

1. Start with the original Chinese ROM **Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes**.
   It is 2,097,168 bytes with SHA-256 `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed`.
2. Apply `Pokemon_Yellow_NJ046_EN_v2.0.4.ips` to a copy with an IPS patcher.
3. Check the resulting ROM's SHA-256 `5b1f1f006f7aa0f0eb42874a90e0d4ea3b68529d2064f3145b9950d20c217a83`.

`SHA256SUMS` records the IPS checksum. Use a mapper 163 emulator such as Mesen
2.2.1. The build verifies the mapper contract, pointers, bank budgets and exact
reconstruction from the Chinese ROM.
