"""
MTTGG Subscription & Licensing System
Multi-tier subscription management with online/offline validation
"""

import json
import hashlib
import uuid
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import base64
from cryptography.fernet import Fernet
import requests


class SubscriptionTier:
    """Defines subscription tier capabilities - Each tier INCLUDES all previous tier features"""
    
    # Base features available to ALL tiers (even free)
    BASE_FEATURES = {
        'scanner_enabled': True,
        'collection_management': True,
        'basic_filtering': True,
        'basic_sorting': True,
        'card_images': True,
        'set_information': True,
        'rarity_display': True,
        'condition_tracking': True
    }
    
    # Tier definitions - CUMULATIVE (each tier gets everything below + new features)
    TIERS = {
        'free': {
            'name': 'Free Trial',
            'price': 0,
            'tier_level': 0,  # Used to check if tier A >= tier B
            'desktop_features': {
                # BASE FEATURES (inherited)
                **BASE_FEATURES,
                # FREE tier additions
                'max_cards': 100,
                'advanced_filtering': False,
                'advanced_sorting': False,
                'price_tracking': False,
                'foil_tracking': False,
                'export_data': False,
                'statistics_panel': False,
                'set_completion': False,
                'api_access': False,
                'custom_reports': False,
                'multi_store': False,
                'automated_pricing': False,
                'inventory_alerts': False,
                'bulk_operations': False,
                'image_grid_view': False
            },
            'marketplace_features': {
                'can_list': False,
                'max_listings': 0,
                'commission_rate': 0,
                'featured_products': 0,
                'promotions': False,
                'analytics': False,
                'bulk_upload': False,
                'api_integration': False,
                'custom_storefront': False,
                'priority_listing': False
            },
            'support': 'community',
            'trial_days': 14
        },
        
        'starter': {
            'name': 'Starter',
            'price': 29,
            'billing_period': 'monthly',
            'tier_level': 1,
            'desktop_features': {
                # BASE FEATURES (inherited from FREE)
                **BASE_FEATURES,
                # STARTER tier upgrades from FREE
                'max_cards': 5000,  # Upgraded from 100
                'advanced_filtering': True,  # NEW in Starter
                'advanced_sorting': True,  # NEW in Starter
                'price_tracking': True,  # NEW in Starter
                'foil_tracking': True,  # NEW in Starter
                'export_data': True,  # NEW in Starter (CSV/Excel)
                'statistics_panel': True,  # NEW in Starter
                'set_completion': True,  # NEW in Starter
                'image_grid_view': True,  # NEW in Starter
                'bulk_operations': True,  # NEW in Starter
                # Still locked (upgrade to Pro for these)
                'api_access': False,
                'custom_reports': False,
                'multi_store': False,
                'automated_pricing': False,
                'inventory_alerts': False
            },
            'marketplace_features': {
                # STARTER gets marketplace access
                'can_list': True,  # NEW in Starter
                'max_listings': 1000,
                'commission_rate': 8.0,  # 8%
                'featured_products': 5,
                'promotions': True,
                'analytics': 'basic',
                'bulk_upload': True,
                # Still locked
                'api_integration': False,
                'custom_storefront': False,
                'priority_listing': False
            },
            'support': 'email',
            'annual_discount': 0.15  # 15% off if paid annually
        },
        
        'professional': {
            'name': 'Professional',
            'price': 79,
            'billing_period': 'monthly',
            'tier_level': 2,
            'desktop_features': {
                # ALL STARTER FEATURES (inherited)
                **BASE_FEATURES,
                'advanced_filtering': True,  # From Starter
                'advanced_sorting': True,  # From Starter
                'price_tracking': True,  # From Starter
                'foil_tracking': True,  # From Starter
                'export_data': True,  # From Starter
                'statistics_panel': True,  # From Starter
                'set_completion': True,  # From Starter
                'image_grid_view': True,  # From Starter
                'bulk_operations': True,  # From Starter
                # PROFESSIONAL tier upgrades from STARTER
                'max_cards': 25000,  # Upgraded from 5,000
                'api_access': True,  # NEW in Professional
                'custom_reports': True,  # NEW in Professional
                'automated_pricing': True,  # NEW in Professional
                'inventory_alerts': True,  # NEW in Professional
                'hover_tooltips': True,  # NEW in Professional
                'detailed_card_info': True,  # NEW in Professional
                'market_analytics': True,  # NEW in Professional
                # Still locked (upgrade to Enterprise for these)
                'multi_store': False,
                'white_label': False,
                'custom_integrations': False
            },
            'marketplace_features': {
                # ALL STARTER MARKETPLACE FEATURES (inherited)
                'can_list': True,  # From Starter
                'promotions': True,  # From Starter
                'bulk_upload': True,  # From Starter
                # PROFESSIONAL tier upgrades from STARTER
                'max_listings': 10000,  # Upgraded from 1,000
                'commission_rate': 6.0,  # Upgraded from 8% → 6%
                'featured_products': 25,  # Upgraded from 5
                'analytics': 'advanced',  # Upgraded from 'basic'
                'api_integration': True,  # NEW in Professional
                'priority_listing': True,  # NEW in Professional
                'custom_storefront': True,  # NEW in Professional
                'vendor_dashboard': True,  # NEW in Professional
                'sales_reports': True,  # NEW in Professional
                # Still locked
                'multi_location': False,
                'dedicated_manager': False
            },
            'support': 'priority_email',
            'annual_discount': 0.20  # 20% off if paid annually
        },
        
        'enterprise': {
            'name': 'Enterprise',
            'price': 199,
            'billing_period': 'monthly',
            'tier_level': 3,
            'desktop_features': {
                # ALL PROFESSIONAL FEATURES (inherited)
                **BASE_FEATURES,
                'advanced_filtering': True,  # From Starter
                'advanced_sorting': True,  # From Starter
                'price_tracking': True,  # From Starter
                'foil_tracking': True,  # From Starter
                'export_data': True,  # From Starter
                'statistics_panel': True,  # From Starter
                'set_completion': True,  # From Starter
                'image_grid_view': True,  # From Starter
                'bulk_operations': True,  # From Starter
                'api_access': True,  # From Professional
                'custom_reports': True,  # From Professional
                'automated_pricing': True,  # From Professional
                'inventory_alerts': True,  # From Professional
                'hover_tooltips': True,  # From Professional
                'detailed_card_info': True,  # From Professional
                'market_analytics': True,  # From Professional
                # ENTERPRISE tier upgrades from PROFESSIONAL
                'max_cards': 'unlimited',  # Upgraded from 25,000
                'multi_store': True,  # NEW in Enterprise
                'white_label': True,  # NEW in Enterprise
                'custom_integrations': True,  # NEW in Enterprise
                'advanced_automation': True,  # NEW in Enterprise
                'priority_support': True,  # NEW in Enterprise
                'custom_development': True,  # NEW in Enterprise
                'dedicated_training': True,  # NEW in Enterprise
                'migration_assistance': True,  # NEW in Enterprise
            },
            'marketplace_features': {
                # ALL PROFESSIONAL MARKETPLACE FEATURES (inherited)
                'can_list': True,  # From Starter
                'promotions': True,  # From Starter
                'bulk_upload': True,  # From Starter
                'api_integration': True,  # From Professional
                'priority_listing': True,  # From Professional
                'custom_storefront': True,  # From Professional
                'vendor_dashboard': True,  # From Professional
                'sales_reports': True,  # From Professional
                # ENTERPRISE tier upgrades from PROFESSIONAL
                'max_listings': 'unlimited',  # Upgraded from 10,000
                'commission_rate': 4.0,  # Upgraded from 6% → 4%
                'featured_products': 100,  # Upgraded from 25
                'analytics': 'enterprise',  # Upgraded from 'advanced'
                'multi_location': True,  # NEW in Enterprise
                'dedicated_account_manager': True,  # NEW in Enterprise
                'custom_reporting': True,  # NEW in Enterprise
                'sla_guarantee': True,  # NEW in Enterprise
                'quarterly_reviews': True,  # NEW in Enterprise
            },
            'support': 'phone_and_email',
            'annual_discount': 0.25  # 25% off if paid annually
        },
        
        'custom': {
            'name': 'Custom Enterprise',
            'price': 'contact_sales',
            'billing_period': 'custom',
            'desktop_features': {
                'custom': True,
                'everything': True
            },
            'marketplace_features': {
                'custom': True,
                'everything': True,
                'commission_rate': 'negotiable'
            },
            'support': 'dedicated',
            'features': 'All features + custom development'
        }
    }
    
    @classmethod
    def get_tier(cls, tier_name: str) -> Dict:
        """Get tier configuration"""
        return cls.TIERS.get(tier_name.lower(), cls.TIERS['free'])
    
    @classmethod
    def can_use_feature(cls, tier_name: str, feature_category: str, feature_name: str) -> bool:
        """Check if tier allows specific feature
        Features are cumulative - higher tiers inherit all lower tier features
        """
        tier = cls.get_tier(tier_name)
        
        if feature_category not in tier:
            return False
        
        feature_set = tier[feature_category]
        
        if feature_name not in feature_set:
            return False
        
        return feature_set[feature_name] is True or feature_set[feature_name] == 'unlimited'
    
    @classmethod
    def get_tier_level(cls, tier_name: str) -> int:
        """Get numeric tier level for comparison (0=free, 1=starter, 2=pro, 3=enterprise)"""
        tier = cls.get_tier(tier_name)
        return tier.get('tier_level', 0)
    
    @classmethod
    def compare_tiers(cls, tier_a: str, tier_b: str) -> int:
        """Compare two tiers
        Returns: -1 if tier_a < tier_b, 0 if equal, 1 if tier_a > tier_b
        """
        level_a = cls.get_tier_level(tier_a)
        level_b = cls.get_tier_level(tier_b)
        
        if level_a < level_b:
            return -1
        elif level_a > level_b:
            return 1
        else:
            return 0
    
    @classmethod
    def get_upgrade_path(cls, current_tier: str) -> List[Dict]:
        """Get list of available upgrades from current tier"""
        current_level = cls.get_tier_level(current_tier)
        upgrades = []
        
        for tier_name, tier_data in cls.TIERS.items():
            tier_level = tier_data.get('tier_level', 0)
            if tier_level > current_level:
                upgrades.append({
                    'tier': tier_name,
                    'name': tier_data['name'],
                    'price': tier_data.get('price', 0),
                    'level': tier_level
                })
        
        # Sort by level
        upgrades.sort(key=lambda x: x['level'])
        return upgrades
    
    @classmethod
    def get_new_features_in_tier(cls, tier_name: str) -> Dict:
        """Get features that are NEW in this tier (not inherited from lower tiers)"""
        tier = cls.get_tier(tier_name)
        tier_level = tier.get('tier_level', 0)
        
        if tier_level == 0:
            # Free tier - all features are "new"
            return tier
        
        # Get previous tier
        previous_tier_name = None
        for name, data in cls.TIERS.items():
            if data.get('tier_level', 0) == tier_level - 1:
                previous_tier_name = name
                break
        
        if not previous_tier_name:
            return tier
        
        previous_tier = cls.get_tier(previous_tier_name)
        new_features = {'desktop_features': {}, 'marketplace_features': {}}
        
        # Compare desktop features
        for feature, value in tier.get('desktop_features', {}).items():
            prev_value = previous_tier.get('desktop_features', {}).get(feature)
            # Feature is new if it didn't exist or was False/0 before and is True/number now
            if prev_value != value and (prev_value is False or prev_value == 0 or prev_value is None):
                new_features['desktop_features'][feature] = value
        
        # Compare marketplace features
        for feature, value in tier.get('marketplace_features', {}).items():
            prev_value = previous_tier.get('marketplace_features', {}).get(feature)
            if prev_value != value and (prev_value is False or prev_value == 0 or prev_value is None):
                new_features['marketplace_features'][feature] = value
        
        return new_features
    
    @classmethod
    def get_limit(cls, tier_name: str, feature_category: str, limit_name: str) -> any:
        """Get numeric limit for feature"""
        tier = cls.get_tier(tier_name)
        
        if feature_category not in tier:
            return 0
        
        feature_set = tier[feature_category]
        
        if limit_name not in feature_set:
            return 0
        
        value = feature_set[limit_name]
        return value if value != 'unlimited' else float('inf')


class LicenseManager:
    """Manages software licenses and subscription validation"""
    
    def __init__(self, license_file: str = 'mttgg_license.json'):
        self.license_file = license_file
        self.license_data = None
        self.validation_url = 'https://api.mttgg.com/v1/licenses/validate'
        self.activation_url = 'https://api.mttgg.com/v1/licenses/activate'
        
        # Offline grace period
        self.offline_grace_days = 30
        
        # Load existing license
        self.load_license()
    
    def generate_hardware_id(self) -> str:
        """Generate unique hardware fingerprint"""
        import platform
        import socket
        
        # Collect hardware info
        info = {
            'machine': platform.machine(),
            'processor': platform.processor(),
            'system': platform.system(),
            'node': platform.node(),
            'mac': self._get_mac_address()
        }
        
        # Create hash
        combined = json.dumps(info, sort_keys=True)
        hw_id = hashlib.sha256(combined.encode()).hexdigest()
        
        return hw_id
    
    def _get_mac_address(self) -> str:
        """Get MAC address of primary network interface"""
        import uuid
        mac = uuid.getnode()
        return ':'.join(['{:02x}'.format((mac >> i) & 0xff) for i in range(0, 48, 8)])
    
    def activate_license(self, license_key: str, email: str) -> Tuple[bool, str]:
        """Activate license with server"""
        hw_id = self.generate_hardware_id()
        
        payload = {
            'license_key': license_key,
            'email': email,
            'hardware_id': hw_id,
            'app_version': '2.0',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            response = requests.post(self.activation_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Save license locally
                self.license_data = {
                    'license_key': license_key,
                    'email': email,
                    'hardware_id': hw_id,
                    'tier': data['tier'],
                    'activated_at': datetime.now().isoformat(),
                    'expires_at': data['expires_at'],
                    'last_validated': datetime.now().isoformat(),
                    'status': 'active'
                }
                
                self.save_license()
                return True, f"License activated! Tier: {data['tier']}"
            else:
                return False, f"Activation failed: {response.json().get('error')}"
                
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to license server. Check internet connection."
        except Exception as e:
            return False, f"Activation error: {str(e)}"
    
    def validate_license(self, force_online: bool = False) -> Tuple[bool, str, str]:
        """Validate license (online or offline)
        Returns: (is_valid, tier, message)
        """
        if not self.license_data:
            return False, 'free', "No license found. Running in trial mode."
        
        # Check if expired
        if 'expires_at' in self.license_data:
            expires = datetime.fromisoformat(self.license_data['expires_at'])
            if datetime.now() > expires:
                return False, 'free', "License expired. Please renew subscription."
        
        # Check hardware ID
        current_hw = self.generate_hardware_id()
        if current_hw != self.license_data.get('hardware_id'):
            return False, 'free', "License hardware mismatch. Please reactivate."
        
        # Online validation
        last_validated = datetime.fromisoformat(self.license_data.get('last_validated', '2000-01-01'))
        days_since_validation = (datetime.now() - last_validated).days
        
        if force_online or days_since_validation > 7:
            # Try online validation
            online_valid, message = self._validate_online()
            
            if online_valid:
                return True, self.license_data['tier'], "License valid (verified online)"
            elif days_since_validation < self.offline_grace_days:
                # Allow offline grace period
                return True, self.license_data['tier'], f"License valid (offline mode, {self.offline_grace_days - days_since_validation} days remaining)"
            else:
                return False, 'free', "License validation required. Please connect to internet."
        
        # Offline validation OK
        return True, self.license_data['tier'], "License valid (offline)"
    
    def _validate_online(self) -> Tuple[bool, str]:
        """Validate license with server"""
        try:
            payload = {
                'license_key': self.license_data['license_key'],
                'hardware_id': self.license_data['hardware_id'],
                'email': self.license_data['email']
            }
            
            response = requests.post(self.validation_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Update license data
                self.license_data['last_validated'] = datetime.now().isoformat()
                self.license_data['status'] = data['status']
                self.license_data['tier'] = data['tier']
                self.license_data['expires_at'] = data['expires_at']
                
                self.save_license()
                return True, "License validated successfully"
            else:
                return False, f"Validation failed: {response.json().get('error')}"
                
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to validation server"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def save_license(self):
        """Save license data to file"""
        with open(self.license_file, 'w') as f:
            json.dump(self.license_data, f, indent=2)
    
    def load_license(self):
        """Load license data from file"""
        if os.path.exists(self.license_file):
            try:
                with open(self.license_file, 'r') as f:
                    self.license_data = json.load(f)
            except Exception as e:
                print(f"Error loading license: {e}")
                self.license_data = None
    
    def deactivate_license(self) -> Tuple[bool, str]:
        """Deactivate license (for transfer to new machine)"""
        if not self.license_data:
            return False, "No active license"
        
        try:
            payload = {
                'license_key': self.license_data['license_key'],
                'hardware_id': self.license_data['hardware_id']
            }
            
            response = requests.post(
                'https://api.mttgg.com/v1/licenses/deactivate',
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                # Remove local license
                if os.path.exists(self.license_file):
                    os.remove(self.license_file)
                self.license_data = None
                return True, "License deactivated successfully"
            else:
                return False, response.json().get('error')
                
        except Exception as e:
            return False, f"Deactivation error: {str(e)}"
    
    def get_license_info(self) -> Dict:
        """Get current license information"""
        if not self.license_data:
            return {
                'tier': 'free',
                'status': 'trial',
                'trial_days_remaining': 14
            }
        
        tier_info = SubscriptionTier.get_tier(self.license_data['tier'])
        
        expires = datetime.fromisoformat(self.license_data['expires_at'])
        days_remaining = (expires - datetime.now()).days
        
        return {
            'tier': self.license_data['tier'],
            'tier_name': tier_info['name'],
            'status': self.license_data['status'],
            'email': self.license_data['email'],
            'activated_at': self.license_data['activated_at'],
            'expires_at': self.license_data['expires_at'],
            'days_remaining': days_remaining,
            'last_validated': self.license_data['last_validated'],
            'features': tier_info
        }


class FeatureGate:
    """Control feature access based on subscription tier"""
    
    def __init__(self, license_manager: LicenseManager):
        self.license_manager = license_manager
        self.current_tier = 'free'
        self.update_tier()
    
    def update_tier(self):
        """Update current tier from license"""
        is_valid, tier, message = self.license_manager.validate_license()
        self.current_tier = tier if is_valid else 'free'
    
    def check_feature(self, category: str, feature: str) -> bool:
        """Check if current tier has access to feature"""
        return SubscriptionTier.can_use_feature(self.current_tier, category, feature)
    
    def get_limit(self, category: str, limit: str) -> any:
        """Get limit value for current tier"""
        return SubscriptionTier.get_limit(self.current_tier, category, limit)
    
    def require_feature(self, category: str, feature: str, action_name: str = "this action") -> bool:
        """Check feature and show upgrade prompt if not available"""
        if not self.check_feature(category, feature):
            self.show_upgrade_prompt(action_name, category, feature)
            return False
        return True
    
    def show_upgrade_prompt(self, action_name: str, category: str, feature: str):
        """Show prompt to upgrade subscription"""
        # This will be integrated into the GUI
        print(f"\n🔒 Upgrade Required")
        print(f"'{action_name}' requires a higher subscription tier.")
        print(f"Feature: {category} → {feature}")
        print(f"Current tier: {self.current_tier}")
        print(f"\nUpgrade to unlock this feature!")
        print(f"Visit: https://mttgg.com/pricing")
    
    def check_limit(self, category: str, limit_name: str, current_value: int) -> Tuple[bool, any]:
        """Check if current value is within tier limit
        Returns: (within_limit, limit_value)
        """
        limit = self.get_limit(category, limit_name)
        within_limit = current_value < limit
        return within_limit, limit


# Testing
if __name__ == "__main__":
    print("🔐 MTTGG Subscription & Licensing System")
    print("=" * 50)
    
    # Show all tiers
    print("\n📋 Available Subscription Tiers:\n")
    
    for tier_name, tier_data in SubscriptionTier.TIERS.items():
        print(f"{'='*50}")
        print(f"🎫 {tier_data['name'].upper()} - ${tier_data.get('price', 'Custom')}/month")
        print(f"{'='*50}")
        
        if 'desktop_features' in tier_data and isinstance(tier_data['desktop_features'], dict):
            print("\n📱 Desktop Features:")
            for feature, enabled in tier_data['desktop_features'].items():
                icon = "✅" if enabled else "❌"
                print(f"  {icon} {feature}: {enabled}")
        
        if 'marketplace_features' in tier_data and isinstance(tier_data['marketplace_features'], dict):
            print("\n🏪 Marketplace Features:")
            for feature, value in tier_data['marketplace_features'].items():
                if isinstance(value, bool):
                    icon = "✅" if value else "❌"
                    print(f"  {icon} {feature}")
                else:
                    print(f"  • {feature}: {value}")
        
        print(f"\n💬 Support: {tier_data.get('support', 'N/A')}")
        print()
    
    # Test license manager
    print("\n🔧 Testing License Manager...")
    
    license_mgr = LicenseManager('test_license.json')
    
    # Generate hardware ID
    hw_id = license_mgr.generate_hardware_id()
    print(f"Hardware ID: {hw_id[:32]}...")
    
    # Test validation
    is_valid, tier, message = license_mgr.validate_license()
    print(f"\nValidation Result:")
    print(f"  Valid: {is_valid}")
    print(f"  Tier: {tier}")
    print(f"  Message: {message}")
    
    # Test feature gate
    print("\n🚪 Testing Feature Gates...")
    
    gate = FeatureGate(license_mgr)
    
    # Test various features
    tests = [
        ('desktop_features', 'advanced_filtering', 'Advanced Filtering'),
        ('desktop_features', 'api_access', 'API Access'),
        ('marketplace_features', 'can_list', 'Marketplace Listing'),
        ('desktop_features', 'multi_store', 'Multi-Store Management')
    ]
    
    for category, feature, name in tests:
        has_access = gate.check_feature(category, feature)
        icon = "✅" if has_access else "🔒"
        print(f"  {icon} {name}: {'Allowed' if has_access else 'UPGRADE REQUIRED'}")
    
    # Test limits
    print("\n📊 Testing Limits...")
    
    max_cards = gate.get_limit('desktop_features', 'max_cards')
    max_listings = gate.get_limit('marketplace_features', 'max_listings')
    
    print(f"  Max Cards: {max_cards}")
    print(f"  Max Marketplace Listings: {max_listings}")
    
    print("\n✅ Subscription system ready!")
