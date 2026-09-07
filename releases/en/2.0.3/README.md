# Pokémon Yellow NJ046 — English Fidelity 2.0.3

Apply this patch directly to the original Chinese ROM **Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes**. No intermediate English translation is needed to play.

## Apply the patch

1. Verify the Chinese ROM: **2,097,168 bytes**, SHA-256 `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed`.
2. Apply `Pokemon_Yellow_NJ046_EN_v2.0.3.ips` to a copy using an IPS patcher.
3. Verify the result: SHA-256 `703662c3739884513bf6493b748743eff0933b2479dc21644433699891f9d0f3`.

Do not use the 2015 English translation, an already translated ROM or the Game Boy game. A filename does not establish identity. IPS does not automatically validate the source ROM.

Version 2.0.3 changes the patch application base. Its resulting ROM is byte-identical to 2.0.2, including all text, graphics, routines and the pitch correction. Mapper 163 is unchanged. This packaging change does not claim a new full playthrough or hardware test.

The builder checks exact reconstruction, 1,912 pointers, graphical labels, bank budgets, mapper headers and the IPS round trip from the Chinese ROM. `SHA256SUMS` records the patch checksum, not the source ROM checksum. No complete ROM is distributed.
