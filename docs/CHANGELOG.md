# Changelog

All notable changes to NEXUS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🚀 Coming Soon
- Mobile app (iOS/Android) integration
- Consumer handheld scanner hardware
- Marketplace platform beta
- Multi-language support (Spanish, French, Japanese)
- Advanced AI deck optimization v2.0

---

## [2.0.0] - 2025-11-26

### 🎉 Major Release - NEXUS Platform

This release represents a complete rebrand and architectural overhaul from the legacy MTTGG system to the modern NEXUS platform.

### ✨ Added
- **Professional Documentation Suite**
  - Comprehensive README.md with project vision
  - CONTRIBUTING.md with developer guidelines
  - CODE_OF_CONDUCT.md for community standards
  - Technical ARCHITECTURE.md documentation
  - GitHub issue templates (bug reports, feature requests)
  - MIT LICENSE with NEXUS-specific terms
  
- **Unified Application (nexus.py)**
  - Consolidated 10,010 lines of production code
  - Modern dark theme UI
  - Tabbed interface for all major features
  - Real-time status indicators
  
- **AI-Powered Deck Building**
  - Support for all major formats (Standard, Modern, Commander, Legacy, Vintage, Pioneer)
  - NumPy-optimized scoring algorithms
  - Mana curve optimization
  - Synergy detection system
  - Budget constraints
  - Meta-aware recommendations
  
- **Network Scanner Support**
  - Raspberry Pi remote scanner integration
  - Android mobile scanner support
  - Multi-device scanning coordination
  - Real-time scan result synchronization
  
- **Hardware Integration**
  - 8K Camera system support (upgraded from DSLR)
  - Arduino Uno R3 firmware v4.0
  - 24 RGB NeoPixel LED control
  - Dual motor control system
  - IR sensor integration
  
- **Business Intelligence**
  - Customer analytics dashboard
  - Sales tracking and reporting
  - Inventory turnover metrics
  - Profit margin analysis
  - Market intelligence integration
  
- **Cloud & API Features**
  - REST API server (nexus_server_api.py)
  - Cloud synchronization (nexus_cloud_sync.py)
  - Remote access capabilities
  - API authentication

### 🔄 Changed
- **Brand Identity**: Rebranded from MTTGG to NEXUS
- **Architecture**: Modular design with clear separation of concerns
- **Configuration**: New portable config system (config_manager.py)
- **Database**: Enhanced SQLite schema for collections and decks
- **Scryfall Integration**: Improved caching and rate limiting
- **UI/UX**: Modernized interface with consistent styling

### 🐛 Fixed
- Unicode handling in card names with special characters
- Camera initialization race conditions
- Deck builder memory leaks with large collections
- Arduino serial communication timeouts
- Image caching inconsistencies
- Format legality checker edge cases

### 🗑️ Removed
- Legacy MTTGG system files (11 files)
- Old mtg_core versions (3 files)
- 141+ Python cache files
- 35+ one-time fix scripts
- 41 obsolete test files
- 8 quick diagnostic scripts
- All backup files from development

### 📦 Dependencies
- Python 3.10+ (required)
- tkinter 8.6+ (GUI framework)
- Pillow 10.0.0+ (image processing)
- OpenCV 4.8.0+ (camera support)
- NumPy 1.24.0+ (performance optimization)
- Requests 2.31.0+ (API integration)
- PySerial 3.5+ (Arduino communication)

### 🔒 Security
- API keys now stored in .env files (not committed)
- User data remains local-first
- No cloud storage without explicit opt-in
- Hardware safety limits in firmware

---

## [1.5.0] - 2025-11-20

### Legacy MTTGG System (Deprecated)

### Added
- Basic scanner functionality
- Initial deck builder
- Simple collection tracking

### Changed
- Multiple system files consolidated

---

## [1.0.0] - 2025-10-15

### Initial Release

### Added
- Basic MTG collection management
- Manual card entry
- CSV import/export
- Simple deck lists

---

## Version History Summary

- **2.0.0** (Current) - NEXUS Platform - Professional, production-ready
- **1.5.0** - MTTGG System - Development/Testing
- **1.0.0** - Initial prototype

---

## Migration Guide

### From MTTGG to NEXUS

If you're upgrading from the legacy MTTGG system:

1. **Backup your data**: Collections and decks are preserved
2. **Update imports**: Change `import mttgg_*` to `import nexus`
3. **Configuration**: New config system auto-migrates settings
4. **Hardware**: Arduino firmware needs update to v4.0
5. **API**: New REST API endpoints (see docs/ARCHITECTURE.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/kcaracozza-creator/NEXUS/issues)
- **Discussions**: [GitHub Discussions](https://github.com/kcaracozza-creator/NEXUS/discussions)
- **Documentation**: [docs/](docs/)

---

**NEXUS** - Universal Collectibles Platform | Est. 2025
