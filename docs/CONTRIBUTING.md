# Contributing to NEXUS

First off, thank you for considering contributing to NEXUS! 🎉

It's people like you who make NEXUS the amazing platform it's becoming. We welcome contributions from developers of all skill levels.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)
- [Testing Guidelines](#testing-guidelines)

---

## 📜 Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

**TL;DR**: Be respectful, professional, and inclusive. We're all here to build something amazing together.

---

## 🤝 How Can I Contribute?

### 🐛 Reporting Bugs

Before creating a bug report:
- **Check existing issues** to avoid duplicates
- **Use the latest version** from the `nexus-clean` branch
- **Test in a clean environment** to rule out local issues

**Good Bug Report Template:**

```markdown
**Description**: Brief description of the bug

**Steps to Reproduce**:
1. Launch NEXUS
2. Go to '...'
3. Click on '...'
4. See error

**Expected Behavior**: What should happen

**Actual Behavior**: What actually happens

**Environment**:
- OS: Windows 11 / Ubuntu 22.04 / macOS 14
- Python Version: 3.10.5
- NEXUS Version: Beta 2.0
- Hardware: Arduino Uno, 8K Camera (if applicable)

**Error Messages/Logs**:
```
Paste error messages here
```

**Screenshots**: (if applicable)
```

### 💡 Suggesting Features

We love new ideas! Before suggesting:
- **Check the roadmap** in [NEXUS_BUSINESS_PLAN.md](NEXUS_BUSINESS_PLAN.md)
- **Search existing feature requests**
- **Consider the scope**: Does it align with NEXUS vision?

**Feature Request Template:**

```markdown
**Feature Name**: Clear, concise name

**Problem Statement**: What problem does this solve?

**Proposed Solution**: How should it work?

**Alternatives Considered**: Other approaches you've thought about

**Additional Context**: Screenshots, mockups, examples
```

### 🔧 Contributing Code

Areas where we need help:
- 🎨 **UI/UX Improvements**: Make NEXUS more beautiful
- 🤖 **AI Enhancements**: Improve deck building algorithms
- 🔌 **Hardware Support**: Add more camera/scanner types
- 🌐 **API Development**: Expand REST API features
- 📊 **Analytics**: New business intelligence features
- 🌍 **Internationalization**: Translate to other languages
- 📚 **Documentation**: Guides, tutorials, examples

---

## 🛠️ Development Setup

### 1. Fork & Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/NEXUS.git
cd "NEXUS/PYTHON SOURCE FILES"
```

### 2. Create Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-number-description
```

### 5. Make Changes

Edit code, test thoroughly, commit with meaningful messages.

---

## 💻 Coding Standards

### Python Style Guide

We follow **PEP 8** with some flexibility:

```python
# Good ✅
def calculate_deck_score(deck_cards: list, meta_data: dict) -> float:
    """
    Calculate deck competitiveness score.
    
    Args:
        deck_cards: List of card dictionaries
        meta_data: Current meta information
        
    Returns:
        float: Score from 0-100
    """
    total_score = 0.0
    for card in deck_cards:
        total_score += card.get('power_level', 0)
    return total_score / len(deck_cards)


# Bad ❌
def calcScore(d,m):
    s=0
    for c in d:
        s+=c['power_level']
    return s/len(d)
```

### Key Principles

1. **Descriptive Names**: `calculate_mana_curve()` not `calc_mc()`
2. **Type Hints**: Use them for function parameters and returns
3. **Docstrings**: All public functions need documentation
4. **Comments**: Explain WHY, not WHAT
5. **Error Handling**: Use try/except with specific exceptions
6. **Constants**: UPPER_CASE for constants
7. **Line Length**: Aim for 80-100 chars (flexible to 120)

### File Organization

```python
#!/usr/bin/env python3
"""
Module Description: Brief summary of what this module does

Author: Your Name
Date: YYYY-MM-DD
"""

# Standard library imports
import os
import sys
from typing import List, Dict

# Third-party imports
import numpy as np
import requests

# Local imports
from modules.scrapers import scryfall_scraper
from config.config_manager import get_config

# Constants
DEFAULT_TIMEOUT = 30
API_BASE_URL = "https://api.scryfall.com"

# Classes and functions below
```

### GUI Code

```python
# Use descriptive names for widgets
self.deck_builder_frame = tk.Frame(parent, bg='#0d0d0d')
self.card_search_entry = tk.Entry(self.deck_builder_frame)
self.add_card_button = tk.Button(self.deck_builder_frame, 
                                   text="Add Card",
                                   command=self.handle_add_card)

# Not
self.f1 = tk.Frame(parent)
self.e = tk.Entry(self.f1)
self.b = tk.Button(self.f1, text="Add", command=self.hac)
```

---

## 🔄 Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Comments added for complex logic
- [ ] Self-review completed
- [ ] Tested on your machine
- [ ] No console errors or warnings
- [ ] Documentation updated (if needed)
- [ ] Commit messages are clear

### PR Title Format

```
[Type] Brief description

Examples:
[Feature] Add Commander deck archetype analyzer
[Bugfix] Fix card image loading issue #123
[Docs] Update installation guide for Linux
[Refactor] Optimize deck building algorithm
[UI] Improve dark theme contrast
```

### PR Description Template

```markdown
## Description
Brief summary of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## How Has This Been Tested?
Describe testing process

## Screenshots (if applicable)
Add screenshots here

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have tested this on my local machine
```

### Review Process

1. **Automated Checks**: (Future: CI/CD will run tests)
2. **Code Review**: Maintainers will review your code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, we'll merge!
5. **Celebration**: You're now a NEXUS contributor! 🎉

---

## 📁 Project Structure

Understanding the codebase:

```
NEXUS/
├── nexus.py                    # Main application - start here
├── nexus_library_system.py     # Card database management
├── nexus_scanner_module.py     # Hardware integration
├── nexus_server_api.py         # REST API
│
├── modules/
│   ├── scanner/                # All scanning-related code
│   │   ├── simple_camera_scanner.py
│   │   └── ai_card_recognition_v2.py
│   │
│   ├── scrapers/               # Data fetching
│   │   ├── scryfall_scraper.py  # Scryfall API wrapper
│   │   └── tcgplayer_scraper.py # TCGPlayer scraping
│   │
│   ├── deck_builder/           # Deck construction
│   │   └── commander_deck_builder_numpy.py
│   │
│   ├── analytics/              # Business intelligence
│   │   └── customer_analytics.py
│   │
│   └── marketplace/            # Trading features
│       └── nexus_marketplace.py
│
├── config/
│   └── config_manager.py       # Configuration system
│
├── data/                       # Data files (gitignored)
├── Auto_Backups/              # Automatic backups (gitignored)
├── Generated Decks/           # Deck output (gitignored)
└── docs/                      # Documentation
```

### Key Files to Know

- **nexus.py**: Main GUI application (10,010 lines)
- **nexus_library_system.py**: Core collection/database logic
- **scryfall_scraper.py**: All card data fetching
- **commander_deck_builder_numpy.py**: Deck building algorithms

---

## 🧪 Testing Guidelines

### Manual Testing

Before submitting a PR, test these core flows:

1. **Startup**: Does NEXUS launch without errors?
2. **Library**: Can you browse your collection?
3. **Deck Builder**: Can you build a deck?
4. **Scanner**: Does hardware detection work? (if you have hardware)
5. **Settings**: Do configuration changes persist?

### Writing Tests (Future)

We're working on a test suite. Future contributions should include:

```python
# Example test structure
def test_deck_legality_checker():
    """Test that Commander deck validation works"""
    deck = create_test_deck()
    result = validate_commander_deck(deck)
    assert result['is_legal'] == True
    assert result['commander_count'] == 1
    assert result['deck_size'] == 100
```

---

## 🎯 Good First Issues

Look for issues tagged with:
- `good first issue`: Perfect for newcomers
- `help wanted`: We need assistance here
- `documentation`: Improve docs
- `ui/ux`: Design improvements

---

## 💬 Questions?

- **GitHub Discussions**: Ask questions, share ideas
- **Issues**: For bugs and feature requests
- **Code Comments**: Read inline comments for context

---

## 🏆 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Acknowledged in release notes
- Part of building a $248B platform!

---

## 📚 Additional Resources

- [Python PEP 8 Style Guide](https://www.python.org/dev/peps/pep-0008/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [How to Write Good Git Commits](https://chris.beams.io/posts/git-commit/)
- [Magic: The Gathering Comprehensive Rules](https://magic.wizards.com/en/rules)

---

## 🙏 Thank You

Every contribution, no matter how small, helps make NEXUS better. Whether you're fixing a typo, adding a feature, or improving documentation—you're building the future of collectibles management.

**Let's build something amazing together!** 🚀

---

<p align="center">
  <strong>Happy Coding!</strong><br>
  <sub>The NEXUS Team</sub>
</p>
