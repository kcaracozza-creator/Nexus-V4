#!/usr/bin/env python3
"""
NEXUS V2 - Market Intelligence Module
======================================
Price tracking, market trends, and alerts for collectibles.
"""

import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PricePoint:
    """Single price data point"""
    card_name: str
    set_code: str
    price_usd: float
    price_usd_foil: Optional[float]
    timestamp: datetime
    source: str
    market_trend: str = "stable"
    confidence: float = 1.0


class MarketIntelligence:
    """
    Market Intelligence System for price tracking and analysis.

    Features:
    - Price fetching from Scryfall API
    - Watchlist management
    - Price history tracking
    - Trend analysis
    - Price alerts
    """

    SCRYFALL_API = "https://api.scryfall.com"

    def __init__(self, db_path: str = None):
        """Initialize Market Intelligence system"""
        if db_path is None:
            db_path = str(Path(__file__).parent / "market_data.db")

        self.db_path = db_path
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

        self._setup_database()
        logger.info(f"[OK] Market Intelligence initialized: {db_path}")

    def _setup_database(self) -> None:
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Price history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_code TEXT,
                price_usd REAL,
                price_usd_foil REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'scryfall',
                market_trend TEXT DEFAULT 'stable',
                confidence REAL DEFAULT 1.0
            )
        ''')

        # Watchlist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_code TEXT,
                priority INTEGER DEFAULT 1,
                added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(card_name, set_code)
            )
        ''')

        # Price alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_code TEXT,
                alert_type TEXT NOT NULL,
                threshold REAL NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def add_to_watchlist(self, card_name: str, set_code: str = "",
                         priority: int = 1) -> bool:
        """Add a card to the watchlist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO watchlist (card_name, set_code, priority)
                VALUES (?, ?, ?)
            ''', (card_name, set_code, priority))

            conn.commit()
            conn.close()
            logger.info(f"[WATCHLIST] Added: {card_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add to watchlist: {e}")
            return False

    def load_watchlist(self) -> List[Dict[str, Any]]:
        """Load all cards from watchlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT card_name, set_code, priority, added_date
            FROM watchlist
            ORDER BY priority DESC, card_name
        ''')

        cards = cursor.fetchall()
        conn.close()

        return [
            {
                'card_name': row[0],
                'set_code': row[1],
                'priority': row[2],
                'added_date': row[3]
            }
            for row in cards
        ]

    def fetch_scryfall_prices(self, card_name: str,
                               set_code: str = "") -> Optional[PricePoint]:
        """Fetch current prices from Scryfall API"""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests module not available")
            return None

        try:
            # Build search query
            query = f'!"{card_name}"'
            if set_code:
                query += f" set:{set_code}"

            url = f"{self.SCRYFALL_API}/cards/search"
            params = {'q': query}

            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                logger.debug(f"Scryfall search failed for {card_name}")
                return None

            data = response.json()

            if not data.get('data'):
                return None

            card_data = data['data'][0]
            prices = card_data.get('prices', {})

            price_usd = float(prices.get('usd') or 0)
            price_usd_foil = float(prices.get('usd_foil') or 0) if prices.get('usd_foil') else None

            price_point = PricePoint(
                card_name=card_data.get('name', card_name),
                set_code=card_data.get('set', set_code),
                price_usd=price_usd,
                price_usd_foil=price_usd_foil,
                timestamp=datetime.now(),
                source='scryfall'
            )

            # Store in database
            self._store_price_data(price_point)

            return price_point

        except Exception as e:
            logger.error(f"Failed to fetch prices for {card_name}: {e}")
            return None

    def _store_price_data(self, price_point: PricePoint) -> None:
        """Store price data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO price_history
            (card_name, set_code, price_usd, price_usd_foil, timestamp, source)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            price_point.card_name,
            price_point.set_code,
            price_point.price_usd,
            price_point.price_usd_foil,
            price_point.timestamp.isoformat(),
            price_point.source
        ))

        conn.commit()
        conn.close()

    def get_price_history(self, card_name: str,
                          days: int = 30) -> List[PricePoint]:
        """Get price history for a card"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute('''
            SELECT card_name, set_code, price_usd, price_usd_foil,
                   timestamp, source, market_trend, confidence
            FROM price_history
            WHERE card_name = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        ''', (card_name, since_date))

        rows = cursor.fetchall()
        conn.close()

        return [
            PricePoint(
                card_name=row[0],
                set_code=row[1],
                price_usd=row[2] or 0.0,
                price_usd_foil=row[3],
                timestamp=datetime.fromisoformat(row[4]) if row[4] else datetime.now(),
                source=row[5] or 'unknown',
                market_trend=row[6] or 'stable',
                confidence=row[7] or 1.0
            )
            for row in rows
        ]

    def analyze_price_trend(self, card_name: str) -> Dict[str, Any]:
        """Analyze price trend for a card"""
        history = self.get_price_history(card_name, days=30)

        if len(history) < 2:
            return {
                'trend': 'insufficient_data',
                'change_percent': 0.0,
                'confidence': 0.0,
                'data_points': len(history)
            }

        prices = [p.price_usd for p in history if p.price_usd > 0]

        if len(prices) < 2:
            return {
                'trend': 'no_price_data',
                'change_percent': 0.0,
                'confidence': 0.0,
                'data_points': 0
            }

        # Compare recent vs older prices
        mid = len(prices) // 2
        recent_avg = sum(prices[:mid]) / mid if mid > 0 else prices[0]
        older_avg = sum(prices[mid:]) / (len(prices) - mid) if len(prices) > mid else prices[-1]

        if older_avg == 0:
            change_percent = 0.0
        else:
            change_percent = ((recent_avg - older_avg) / older_avg) * 100

        # Determine trend
        if change_percent > 10:
            trend = 'rising'
        elif change_percent < -10:
            trend = 'falling'
        else:
            trend = 'stable'

        # Confidence based on data points
        confidence = min(1.0, len(prices) / 10)

        return {
            'trend': trend,
            'change_percent': round(change_percent, 2),
            'confidence': round(confidence, 2),
            'data_points': len(prices),
            'current_price': prices[0] if prices else 0,
            'avg_price': round(sum(prices) / len(prices), 2) if prices else 0
        }

    def update_watchlist_prices(self) -> int:
        """Update prices for all cards in watchlist"""
        watchlist = self.load_watchlist()
        updated_count = 0

        for card in watchlist:
            price_point = self.fetch_scryfall_prices(
                card['card_name'],
                card.get('set_code', '')
            )
            if price_point:
                updated_count += 1

            # Rate limiting - Scryfall requests 50-100ms delay
            time.sleep(0.1)

        logger.info(f"[WATCHLIST] Updated {updated_count}/{len(watchlist)} prices")
        return updated_count

    def create_price_alert(self, card_name: str, alert_type: str,
                           threshold: float, set_code: str = "") -> bool:
        """
        Create a price alert.

        Args:
            card_name: Card to monitor
            alert_type: 'above', 'below', or 'change'
            threshold: Price threshold or percentage change
            set_code: Optional set code
        """
        if alert_type not in ('above', 'below', 'change'):
            logger.error(f"Invalid alert type: {alert_type}")
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO price_alerts
                (card_name, set_code, alert_type, threshold)
                VALUES (?, ?, ?, ?)
            ''', (card_name, set_code, alert_type, threshold))

            conn.commit()
            conn.close()
            logger.info(f"[ALERT] Created: {card_name} {alert_type} ${threshold}")
            return True
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            return False

    def check_price_alerts(self) -> List[Dict[str, Any]]:
        """Check all active alerts and return triggered ones"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, card_name, set_code, alert_type, threshold
            FROM price_alerts
            WHERE is_active = 1
        ''')

        alerts = cursor.fetchall()
        conn.close()

        triggered_alerts = []

        for alert in alerts:
            alert_id, card_name, set_code, alert_type, threshold = alert

            # Get current price
            price_point = self.fetch_scryfall_prices(card_name, set_code)
            if not price_point:
                continue

            triggered = False
            current_price = price_point.price_usd

            if alert_type == 'above' and current_price >= threshold:
                triggered = True
            elif alert_type == 'below' and current_price <= threshold:
                triggered = True
            elif alert_type == 'change':
                trend = self.analyze_price_trend(card_name)
                if abs(trend.get('change_percent', 0)) >= threshold:
                    triggered = True

            if triggered:
                triggered_alerts.append({
                    'alert_id': alert_id,
                    'card_name': card_name,
                    'set_code': set_code,
                    'alert_type': alert_type,
                    'threshold': threshold,
                    'current_price': current_price
                })

        return triggered_alerts

    def start_monitoring(self, interval_minutes: int = 60) -> None:
        """Start background price monitoring"""
        if self._monitoring:
            logger.warning("Monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_minutes,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"[MONITOR] Started (interval: {interval_minutes}min)")

    def stop_monitoring(self) -> None:
        """Stop background price monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("[MONITOR] Stopped")

    def _monitoring_loop(self, interval_minutes: int) -> None:
        """Background monitoring loop"""
        while self._monitoring:
            try:
                self.update_watchlist_prices()
                alerts = self.check_price_alerts()

                if alerts:
                    logger.info(f"[ALERT] {len(alerts)} price alerts triggered")
                    for alert in alerts:
                        logger.info(
                            f"  - {alert['card_name']}: ${alert['current_price']:.2f} "
                            f"({alert['alert_type']} ${alert['threshold']:.2f})"
                        )
            except Exception as e:
                logger.error(f"Monitoring error: {e}")

            # Sleep in small intervals for responsive shutdown
            for _ in range(interval_minutes * 60):
                if not self._monitoring:
                    break
                time.sleep(1)

    def generate_market_report(self) -> Dict[str, Any]:
        """Generate a comprehensive market report"""
        watchlist = self.load_watchlist()

        report = {
            'generated_at': datetime.now().isoformat(),
            'total_watched': len(watchlist),
            'cards': [],
            'insights': []
        }

        rising_count = 0
        falling_count = 0
        stable_count = 0

        for card in watchlist:
            trend = self.analyze_price_trend(card['card_name'])

            card_report = {
                'name': card['card_name'],
                'set_code': card.get('set_code', ''),
                **trend
            }
            report['cards'].append(card_report)

            if trend['trend'] == 'rising':
                rising_count += 1
            elif trend['trend'] == 'falling':
                falling_count += 1
            else:
                stable_count += 1

        # Generate market data summary (source attribution only, no trading guidance)
        total = len(watchlist)
        if total > 0:
            if rising_count > total * 0.5:
                report['insights'].append(f"Price data: {rising_count} of {total} watched cards trending upward (source: Scryfall/TCGPlayer)")
            if falling_count > total * 0.5:
                report['insights'].append(f"Price data: {falling_count} of {total} watched cards trending downward (source: Scryfall/TCGPlayer)")
            if stable_count > total * 0.7:
                report['insights'].append(f"Price data: {stable_count} of {total} watched cards showing stable prices (source: Scryfall/TCGPlayer)")
        report['disclaimer'] = "Market data provided by Scryfall/TCGPlayer. NEXUS does not determine prices."

        report['summary'] = {
            'rising': rising_count,
            'falling': falling_count,
            'stable': stable_count
        }

        return report


# Module test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    intel = MarketIntelligence()

    # Test watchlist
    intel.add_to_watchlist("Lightning Bolt", "2x2")
    intel.add_to_watchlist("Sol Ring", "c21")

    print("\nWatchlist:")
    for card in intel.load_watchlist():
        print(f"  - {card['card_name']} ({card['set_code']})")

    # Test price fetch
    print("\nFetching prices...")
    price = intel.fetch_scryfall_prices("Lightning Bolt")
    if price:
        print(f"  Lightning Bolt: ${price.price_usd:.2f}")

    # Generate report
    print("\nMarket Report:")
    report = intel.generate_market_report()
    print(f"  Total watched: {report['total_watched']}")
    print(f"  Rising: {report['summary']['rising']}")
    print(f"  Falling: {report['summary']['falling']}")
    print(f"  Stable: {report['summary']['stable']}")
