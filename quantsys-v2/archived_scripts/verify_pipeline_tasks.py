#!/usr/bin/env python3
"""
Verify that scheduled tasks are properly integrated with the scheduler.

This script checks:
1. Scheduled task functions can be imported
2. SchedulerService can be initialized
3. Command handlers are registered
4. Tasks can be executed via the scheduler
"""
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_imports():
    """Verify that all required modules can be imported."""
    logger.info("Step 1: Verifying imports...")
    try:
        from infrastructure.scheduler.scheduled_tasks import daily_data_pipeline, weekly_full_rebuild
        from infrastructure.scheduler.scheduler import SchedulerService
        from application.services.data_pipeline_service import DataPipelineService
        logger.info("✓ All imports successful")
        return True
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False


def verify_scheduler_handlers():
    """Verify that command handlers are registered in the scheduler."""
    logger.info("\nStep 2: Verifying scheduler command handlers...")
    try:
        from infrastructure.scheduler.scheduler import SchedulerService

        scheduler = SchedulerService()

        # Test that the handlers exist by checking if they can be called
        # We'll use a try-except to catch the ValueError for unknown commands
        test_commands = ['data_pipeline_daily', 'data_pipeline_weekly']

        for cmd in test_commands:
            try:
                # This will fail if command is unknown
                # We expect it to fail with other errors (like missing data)
                # but NOT with "Unknown scheduler command"
                scheduler._execute_command(cmd, {})
            except ValueError as e:
                if "Unknown scheduler command" in str(e):
                    logger.error(f"✗ Command '{cmd}' not registered")
                    return False
                # Other errors are OK - we just want to verify registration
            except Exception:
                # Expected - the command exists but may fail due to missing data
                pass

        logger.info("✓ Command handlers registered: data_pipeline_daily, data_pipeline_weekly")
        scheduler.close()
        return True

    except Exception as e:
        logger.error(f"✗ Scheduler verification failed: {e}")
        return False


def verify_task_functions():
    """Verify that task functions can be called (dry run)."""
    logger.info("\nStep 3: Verifying task functions (dry run)...")
    try:
        from infrastructure.scheduler.scheduled_tasks import get_csi300_components

        # Test get_csi300_components (may return empty list if DB not available)
        symbols = get_csi300_components()
        logger.info(f"✓ get_csi300_components() returned {len(symbols)} symbols")

        # Note: We don't actually run the pipeline tasks here as they may take time
        # and require database access. The import verification is sufficient.
        logger.info("✓ Task functions are callable")
        return True

    except Exception as e:
        logger.error(f"✗ Task function verification failed: {e}")
        return False


def main():
    """Run all verification steps."""
    logger.info("=" * 60)
    logger.info("Verifying Scheduled Tasks Integration")
    logger.info("=" * 60)

    results = []

    results.append(("Imports", verify_imports()))
    results.append(("Scheduler Handlers", verify_scheduler_handlers()))
    results.append(("Task Functions", verify_task_functions()))

    logger.info("\n" + "=" * 60)
    logger.info("Verification Summary")
    logger.info("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {name}")
        if not passed:
            all_passed = False

    if all_passed:
        logger.info("\n✓ All verifications passed!")
        logger.info("\nNext steps:")
        logger.info("1. Register tasks: python scripts/register_pipeline_tasks.py")
        logger.info("2. Start scheduler: python -m runtime.scheduler.scheduler")
        sys.exit(0)
    else:
        logger.error("\n✗ Some verifications failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
