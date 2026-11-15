import os
import sys
import logging
from datetime import datetime, timezone
from src.config import AppConfig

def setup_logger(config: AppConfig, verbose: bool = False) -> logging.Logger:
    os.makedirs(config.log_dir, exist_ok=True)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = os.path.join(config.log_dir, f"{today_str}.log")

    logger = logging.getLogger("CyberNewsAgent")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Clear existing handlers to prevent duplication
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG if verbose else logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger