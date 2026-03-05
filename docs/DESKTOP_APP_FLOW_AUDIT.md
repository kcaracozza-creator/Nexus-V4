# NEXUS Desktop App V2 — Process Flow Audit
## Every API Call: Where It Starts, Where It Ends

**Date:** February 15, 2026  
**Audited by:** Claude (Mendel mode)  
**Architecture Reference:** BROK=Brain, SNARF=Body, Desktop=Face, ZULTAN=Hub

### Hardware IPs Verified:
| Machine | IP | Port | Service Running |
|---------|-----|------|-----------------|
| SNARF | 192.168.1.172 | 5001 | Camera, arm, lights, ESP32 |
| SNARF | 192.168.1.172 | 5002 | Vision stream service |
| BROK | 192.168.1.174 | 5000 | Scanner, OCR, review queue, library |
| ZULTAN | 192.168.1.152 | 5000 | Marketplace (server.py) |
| ZULTAN | 192.168.1.152 | 8000 | Card catalog API (nexus_unified_api.py) |
| ESP32 | 192.168.1.218 | — | Lightbox/stepper bridge |

---

## SUMMARY: ISSUES BY SEVERITY

### ❌ CRITICAL (Broken)
1. ai_training.py → all 6 endpoints hit marketplace:5000 instead of training agent (no agent exists)
2. deck_builder.py → BrockLibraryClient calls /api/library/* on BROK which 404s (not deployed)

### ⚠️ HIGH (Working Wrong)
3. collection.py + hardware_scanner.py sync reads in-memory ReviewQueue (500 cap, lost on reboot)
4. live_view.py captures go direct to SNARF — BROK never tracks them

### ⚠️ MEDIUM
5. scanner_modes.py checks SNARF /health, all other tabs check /status — inconsistent

### ✅ CORRECT: hardware_controls, marketplace, ai_learning, settings, system_control, config system
