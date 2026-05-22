#!/usr/bin/env python3
"""
VC Vetting Agent
Entrypoint script to initialize logging and run the VC classification CLI.
"""
import logging
import sys
from vc_vetter.config import Settings
from vc_vetter.cli import CLIRunner

# Set up clean file-based logging to ensure console outputs/progress bars remain uncluttered
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("vc_vetter.log", mode="w", encoding="utf-8")
    ]
)

# Suppress noisy logs from third-party libraries in the log file
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("vc_vetter")

def main():
    try:
        settings = Settings()
        runner = CLIRunner(settings)
        runner.run()
    except KeyboardInterrupt:
        print("\n\nExecution cancelled by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        logger.critical("Fatal exception in main execution loop", exc_info=True)
        print(f"\nFatal error occurred during execution: {e}")
        print("Please check 'vc_vetter.log' for detailed technical logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()
