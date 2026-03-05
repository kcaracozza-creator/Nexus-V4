#!/usr/bin/env python3
"""
MTTGG AI Complete System Launcher
Launches the full system with all AI features
"""

import sys
import os

# Add source directory to path
sys.path.insert(0, r"E:\MTTGG\PYTHON SOURCE FILES")

def main():
    """Launch MTTGG with AI features"""
    print("🤖 MTTGG AI Complete System")
    print("=" * 40)
    print("🚀 Initializing AI components...")
    
    try:
        # Test AI components first
        from ai_deck_optimizer import AdvancedDeckOptimizer, AIMetaAnalyzer, InvestmentAnalyzer
        from ai_trading_bot import AITradingBot
        print("✅ AI components loaded")
        
        # Launch main system
        from mttgg_complete_system import MTTGGCompleteSystem
        print("✅ Main system loaded")
        
        print("\n🎯 Starting MTTGG AI Complete System...")
        print("Features enabled:")
        print("  • 🤖 AI Deck Optimization")
        print("  • 🔮 Meta Prediction Algorithms") 
        print("  • 💎 Investment Analysis")
        print("  • 📈 Automated Trading Bot")
        print("  • 📷 Hardware Scanner")
        print("  • 💹 Market Intelligence")
        
        # Create and run application
        app = MTTGGCompleteSystem()
        print("\\n✨ MTTGG AI System Ready!")
        app.run()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("🔧 Please check that all AI files are present")
        sys.exit(1)
    except Exception as e:
        print(f"❌ System error: {e}")
        print("🔧 Check system configuration")
        sys.exit(1)

if __name__ == "__main__":
    main()