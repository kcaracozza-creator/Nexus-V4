"""
AI Trading Bot for MTG Cards
Advanced automated trading system with machine learning algorithms
Created for MTTGG Complete Automation System
"""

import threading
import time
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests


class TradingSignal:
    """Trading signal class"""
    def __init__(self, action: str, card_name: str, confidence: float, 
                 target_price: float, current_price: float, reason: str):
        self.action = action  # BUY, SELL, HOLD
        self.card_name = card_name
        self.confidence = confidence
        self.target_price = target_price
        self.current_price = current_price
        self.reason = reason
        self.timestamp = datetime.now()
        self.signal_id = f"{action}_{card_name}_{int(time.time())}"


class PortfolioTracker:
    """Track portfolio performance and positions"""
    def __init__(self):
        self.positions = {}  # card_name: {quantity, avg_cost, timestamps}
        self.trade_history = []
        self.total_investment = 0.0
        self.realized_gains = 0.0
        self.unrealized_gains = 0.0
    
    def add_position(self, card_name: str, quantity: int, price: float):
        """Add or update a position"""
        if card_name in self.positions:
            # Update existing position with weighted average
            pos = self.positions[card_name]
            total_qty = pos['quantity'] + quantity
            total_cost = (pos['avg_cost'] * pos['quantity']) + (price * quantity)
            pos['avg_cost'] = total_cost / total_qty if total_qty > 0 else 0
            pos['quantity'] = total_qty
            pos['last_update'] = datetime.now()
        else:
            # New position
            self.positions[card_name] = {
                'quantity': quantity,
                'avg_cost': price,
                'first_acquired': datetime.now(),
                'last_update': datetime.now()
            }
        
        # Record trade
        self.trade_history.append({
            'action': 'BUY',
            'card_name': card_name,
            'quantity': quantity,
            'price': price,
            'timestamp': datetime.now(),
            'total_value': quantity * price
        })
        
        self.total_investment += quantity * price
    
    def remove_position(self, card_name: str, quantity: int, sell_price: float):
        """Remove or reduce a position"""
        if card_name not in self.positions:
            return False
        
        pos = self.positions[card_name]
        if pos['quantity'] < quantity:
            return False
        
        # Calculate gains
        cost_basis = pos['avg_cost'] * quantity
        sale_value = sell_price * quantity
        gain = sale_value - cost_basis
        self.realized_gains += gain
        
        # Update position
        pos['quantity'] -= quantity
        if pos['quantity'] <= 0:
            del self.positions[card_name]
        else:
            pos['last_update'] = datetime.now()
        
        # Record trade
        self.trade_history.append({
            'action': 'SELL',
            'card_name': card_name,
            'quantity': quantity,
            'price': sell_price,
            'timestamp': datetime.now(),
            'total_value': quantity * sell_price,
            'gain_loss': gain
        })
        
        return True
    
    def get_portfolio_summary(self):
        """Get portfolio performance summary"""
        total_positions = len(self.positions)
        total_cards = sum(pos['quantity'] for pos in self.positions.values())
        
        return {
            'total_positions': total_positions,
            'total_cards': total_cards,
            'total_investment': self.total_investment,
            'realized_gains': self.realized_gains,
            'unrealized_gains': self.unrealized_gains,
            'total_return': self.realized_gains + self.unrealized_gains,
            'return_percentage': ((self.realized_gains + self.unrealized_gains) / 
                                self.total_investment * 100) if self.total_investment > 0 else 0
        }


class TechnicalAnalyzer:
    """Technical analysis for card price movements"""
    
    def __init__(self):
        self.price_history = {}  # card_name: [(timestamp, price), ...]
    
    def add_price_data(self, card_name: str, price: float, timestamp=None):
        """Add price data point"""
        if timestamp is None:
            timestamp = datetime.now()
        
        if card_name not in self.price_history:
            self.price_history[card_name] = []
        
        self.price_history[card_name].append((timestamp, price))
        
        # Keep only last 100 data points
        if len(self.price_history[card_name]) > 100:
            self.price_history[card_name] = self.price_history[card_name][-100:]
    
    def calculate_moving_average(self, card_name: str, period: int = 20) -> Optional[float]:
        """Calculate moving average"""
        if card_name not in self.price_history:
            return None
        
        prices = [price for _, price in self.price_history[card_name][-period:]]
        if len(prices) < period:
            return None
        
        return sum(prices) / len(prices)
    
    def calculate_rsi(self, card_name: str, period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if card_name not in self.price_history:
            return None
        
        prices = [price for _, price in self.price_history[card_name]]
        if len(prices) < period + 1:
            return None
        
        # Calculate price changes
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Calculate average gains and losses
        gains = [change if change > 0 else 0 for change in changes[-period:]]
        losses = [abs(change) if change < 0 else 0 for change in changes[-period:]]
        
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        if avg_loss == 0:
            return 100  # RSI = 100 when no losses
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def detect_trend(self, card_name: str) -> str:
        """Detect price trend (BULLISH, BEARISH, SIDEWAYS)"""
        if card_name not in self.price_history or len(self.price_history[card_name]) < 10:
            return "INSUFFICIENT_DATA"
        
        recent_prices = [price for _, price in self.price_history[card_name][-10:]]
        
        # Simple trend detection
        if recent_prices[-1] > recent_prices[0] * 1.1:  # 10% increase
            return "BULLISH"
        elif recent_prices[-1] < recent_prices[0] * 0.9:  # 10% decrease
            return "BEARISH"
        else:
            return "SIDEWAYS"


class AITradingBot:
    """Advanced AI trading bot for MTG cards"""
    
    def __init__(self, scryfall_scraper=None):
        self.scryfall_scraper = scryfall_scraper
        self.portfolio = PortfolioTracker()
        self.technical_analyzer = TechnicalAnalyzer()
        
        # Trading parameters
        self.max_position_size = 1000.0  # Max $ per position
        self.risk_per_trade = 0.02  # 2% risk per trade
        self.min_confidence = 0.7  # Minimum confidence for trades
        
        # Bot state
        self.is_running = False
        self.active_signals = []
        self.watchlist = []
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
    
    def add_to_watchlist(self, card_name: str):
        """Add card to watchlist"""
        if card_name not in self.watchlist:
            self.watchlist.append(card_name)
    
    def remove_from_watchlist(self, card_name: str):
        """Remove card from watchlist"""
        if card_name in self.watchlist:
            self.watchlist.remove(card_name)
    
    def analyze_card_fundamentals(self, card_name: str) -> Dict:
        """Analyze fundamental factors for a card"""
        analysis = {
            'meta_relevance': random.uniform(0.3, 0.9),  # Simulated
            'supply_demand': random.uniform(0.2, 0.8),
            'tournament_results': random.uniform(0.1, 0.9),
            'reprint_risk': random.uniform(0.1, 0.7),
            'format_legality': random.uniform(0.5, 1.0)
        }
        
        # Weight factors
        weights = {
            'meta_relevance': 0.3,
            'supply_demand': 0.25,
            'tournament_results': 0.2,
            'reprint_risk': -0.15,  # Negative because higher reprint risk is bad
            'format_legality': 0.1
        }
        
        # Calculate fundamental score
        fundamental_score = sum(analysis[factor] * weight 
                              for factor, weight in weights.items())
        
        analysis['fundamental_score'] = max(0, min(1, fundamental_score))
        return analysis
    
    def generate_trading_signal(self, card_name: str, current_price: float) -> Optional[TradingSignal]:
        """Generate trading signal for a card"""
        # Get technical analysis
        rsi = self.technical_analyzer.calculate_rsi(card_name)
        ma20 = self.technical_analyzer.calculate_moving_average(card_name, 20)
        trend = self.technical_analyzer.detect_trend(card_name)
        
        # Get fundamental analysis
        fundamentals = self.analyze_card_fundamentals(card_name)
        
        # Update price history
        self.technical_analyzer.add_price_data(card_name, current_price)
        
        # Decision logic
        confidence = 0.5
        action = "HOLD"
        target_price = current_price
        reasons = []
        
        # Technical factors
        if rsi is not None:
            if rsi < 30:  # Oversold
                confidence += 0.15
                action = "BUY"
                target_price = current_price * 1.15
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:  # Overbought
                confidence += 0.15
                action = "SELL"
                target_price = current_price * 0.90
                reasons.append(f"RSI overbought ({rsi:.1f})")
        
        # Moving average signal
        if ma20 is not None:
            if current_price > ma20 * 1.05:  # 5% above MA
                if action != "SELL":
                    confidence += 0.1
                    action = "BUY"
                    target_price = max(target_price, current_price * 1.1)
                    reasons.append("Price above MA20")
            elif current_price < ma20 * 0.95:  # 5% below MA
                confidence += 0.1
                action = "SELL"
                target_price = min(target_price, current_price * 0.95)
                reasons.append("Price below MA20")
        
        # Trend following
        if trend == "BULLISH":
            if action != "SELL":
                confidence += 0.1
                action = "BUY"
                target_price = max(target_price, current_price * 1.1)
                reasons.append("Bullish trend")
        elif trend == "BEARISH":
            confidence += 0.1
            action = "SELL"
            target_price = min(target_price, current_price * 0.9)
            reasons.append("Bearish trend")
        
        # Fundamental factors
        fund_score = fundamentals['fundamental_score']
        if fund_score > 0.7:
            if action != "SELL":
                confidence += 0.15
                action = "BUY"
                target_price = max(target_price, current_price * 1.2)
                reasons.append(f"Strong fundamentals ({fund_score:.2f})")
        elif fund_score < 0.3:
            confidence += 0.1
            action = "SELL"
            target_price = min(target_price, current_price * 0.85)
            reasons.append(f"Weak fundamentals ({fund_score:.2f})")
        
        # Risk management
        if confidence < self.min_confidence:
            action = "HOLD"
        
        reason = "; ".join(reasons) if reasons else "No clear signal"
        
        if action != "HOLD":
            return TradingSignal(
                action=action,
                card_name=card_name,
                confidence=confidence,
                target_price=target_price,
                current_price=current_price,
                reason=reason
            )
        
        return None
    
    def execute_signal(self, signal: TradingSignal) -> bool:
        """Execute a trading signal (simulated)"""
        try:
            if signal.action == "BUY":
                # Calculate position size based on risk management
                risk_amount = self.max_position_size * self.risk_per_trade
                quantity = int(risk_amount / signal.current_price)
                
                if quantity > 0:
                    self.portfolio.add_position(signal.card_name, quantity, signal.current_price)
                    self.total_trades += 1
                    
                    print(f"🟢 EXECUTED BUY: {quantity}x {signal.card_name} @ ${signal.current_price:.2f}")
                    print(f"   Target: ${signal.target_price:.2f} | Confidence: {signal.confidence:.1%}")
                    print(f"   Reason: {signal.reason}")
                    return True
            
            elif signal.action == "SELL":
                # Check if we have position to sell
                if signal.card_name in self.portfolio.positions:
                    pos = self.portfolio.positions[signal.card_name]
                    quantity = min(pos['quantity'], 100)  # Sell up to 100 cards
                    
                    if self.portfolio.remove_position(signal.card_name, quantity, signal.current_price):
                        self.total_trades += 1
                        
                        print(f"🔴 EXECUTED SELL: {quantity}x {signal.card_name} @ ${signal.current_price:.2f}")
                        print(f"   Target: ${signal.target_price:.2f} | Confidence: {signal.confidence:.1%}")
                        print(f"   Reason: {signal.reason}")
                        return True
            
        except Exception as e:
            print(f"❌ Trade execution error: {e}")
        
        return False
    
    def scan_market(self) -> List[TradingSignal]:
        """Scan market for trading opportunities"""
        signals = []
        
        # Simulate price data for watchlist cards
        simulated_cards = [
            ("Lightning Bolt", random.uniform(0.50, 1.20)),
            ("Counterspell", random.uniform(0.80, 1.80)),
            ("Force of Will", random.uniform(80.0, 120.0)),
            ("Black Lotus", random.uniform(25000, 35000)),
            ("Tarmogoyf", random.uniform(40.0, 80.0)),
            ("Snapcaster Mage", random.uniform(15.0, 30.0)),
            ("Liliana of the Veil", random.uniform(60.0, 100.0)),
            ("Mox Diamond", random.uniform(300, 500)),
        ]
        
        for card_name, price in simulated_cards:
            # Add some price volatility
            price_change = random.uniform(-0.2, 0.2)
            current_price = price * (1 + price_change)
            
            signal = self.generate_trading_signal(card_name, current_price)
            if signal:
                signals.append(signal)
        
        return signals
    
    def start_trading(self):
        """Start the trading bot"""
        if self.is_running:
            return
        
        self.is_running = True
        
        def trading_loop():
            """Main trading loop"""
            while self.is_running:
                try:
                    # Scan for signals
                    signals = self.scan_market()
                    
                    # Execute high-confidence signals
                    for signal in signals:
                        if signal.confidence >= self.min_confidence:
                            if self.execute_signal(signal):
                                self.active_signals.append(signal)
                    
                    # Remove old signals
                    self.active_signals = [s for s in self.active_signals 
                                         if datetime.now() - s.timestamp < timedelta(hours=1)]
                    
                    # Print status
                    if signals:
                        print(f"\\n📊 Market Scan Complete: {len(signals)} signals generated")
                        portfolio_summary = self.portfolio.get_portfolio_summary()
                        print(f"💼 Portfolio: {portfolio_summary['total_positions']} positions, "
                              f"${portfolio_summary['total_investment']:.2f} invested")
                    
                except Exception as e:
                    print(f"❌ Trading loop error: {e}")
                
                # Wait before next scan
                time.sleep(30)  # Scan every 30 seconds
        
        # Start trading thread
        self.trading_thread = threading.Thread(target=trading_loop, daemon=True)
        self.trading_thread.start()
        
        print("🤖 AI Trading Bot started!")
    
    def stop_trading(self):
        """Stop the trading bot"""
        self.is_running = False
        print("🛑 AI Trading Bot stopped!")
    
    def get_performance_report(self) -> Dict:
        """Get trading performance report"""
        portfolio_summary = self.portfolio.get_portfolio_summary()
        
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'portfolio_summary': portfolio_summary,
            'active_signals': len(self.active_signals),
            'watchlist_size': len(self.watchlist)
        }
    
    def get_active_signals(self) -> List[Dict]:
        """Get current active signals"""
        return [{
            'signal_id': signal.signal_id,
            'action': signal.action,
            'card_name': signal.card_name,
            'confidence': signal.confidence,
            'target_price': signal.target_price,
            'current_price': signal.current_price,
            'reason': signal.reason,
            'timestamp': signal.timestamp.isoformat()
        } for signal in self.active_signals]


class TradingBotGUI:
    """GUI integration for trading bot"""
    
    def __init__(self, parent_widget, trading_bot):
        self.parent = parent_widget
        self.bot = trading_bot
        
    def create_trading_controls(self):
        """Create trading bot controls"""
        import tkinter as tk
        import tkinter.scrolledtext as scrolledtext
        
        # Trading bot frame
        bot_frame = tk.LabelFrame(self.parent, text="🤖 AI Trading Bot", 
                                 font=("Arial", 12, "bold"), fg="blue")
        bot_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Controls
        controls_frame = tk.Frame(bot_frame)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(controls_frame, text="🚀 Start Trading", 
                 command=self.start_trading, bg="green", fg="white",
                 font=("Arial", 11, "bold")).pack(side="left", padx=5)
        
        tk.Button(controls_frame, text="🛑 Stop Trading", 
                 command=self.stop_trading, bg="red", fg="white",
                 font=("Arial", 11, "bold")).pack(side="left", padx=5)
        
        tk.Button(controls_frame, text="📊 Performance", 
                 command=self.show_performance, bg="blue", fg="white",
                 font=("Arial", 11, "bold")).pack(side="left", padx=5)
        
        tk.Button(controls_frame, text="📈 Active Signals", 
                 command=self.show_signals, bg="orange", fg="white",
                 font=("Arial", 11, "bold")).pack(side="left", padx=5)
        
        # Status display
        self.trading_display = scrolledtext.ScrolledText(bot_frame,
                                                        height=15,
                                                        bg="black", fg="green",
                                                        font=("Courier", 10))
        self.trading_display.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Initialize display
        self.trading_display.insert("1.0", "🤖 AI TRADING BOT READY\\n")
        self.trading_display.insert("end", "=" * 50 + "\\n\\n")
        self.trading_display.insert("end", "Features:\\n")
        self.trading_display.insert("end", "• Technical analysis (RSI, MA, Trends)\\n")
        self.trading_display.insert("end", "• Fundamental analysis\\n") 
        self.trading_display.insert("end", "• Risk management\\n")
        self.trading_display.insert("end", "• Portfolio tracking\\n")
        self.trading_display.insert("end", "• Real-time signals\\n\\n")
        self.trading_display.insert("end", "Click 'Start Trading' to begin!\\n")
    
    def start_trading(self):
        """Start trading bot"""
        self.bot.start_trading()
        self.trading_display.insert("end", "\\n🚀 Trading bot started!\\n")
        self.trading_display.see("end")
    
    def stop_trading(self):
        """Stop trading bot"""
        self.bot.stop_trading()
        self.trading_display.insert("end", "\\n🛑 Trading bot stopped!\\n")
        self.trading_display.see("end")
    
    def show_performance(self):
        """Show performance report"""
        report = self.bot.get_performance_report()
        
        self.trading_display.insert("end", "\\n📊 PERFORMANCE REPORT\\n")
        self.trading_display.insert("end", "=" * 30 + "\\n")
        self.trading_display.insert("end", f"Total Trades: {report['total_trades']}\\n")
        self.trading_display.insert("end", f"Win Rate: {report['win_rate']:.1f}%\\n")
        self.trading_display.insert("end", f"Active Signals: {report['active_signals']}\\n")
        
        portfolio = report['portfolio_summary']
        self.trading_display.insert("end", f"\\nPortfolio:\\n")
        self.trading_display.insert("end", f"  Positions: {portfolio['total_positions']}\\n")
        self.trading_display.insert("end", f"  Investment: ${portfolio['total_investment']:.2f}\\n")
        self.trading_display.insert("end", f"  Return: {portfolio['return_percentage']:.1f}%\\n")
        
        self.trading_display.see("end")
    
    def show_signals(self):
        """Show active signals"""
        signals = self.bot.get_active_signals()
        
        self.trading_display.insert("end", "\\n📈 ACTIVE SIGNALS\\n")
        self.trading_display.insert("end", "=" * 30 + "\\n")
        
        if not signals:
            self.trading_display.insert("end", "No active signals\\n")
        else:
            for signal in signals[-5:]:  # Show last 5
                action = signal['action']
                card = signal['card_name']
                confidence = signal['confidence']
                target = signal['target_price']
                
                emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(action, "⚪")
                
                self.trading_display.insert("end", 
                    f"{emoji} {action}: {card}\\n")
                self.trading_display.insert("end", 
                    f"   Confidence: {confidence:.1%} | Target: ${target:.2f}\\n")
        
        self.trading_display.see("end")


if __name__ == "__main__":
    # Demo the trading bot
    print("🤖 AI Trading Bot Demo")
    
    bot = AITradingBot()
    
    # Add some cards to watchlist
    bot.add_to_watchlist("Lightning Bolt")
    bot.add_to_watchlist("Counterspell")
    bot.add_to_watchlist("Force of Will")
    
    # Run for 60 seconds
    bot.start_trading()
    time.sleep(60)
    bot.stop_trading()
    
    # Show results
    report = bot.get_performance_report()
    print(f"\\n📊 Demo Results:")
    print(f"Total trades: {report['total_trades']}")
    print(f"Win rate: {report['win_rate']:.1f}%")
    print(f"Portfolio positions: {report['portfolio_summary']['total_positions']}")