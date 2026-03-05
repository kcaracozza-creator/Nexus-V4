# NEXUS - Zero-Sort MTG Library System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Revolutionary card cataloging system for Magic: The Gathering collections.**

No more sorting alphabetically. No more organizing by set. Just drop cards in boxes sequentially and let NEXUS find everything instantly.

##  What is NEXUS?

NEXUS is a library catalog system for MTG cards. Instead of manually sorting thousands of cards:
- Drop cards into boxes in any order
- Each card gets a call number (AA-0001, AA-0002, etc.)
- Search finds any card across hundreds of boxes instantly
- Master database provides pricing, Oracle text, legality, and more

**Current Status:** Beta - 5 game shops testing

##  Features

- **Zero-Sort System**: No alphabetizing, no set grouping required
- **Scryfall Integration**: Accurate pricing per printing (Forest [EOE] $0.05 vs Forest [MC3] $2.00)
- **Bulk Import**: Import entire collections from Gestix/Deckbox/Archidekt
- **Collection Manager**: Group and browse by unique printings
- **Fast Search**: Find cards across 100,000+ cards in milliseconds
- **Box Management**: Automatic box transitions at 1000-card capacity

##  Quick Start

### For Developers

```powershell
# Clone repository
git clone https://github.com/kcaracozza-creator/mTG-SCANNER.git
cd mTG-SCANNER

# Set up virtual environment
python -m venv venv
venv\Scripts\activate  # On Mac/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run NEXUS
python nexus.py
```

See [NEXUS_PROJECT_OVERVIEW.md](NEXUS_PROJECT_OVERVIEW.md) for complete technical documentation.

##  Documentation

- **[NEXUS_PROJECT_OVERVIEW.md](NEXUS_PROJECT_OVERVIEW.md)** - Complete technical reference
- **[LETTER_TO_MENDEL.md](LETTER_TO_MENDEL.md)** - Onboarding guide for new developers  
- **[GITHUB_SETUP.md](GITHUB_SETUP.md)** - Repository setup instructions

##  Architecture

```

         nexus.py (GUI Layer)            
  - PyQt5 interface                       
  - Collection Manager, Search, Deck      

               

  nexus_library_system.py (Core Engine)   
  - Card cataloging                        
  - Database management                    
  - Scryfall enrichment                    

               

      nexus_library.json (Storage)        
  - JSON-based card database               
  - 1000 cards per box (AA-ZZ)            

```

##  Tech Stack

- **Language**: Python 3.8+
- **GUI**: PyQt5
- **Database**: JSON (simple, portable)
- **API**: Scryfall (card data enrichment)
- **Master DB**: 106,804 cards from MTGJSON

##  Current Stats

-  26,850 cards cataloged
-  27 boxes (AA through BA)
-  Scryfall ID grouping operational
-  Clean cataloging (no numbered suffixes)
-  Production polish in progress

##  Key Concept: Scryfall ID as The Bible

Card names are ambiguous - **Forest** has hundreds of printings with vastly different prices. NEXUS groups by **Scryfall ID** (unique per printing) to ensure:
- Accurate pricing per printing
- Proper inventory separation
- No mixing of $0.05 and $2.00 cards

When you search forest, you'll see ALL printings across all boxes, but each printing appears as a separate row with individual pricing.

##  Contributing

This project is currently in beta. Contributions welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

##  License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

##  Acknowledgments

- [Scryfall](https://scryfall.com/) for their amazing API
- [MTGJSON](https://mtgjson.com/) for comprehensive card database
- The MTG community for inspiration

##  Support

- **Issues**: [GitHub Issues](https://github.com/kcaracozza-creator/mTG-SCANNER/issues)
- **Discussions**: [GitHub Discussions](https://github.com/kcaracozza-creator/mTG-SCANNER/discussions)

---

**Remember:** The Scryfall ID is the Bible. 

*Built with  for game shops who deserve better inventory management.*
