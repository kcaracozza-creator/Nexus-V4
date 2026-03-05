"""
NEXUS Box Consolidation System
When boxes drop below 50%, consolidate into fuller boxes
"""

from typing import Dict, List, Tuple
from datetime import datetime


class BoxConsolidator:
    """
    Handles box consolidation when inventory drops below threshold
    """
    
    CONSOLIDATION_THRESHOLD = 0.50  # 50% = 500 cards
    CARDS_PER_BOX = 1000
    
    def __init__(self, library_system):
        """
        Args:
            library_system: NexusLibrarySystem instance
        """
        self.library = library_system
    
    def get_boxes_needing_consolidation(self) -> List[Dict]:
        """
        Find all boxes below 50% capacity
        
        Returns:
            List of box dicts sorted by card count (lowest first)
        """
        flagged = []
        threshold = int(self.CARDS_PER_BOX * self.CONSOLIDATION_THRESHOLD)
        
        for box_id, cards in self.library.box_inventory.items():
            count = len(cards)
            if 0 < count <= threshold:  # Has cards but below 50%
                flagged.append({
                    'box_id': box_id,
                    'card_count': count,
                    'fill_percent': (count / self.CARDS_PER_BOX) * 100,
                    'cards': cards
                })
        
        # Sort by card count (lowest first - empty these first)
        flagged.sort(key=lambda x: x['card_count'])
        return flagged
    
    def find_consolidation_target(self, source_box_id: str, cards_to_move: int) -> str:
        """
        Find the best box to consolidate INTO
        
        Logic: Find box with most cards that still has room for the incoming cards
        
        Args:
            source_box_id: Box we're moving FROM
            cards_to_move: How many cards need a new home
            
        Returns:
            Target box_id or None if no suitable box found
        """
        best_target = None
        best_count = 0
        
        for box_id, cards in self.library.box_inventory.items():
            if box_id == source_box_id:
                continue
                
            count = len(cards)
            available_space = self.CARDS_PER_BOX - count
            
            # Must have room for all incoming cards
            if available_space >= cards_to_move:
                # Prefer the box with most cards (keep boxes full)
                if count > best_count:
                    best_count = count
                    best_target = box_id
        
        return best_target
    
    def generate_consolidation_plan(self) -> List[Dict]:
        """
        Generate a full consolidation plan for all flagged boxes
        
        Returns:
            List of consolidation tasks
        """
        flagged = self.get_boxes_needing_consolidation()
        
        if not flagged:
            return []
        
        plan = []
        
        for source in flagged:
            source_id = source['box_id']
            cards_to_move = source['card_count']
            
            target_id = self.find_consolidation_target(source_id, cards_to_move)
            
            if target_id:
                target_current = len(self.library.box_inventory[target_id])
                
                plan.append({
                    'action': 'consolidate',
                    'source_box': source_id,
                    'target_box': target_id,
                    'cards_to_move': cards_to_move,
                    'target_current_count': target_current,
                    'target_after_count': target_current + cards_to_move,
                    'new_call_number_start': f"{target_id}-{target_current + 1:04d}",
                    'source_becomes': 'empty'
                })
        
        return plan
    
    def generate_move_list(self, source_box_id: str, target_box_id: str) -> List[Dict]:
        """
        Generate detailed move list for consolidation task
        
        Args:
            source_box_id: Box moving FROM
            target_box_id: Box moving TO
            
        Returns:
            List of individual card moves
        """
        source_cards = self.library.box_inventory.get(source_box_id, [])
        target_current = len(self.library.box_inventory.get(target_box_id, []))
        
        moves = []
        new_position = target_current + 1
        
        for card in source_cards:
            old_call = card.get('call_number', f"{source_box_id}-????")
            new_call = f"{target_box_id}-{new_position:04d}"
            
            moves.append({
                'card_name': card.get('name', 'Unknown'),
                'old_call_number': old_call,
                'new_call_number': new_call,
                'old_box': source_box_id,
                'new_box': target_box_id,
                'new_position': new_position
            })
            
            new_position += 1
        
        return moves
    
    def print_move_list(self, source_box_id: str, target_box_id: str) -> str:
        """
        Generate printable move list for shop staff
        
        Returns:
            Formatted string ready for printing
        """
        moves = self.generate_move_list(source_box_id, target_box_id)
        
        output = []
        output.append("=" * 60)
        output.append("NEXUS BOX CONSOLIDATION - MOVE LIST")
        output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        output.append("=" * 60)
        output.append("")
        output.append(f"FROM: Box {source_box_id} ({len(moves)} cards)")
        output.append(f"TO:   Box {target_box_id}")
        output.append("")
        output.append("-" * 60)
        output.append(f"{'□':<3} {'Card Name':<30} {'Old':<10} {'New':<10}")
        output.append("-" * 60)
        
        for move in moves:
            output.append(
                f"{'□':<3} {move['card_name'][:28]:<30} "
                f"{move['old_call_number']:<10} {move['new_call_number']:<10}"
            )
        
        output.append("-" * 60)
        output.append(f"TOTAL CARDS TO MOVE: {len(moves)}")
        output.append("")
        output.append("Instructions:")
        output.append("1. Pull cards from source box in order")
        output.append("2. Place in target box at new positions")
        output.append("3. Check off each card as moved")
        output.append("4. Click 'Complete Consolidation' when done")
        output.append("=" * 60)
        
        return "\n".join(output)
    
    def execute_consolidation(self, source_box_id: str, target_box_id: str) -> Dict:
        """
        Actually perform the consolidation in the database
        
        Args:
            source_box_id: Box moving FROM
            target_box_id: Box moving TO
            
        Returns:
            Result dict with stats
        """
        moves = self.generate_move_list(source_box_id, target_box_id)
        
        if not moves:
            return {'success': False, 'error': 'No cards to move'}
        
        # Update each card's call number and location
        for move in moves:
            old_call = move['old_call_number']
            new_call = move['new_call_number']
            card_name = move['card_name']
            
            # Update card_locations
            if old_call in self.library.card_locations:
                del self.library.card_locations[old_call]
            self.library.card_locations[new_call] = card_name
        
        # Move cards in box_inventory
        source_cards = self.library.box_inventory[source_box_id].copy()
        
        # Update call numbers on the card objects
        target_current = len(self.library.box_inventory[target_box_id])
        for i, card in enumerate(source_cards):
            card['call_number'] = f"{target_box_id}-{target_current + i + 1:04d}"
            card['position'] = target_current + i + 1
            card['consolidated_from'] = source_box_id
            card['consolidated_date'] = datetime.now().isoformat()
        
        # Add to target box
        self.library.box_inventory[target_box_id].extend(source_cards)
        
        # Clear source box
        self.library.box_inventory[source_box_id] = []
        
        # Update library data
        if source_box_id in self.library.library_data:
            self.library.library_data[source_box_id]['status'] = 'empty'
            self.library.library_data[source_box_id]['current_count'] = 0
        
        if target_box_id in self.library.library_data:
            self.library.library_data[target_box_id]['current_count'] = len(
                self.library.box_inventory[target_box_id]
            )
        
        # Save changes
        self.library._save_library()
        
        return {
            'success': True,
            'cards_moved': len(moves),
            'source_box': source_box_id,
            'target_box': target_box_id,
            'target_new_total': len(self.library.box_inventory[target_box_id]),
            'source_status': 'empty',
            'timestamp': datetime.now().isoformat()
        }
    
    def get_consolidation_summary(self) -> Dict:
        """
        Get overview of consolidation status
        
        Returns:
            Summary dict
        """
        flagged = self.get_boxes_needing_consolidation()
        plan = self.generate_consolidation_plan()
        
        total_boxes = len(self.library.box_inventory)
        total_cards = sum(len(cards) for cards in self.library.box_inventory.values())
        
        return {
            'total_boxes': total_boxes,
            'total_cards': total_cards,
            'boxes_below_threshold': len(flagged),
            'consolidation_tasks': len(plan),
            'flagged_boxes': [f['box_id'] for f in flagged],
            'potential_boxes_freed': len([p for p in plan if p['source_becomes'] == 'empty']),
            'plan': plan
        }


# Example usage and integration with NexusLibrarySystem
def add_consolidation_to_library_system():
    """
    Add these methods to NexusLibrarySystem class
    """
    code = '''
    # Add to NexusLibrarySystem.__init__:
    self.consolidator = BoxConsolidator(self)
    
    # Add these methods to NexusLibrarySystem:
    
    def check_consolidation_needed(self) -> List[Dict]:
        """Check if any boxes need consolidation"""
        return self.consolidator.get_boxes_needing_consolidation()
    
    def get_consolidation_plan(self) -> List[Dict]:
        """Get full consolidation plan"""
        return self.consolidator.generate_consolidation_plan()
    
    def print_consolidation_task(self, source_box: str, target_box: str) -> str:
        """Print move list for a consolidation task"""
        return self.consolidator.print_move_list(source_box, target_box)
    
    def execute_consolidation(self, source_box: str, target_box: str) -> Dict:
        """Execute a consolidation task"""
        return self.consolidator.execute_consolidation(source_box, target_box)
    
    def get_consolidation_summary(self) -> Dict:
        """Get consolidation status overview"""
        return self.consolidator.get_consolidation_summary()
    '''
    return code


# Demo
if __name__ == "__main__":
    print("=" * 60)
    print("NEXUS BOX CONSOLIDATION SYSTEM")
    print("=" * 60)
    print()
    print("Features:")
    print("- Flags boxes below 50% capacity")
    print("- Finds best target box to consolidate into")
    print("- Generates printable move lists")
    print("- Updates call numbers sequentially")
    print("- Marks emptied boxes for reuse")
    print()
    print("Example:")
    print("  DC: 500 cards (DC-0001 to DC-0500)")
    print("  FJ: 300 cards")
    print()
    print("  After consolidation:")
    print("  DC: 800 cards (DC-0001 to DC-0800)")
    print("  FJ: EMPTY (available for reuse)")
    print()
    print("Integration:")
    print("  from consolidation_system import BoxConsolidator")
    print("  consolidator = BoxConsolidator(library_system)")
    print("  plan = consolidator.generate_consolidation_plan()")
    print("  consolidator.execute_consolidation('FJ', 'DC')")
    print("=" * 60)
