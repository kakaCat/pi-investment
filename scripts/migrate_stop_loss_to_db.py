#!/usr/bin/env python3
"""
Migrate stop loss rules from JSON file to database.

This script reads existing stop loss rules from the JSON file
(.pi-invest/stop_loss_rules.json) and migrates them to the
stop_loss_rules table in the database.
"""

import json
import os
import sys
from pathlib import Path

# Add quant to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'quant'))

from quantsys.data.db import Database
from quantsys.db.dao import StopLossRuleDAO


def migrate_stop_loss_rules():
    """Migrate stop loss rules from JSON to database."""

    # Path to JSON file (in project directory)
    json_file = Path(__file__).parent.parent / '.pi-invest' / 'stop_loss_rules.json'

    if not json_file.exists():
        print(f"JSON file not found: {json_file}")
        print("No data to migrate.")
        return

    # Read JSON data
    print(f"Reading data from {json_file}...")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rules = data.get('rules', [])
    print(f"Found {len(rules)} rules to migrate")

    if not rules:
        print("No rules to migrate.")
        return

    # Connect to database
    print("Connecting to database...")
    db = Database()
    dao = StopLossRuleDAO(db)

    # Migrate each rule
    migrated = 0
    skipped = 0
    errors = 0

    for rule in rules:
        rule_id = rule.get('id')
        symbol = rule.get('symbol')

        if not rule_id or not symbol:
            print(f"Skipping invalid rule: {rule}")
            skipped += 1
            continue

        # Check if rule already exists
        existing = dao.get_rule(rule_id)
        if existing:
            print(f"Rule {rule_id} ({symbol}) already exists, skipping")
            skipped += 1
            continue

        try:
            # Create rule in database
            dao.create_rule(
                rule_id=rule_id,
                symbol=symbol,
                name=rule.get('name', f"{symbol}止损"),
                rule_type=rule.get('type', 'fixed_percent'),
                stop_loss_percent=rule.get('stopLossPercent') or rule.get('triggerPercent'),
                trailing_percent=rule.get('trailingPercent'),
                atr_multiplier=rule.get('atrMultiplier'),
                status=rule.get('status', 'active')
            )
            print(f"✓ Migrated rule {rule_id} ({symbol})")
            migrated += 1
        except Exception as e:
            print(f"✗ Error migrating rule {rule_id} ({symbol}): {e}")
            errors += 1

    # Summary
    print("\n" + "="*60)
    print("Migration Summary:")
    print(f"  Total rules in JSON: {len(rules)}")
    print(f"  Successfully migrated: {migrated}")
    print(f"  Skipped (already exist): {skipped}")
    print(f"  Errors: {errors}")
    print("="*60)

    if migrated > 0:
        print(f"\n✓ Migration completed successfully!")
        print(f"\nYou can now safely backup or remove the JSON file:")
        print(f"  {json_file}")
    elif skipped == len(rules):
        print(f"\n✓ All rules already exist in database, no migration needed.")
    else:
        print(f"\n⚠ Migration completed with errors.")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(migrate_stop_loss_rules())
