# NEXUS Blockchain Mint Compliance Log

## Status: MINTING HOLD ACTIVE

`MINTING_ENABLED = False` in `proof_of_presence.py`.

Do not re-enable until all items in the **Re-enable Checklist** below are verified.

---

## Pre-Compliance Development Test Mints (Tokens #1–4)

The following NFTs were minted on Polygon mainnet (contract `0x72a4e96cF2203DF1C1D4d3543397feB2a26C728E`)
during initial development and system testing, prior to the condition assessment compliance
schema being finalized. They were minted on founder Kevin Caracozza's personal cards
as functional tests of the minting pipeline.

| Token | Card | Date | TX Hash (partial) | Note |
|---|---|---|---|---|
| #1 | Lightning Bolt | 2026-02-17 | block 83111080 | First pipeline test |
| #2 | (development test) | ~2026-02-17 | — | Schema pre-compliance |
| #3 | (development test) | ~2026-02-17 | — | Schema pre-compliance |
| #4 | (development test) | ~2026-02-17 | — | Schema pre-compliance |

**Schema used at time of mint:** Included `condition_score` (numeric 1-10 overall grade),
`grade_label` (e.g. "NM"), `assessor: 'NEXUS Automated Condition Assessment'`.

**Why this is acceptable:** These tokens were minted on the founder's own personal cards
for development testing only. No commercial transactions, no shop deployments, no
third-party reliance on these records. Tokens are non-transferable in commercial context
and carry no financial representations.

**Corrective action:** Schema updated 2026-03-02. New mints will use:
- `condition_indicators` (four raw component scores, 0-100)
- No overall numeric grade
- No grade label
- `disclaimer` field embedded in all cert records

---

## Re-enable Checklist

Before setting `MINTING_ENABLED = True`:

- [ ] Verify `generate_certificate_data()` in all three grading files outputs clean schema (no `condition_score`, no `grade_label`)
- [ ] Verify `hardware_scanner.py` NFT cert metadata passes `image_sha256` and `scanner_serial` to `generate_certificate_data()`
- [ ] Verify `mint_from_scanner_result()` in `polygon_minter.py` does NOT pass NEXUS AI output as `grade_value` (only professional PSA/BGS/CGC grades)
- [ ] Confirm `market_price_cents` passed to minter comes from shop-set price, not NEXUS-generated value
- [ ] Run one test mint on Polygon Amoy testnet with new schema, verify token metadata
- [ ] Attorney review of on-chain metadata fields before mainnet resume

---

*Last updated: 2026-03-02*
