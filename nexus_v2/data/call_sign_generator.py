#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS Call Sign Generator
Generates unique identifiers for cards and collections
"""

import random
import string
from typing import Optional


class CallSignGenerator:
    """Generates unique call signs for NEXUS items"""

    PREFIXES = ['NX', 'MG', 'PT', 'SP', 'RC']  # NEXUS, Magic, Pokemon, Sports, Rare

    def __init__(self, prefix: str = 'NX'):
        self.prefix = prefix
        self.counter = 0

    def generate(self, length: int = 8) -> str:
        """Generate a unique call sign"""
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choices(chars, k=length - len(self.prefix) - 1))
        self.counter += 1
        return f"{self.prefix}-{random_part}"

    def generate_batch(self, count: int) -> list:
        """Generate multiple unique call signs"""
        return [self.generate() for _ in range(count)]


def generate_call_sign(prefix: str = 'NX', length: int = 8) -> str:
    """Convenience function to generate a single call sign"""
    gen = CallSignGenerator(prefix)
    return gen.generate(length)


def generate_call_signs(count: int, prefix: str = 'NX') -> list:
    """Generate multiple call signs"""
    gen = CallSignGenerator(prefix)
    return gen.generate_batch(count)


# Singleton generator instance
_generator: Optional[CallSignGenerator] = None


def get_generator(prefix: str = 'NX') -> CallSignGenerator:
    """Get or create a singleton generator instance"""
    global _generator
    if _generator is None or _generator.prefix != prefix:
        _generator = CallSignGenerator(prefix)
    return _generator


if __name__ == "__main__":
    gen = CallSignGenerator('NX')
    print("Sample call signs:")
    for sign in gen.generate_batch(5):
        print(f"  {sign}")
