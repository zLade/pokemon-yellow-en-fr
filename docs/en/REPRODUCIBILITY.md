# Reproducibility

## Publicly tracked checks

GitHub Actions can validate the language boundary, absence of iNES payloads,
release checksums, catalogue cardinalities, English codec/layout rules and
ROM-free unit tests. These checks require Python only; the tooling uses the
standard library for this path.

## Local build and runtime checks

A complete build additionally requires locally supplied input ROMs matching
`data/source-inputs.sha256`, plus the runtime evidence described in
`BUILD_AND_RELEASE.md`. Mesen tests run through PowerShell and must be bound to
the candidate ROM SHA rather than inherited proof from another build.

The release gate must establish:

- two byte-identical independent builds;
- all IPS/BPS routes reconstructing one target;
- mapper 163 and pointer-manifest validation;
- English catalogue, codec, layout, bank-budget and glyph-residue gates;
- credited `YELLOW VERSION` title validation in Mesen;
- French golden non-regression for shared tooling.

The final English target is not tracked. Its expected SHA-256 is
`703662c3739884513bf6493b748743eff0933b2479dc21644433699891f9d0f3`.

## Claims deliberately excluded

The current evidence does not establish a complete human playthrough, natural
visitation of every dialogue branch, harmlessness of all inherited
uninitialized-RAM behavior, or operation on physical mapper-163 hardware.
