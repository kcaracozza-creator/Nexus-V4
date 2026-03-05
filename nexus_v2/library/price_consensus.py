"""
NEXUS Price Consensus Engine
============================
Aggregates and displays third-party market price data.
NEXUS does not determine, generate, or recommend prices.
All prices are sourced from and attributed to third-party providers.

Sources (weighted by trust/volume):
- TCGPlayer Market: 50% (highest transaction volume)
- Scryfall:         30% (aggregates TCGPlayer + others)
- CardKingdom:      15% (retail, usually 10-20% higher)
- DB Cache:          5% (historical, may be stale)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics


@dataclass
class PriceSource:
    """Individual price source"""
    name: str
    price: float
    weight: float  # Trust weight 0-1
    timestamp: Optional[datetime] = None
    is_retail: bool = False  # Retail prices are typically higher


@dataclass
class ConsensusResult:
    """Result of consensus calculation"""
    consensus_price: float
    confidence: str  # HIGH, MED, LOW
    confidence_score: float  # 0-100
    sources_used: int
    sources_agree: int
    outliers: List[str]  # Sources flagged as outliers
    anomaly_detected: bool
    anomaly_type: Optional[str]  # "spike", "crash", "stale"
    source_summary: str  # Source attribution and data quality note


class PriceConsensus:
    """
    Byzantine Fault Tolerant price consensus engine.
    Uses weighted voting to determine true market price.
    """

    # Source weights (trust levels) - MTG
    SOURCE_WEIGHTS_MTG = {
        'tcgplayer': 0.50,   # Highest volume marketplace
        'scryfall': 0.30,    # Aggregates from TCGPlayer
        'cardkingdom': 0.15, # Retail (typically 10-20% higher)
        'db_cache': 0.05,    # Historical, may be stale
    }

    # Source weights (trust levels) - Yu-Gi-Oh!
    SOURCE_WEIGHTS_YUGIOH = {
        'tcgplayer': 0.50,      # US market leader
        'cardmarket': 0.30,     # EU market leader
        'coolstuffinc': 0.15,   # US retail
        'ebay': 0.05,           # Auction prices (volatile)
        'db_cache': 0.05,       # Historical, may be stale
    }

    # Default to MTG weights for backward compatibility
    SOURCE_WEIGHTS = SOURCE_WEIGHTS_MTG

    # Anomaly thresholds
    OUTLIER_THRESHOLD = 0.25      # 25% from consensus = outlier
    SPIKE_THRESHOLD = 2.0         # 200% increase = spike
    CRASH_THRESHOLD = 0.5         # 50% decrease = crash
    STALE_HOURS = 72              # Data older than 72h is stale

    # Confidence thresholds
    HIGH_CONFIDENCE_AGREE = 0.15  # Sources within 15%
    MED_CONFIDENCE_AGREE = 0.30   # Sources within 30%

    def __init__(self, card_type: str = "mtg"):
        """
        Initialize price consensus engine

        Args:
            card_type: Card type ('mtg', 'pokemon', 'yugioh')
        """
        self.price_history: Dict[str, List[Tuple[float, datetime]]] = {}
        self.card_type = card_type
        self._update_source_weights()

    def _update_source_weights(self):
        """Update SOURCE_WEIGHTS based on card_type"""
        if self.card_type == "yugioh":
            self.SOURCE_WEIGHTS = self.SOURCE_WEIGHTS_YUGIOH
        else:
            self.SOURCE_WEIGHTS = self.SOURCE_WEIGHTS_MTG

    def set_card_type(self, card_type: str):
        """
        Change card type and update source weights

        Args:
            card_type: Card type ('mtg', 'pokemon', 'yugioh')
        """
        self.card_type = card_type
        self._update_source_weights()

    def calculate_consensus(
        self,
        scryfall_id: str,
        prices: Dict[str, float],
        previous_price: Optional[float] = None,
        previous_date: Optional[datetime] = None
    ) -> ConsensusResult:
        """
        Calculate consensus price from multiple sources.

        Args:
            scryfall_id: Card identifier
            prices: Dict of source_name -> price
            previous_price: Last known price (for anomaly detection)
            previous_date: When previous price was recorded

        Returns:
            ConsensusResult with consensus price and confidence
        """
        sources = []
        for name, price in prices.items():
            if price and price > 0:
                weight = self.SOURCE_WEIGHTS.get(name.lower(), 0.10)
                sources.append(PriceSource(
                    name=name,
                    price=price,
                    weight=weight,
                    is_retail=(name.lower() == 'cardkingdom')
                ))

        if not sources:
            return ConsensusResult(
                consensus_price=0,
                confidence="LOW",
                confidence_score=0,
                sources_used=0,
                sources_agree=0,
                outliers=[],
                anomaly_detected=False,
                anomaly_type=None,
                source_summary="No price data available from third-party sources."
            )

        # Step 1: Calculate weighted consensus
        total_weight = sum(s.weight for s in sources)
        weighted_price = sum(s.price * s.weight for s in sources) / total_weight

        # Step 2: Identify outliers (>25% from weighted consensus)
        outliers = []
        agreeing = []
        for s in sources:
            deviation = abs(s.price - weighted_price) / weighted_price if weighted_price > 0 else 1
            if deviation > self.OUTLIER_THRESHOLD:
                outliers.append(s.name)
            else:
                agreeing.append(s)

        # Step 3: Recalculate without outliers if we have enough agreeing sources
        if len(agreeing) >= 2:
            total_weight = sum(s.weight for s in agreeing)
            consensus_price = sum(s.price * s.weight for s in agreeing) / total_weight
        else:
            consensus_price = weighted_price

        # Step 4: Check for anomalies (spikes/crashes)
        anomaly_detected = False
        anomaly_type = None

        if previous_price and previous_price > 0:
            change_ratio = consensus_price / previous_price

            if change_ratio >= self.SPIKE_THRESHOLD:
                anomaly_detected = True
                anomaly_type = "spike"
            elif change_ratio <= self.CRASH_THRESHOLD:
                anomaly_detected = True
                anomaly_type = "crash"

            # Check for stale data
            if previous_date:
                hours_old = (datetime.now() - previous_date).total_seconds() / 3600
                if hours_old > self.STALE_HOURS:
                    anomaly_type = "stale" if not anomaly_type else f"{anomaly_type}_stale"

        # Step 5: Calculate confidence score
        if len(sources) == 0:
            confidence_score = 0
        elif len(sources) == 1:
            confidence_score = 40  # Single source = low-medium
        else:
            # Calculate price variance
            prices_list = [s.price for s in sources]
            if len(prices_list) >= 2:
                variance = statistics.stdev(prices_list) / statistics.mean(prices_list)
            else:
                variance = 0

            # Score based on agreement
            agree_ratio = len(agreeing) / len(sources)
            confidence_score = (
                agree_ratio * 60 +  # Agreement contributes 60%
                (1 - min(variance, 1)) * 30 +  # Low variance contributes 30%
                min(len(sources) / 4, 1) * 10  # More sources contributes 10%
            )

            # Penalize for anomalies
            if anomaly_detected:
                confidence_score *= 0.5

        # Determine confidence level
        if confidence_score >= 70 and not anomaly_detected:
            confidence = "HIGH"
        elif confidence_score >= 40:
            confidence = "MED"
        else:
            confidence = "LOW"

        # Build source attribution summary
        source_summary = self._build_source_summary(
            sources, outliers, anomaly_detected, anomaly_type
        )

        return ConsensusResult(
            consensus_price=round(consensus_price, 2),
            confidence=confidence,
            confidence_score=round(confidence_score, 1),
            sources_used=len(sources),
            sources_agree=len(agreeing),
            outliers=outliers,
            anomaly_detected=anomaly_detected,
            anomaly_type=anomaly_type,
            source_summary=source_summary
        )

    def _build_source_summary(
        self,
        sources: List[PriceSource],
        outliers: List[str],
        anomaly: bool,
        anomaly_type: Optional[str],
    ) -> str:
        """Build source attribution and data quality note.
        Market data provided by third-party sources. NEXUS does not determine prices."""
        source_names = [s.name for s in sources]
        parts = [f"Sources: {', '.join(source_names)}"]

        if outliers:
            parts.append(f"Outlier sources excluded: {', '.join(outliers)}")

        if anomaly:
            if anomaly_type == "spike":
                parts.append("Note: Large price change detected vs previous data point")
            elif anomaly_type == "crash":
                parts.append("Note: Large price decrease detected vs previous data point")
            elif "stale" in str(anomaly_type):
                parts.append("Note: Data may be outdated - consider refreshing")

        parts.append("Market data provided by third-party sources. NEXUS does not determine prices.")
        return ". ".join(parts)

    def check_listing_sanity(
        self,
        listing_price: float,
        market_price: float,
        is_buying: bool = False
    ) -> Tuple[bool, str]:
        """
        Check if a listing price is sane relative to market.

        Args:
            listing_price: Price being listed/offered
            market_price: Current market consensus
            is_buying: True if this is a buylist offer, False if selling

        Returns:
            (is_sane, warning_message)
        """
        if market_price <= 0:
            return True, ""

        ratio = listing_price / market_price

        if is_buying:
            # Buylist - we're offering to buy
            if ratio > 1.0:
                return False, f"Buylist ${listing_price:.2f} is ABOVE market ${market_price:.2f} - will lose money!"
            elif ratio > 0.85:
                return True, f"Buylist at {ratio:.0%} of market - tight margin"
            elif ratio > 0.60:
                return True, ""  # Normal buylist range 60-85%
            else:
                return True, f"Buylist at {ratio:.0%} - very low, may not get sellers"
        else:
            # Selling - we're listing to sell
            if ratio < 0.60:
                return False, f"Price ${listing_price:.2f} is {ratio:.0%} of market - significantly underpriced!"
            elif ratio < 0.85:
                return True, f"Price is {ratio:.0%} of market - below average"
            elif ratio > 1.50:
                return True, f"Price is {ratio:.0%} of market - may not sell quickly"
            elif ratio > 2.0:
                return False, f"Price ${listing_price:.2f} is {ratio:.0%} of market - unlikely to sell"
            else:
                return True, ""  # Normal sell range 85-150%

# Quick test
if __name__ == "__main__":
    engine = PriceConsensus()

    # Test consensus
    prices = {
        'tcgplayer': 10.50,
        'scryfall': 10.25,
        'cardkingdom': 12.99,  # Retail, typically higher
        'db_cache': 9.80,
    }

    result = engine.calculate_consensus("test-id", prices, previous_price=10.00)
    print(f"Consensus: ${result.consensus_price:.2f}")
    print(f"Confidence: {result.confidence} ({result.confidence_score}%)")
    print(f"Sources: {result.sources_used} used, {result.sources_agree} agree")
    print(f"Outliers: {result.outliers}")
    print(f"Source summary: {result.source_summary}")

    # Test listing sanity
    sane, warning = engine.check_listing_sanity(5.00, 10.00, is_buying=False)
    print(f"\nListing $5 vs $10 market: {warning if warning else 'OK'}")
