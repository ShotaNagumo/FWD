from pathlib import Path

from fwdnagaoka.main import FwdNagaoka
from fwdutil import logger_initializer

if __name__ == "__main__":
    logconfig_file_path = Path(__file__).parents[2] / "config" / "log_format.yaml"
    logger_initializer.initialize(logconfig_file_path)
    nagaoka = FwdNagaoka()
