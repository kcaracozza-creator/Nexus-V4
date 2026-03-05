#!/usr/bin/env python3
"""
NEXUS CARD SCANNER - COMPLETE SYSTEM
Main launcher for all functionality
"""

import sys
import os

def main():
    print("=" * 80)
    print("🎴 NEXUS CARD SCANNER SYSTEM")
    print("=" * 80)
    print()
    
    while True:
        print("\n📋 MAIN MENU:")
        print()
        print("  1. 🤖 Hardware Test (Arduino + Motors)")
        print("  2. 🎮 AI Card Grading Demo")
        print("  3. 💰 Deckbuilding API (QuickBooks)")
        print("  4. 📊 Subscription Manager")
        print("  5. 🔧 XY Scanner Control")
        print("  6. 🎰 Card Shuffler Control")
        print("  7. 📈 System Status")
        print("  8. 🚀 Launch Full System")
        print()
        print("  0. ❌ Exit")
        print()
        
        choice = input("Select option: ").strip()
        
        if choice == "1":
            print("\n🤖 Hardware Test")
            print("-" * 80)
            os.system('python "PYTHON SOURCE FILES/complete_system_test.py"')
            
        elif choice == "2":
            print("\n🎮 AI Card Grading Demo")
            print("-" * 80)
            os.system('python "PYTHON SOURCE FILES/card_grading_analyzer.py"')
            
        elif choice == "3":
            print("\n💰 Deckbuilding API")
            print("-" * 80)
            os.system('python "PYTHON SOURCE FILES/deckbuilding_api.py"')
            
        elif choice == "4":
            print("\n📊 Subscription Manager")
            print("-" * 80)
            os.system('python "PYTHON SOURCE FILES/subscription_manager.py"')
            
        elif choice == "5":
            print("\n🔧 XY Scanner Control")
            print("-" * 80)
            os.system('python "PYTHON SOURCE FILES/xy_scanner_controller.py"')
            
        elif choice == "6":
            print("\n🎰 Card Shuffler Control")
            print("-" * 80)
            os.system('python "PYTHON SOURCE FILES/card_shuffler_controller.py"')
            
        elif choice == "7":
            print("\n📈 System Status")
            print("-" * 80)
            print("✅ Python:", sys.version.split()[0])
            print("✅ Platform:", sys.platform)
            print("✅ Working Directory:", os.getcwd())
            
            # Check for key files
            check_files = [
                "PYTHON SOURCE FILES/card_grading_analyzer.py",
                "PYTHON SOURCE FILES/deckbuilding_api.py",
                "PYTHON SOURCE FILES/xy_scanner_controller.py",
                "PYTHON SOURCE FILES/card_shuffler_controller.py",
                "PYTHON SOURCE FILES/subscription_manager.py",
                "SAMPLE_DATA/quickbooks_sales_sample.csv"
            ]
            
            print("\n📁 File Status:")
            for f in check_files:
                status = "✅" if os.path.exists(f) else "❌"
                print(f"  {status} {f}")
            
            # Check for hardware
            print("\n🔌 Hardware:")
            try:
                import serial.tools.list_ports
                ports = list(serial.tools.list_ports.comports())
                if ports:
                    print(f"  ✅ {len(ports)} COM port(s) detected:")
                    for p in ports:
                        print(f"     • {p.device}: {p.description}")
                else:
                    print("  ⚠️ No Arduino detected (will work in demo mode)")
            except:
                print("  ⚠️ Cannot check COM ports")
            
            input("\nPress Enter to continue...")
            
        elif choice == "8":
            print("\n🚀 Launching Full System")
            print("-" * 80)
            os.system('python "PYTHON SOURCE FILES/unified_system_demo.py"')
            
        elif choice == "0":
            print("\n👋 Goodbye!")
            break
            
        else:
            print("\n❌ Invalid choice. Try again.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
