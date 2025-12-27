import logging
import os

from src.MediaOrganizer import MissingConfigException, MediaOrganizer, config_dir, reload_generic_config, reload_scan_config


def initialize_log(config):
    """
    Initialize log file
    :return:
    """
    log_section = "log"
    packages_section = "Packages"
    log_file_field, default_log_file = "logFile",  "AutoMediaOrganizer.log"
    log_level_field, default_log_level = "logLevel", "DEBUG"
    filename = os.path.abspath(os.path.join(os.path.dirname(__file__), config_dir, config.get(log_section, {}).get(log_file_field, default_log_file)))
    log_level = config.get(log_section, {}).get(log_level_field, default_log_level)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(filename, mode="a"),
        ]
    )
    for package in config.get(packages_section, []):
        name = package.get('name')
        level = package.get('log_level', log_level)
        logging.getLogger(name).setLevel(level)
    logger = logging.getLogger("main")
    return logger

def main():
    try:
        # Load config
        config = reload_generic_config()
        logger = initialize_log(config)
        logger.info("Configuration loaded successfully.")
        organizer = MediaOrganizer(config)
    except MissingConfigException as exc:
        print(f"Cannot load config - Error: {exc}")
        logging.error(f"Cannot load config - Error: {exc}")
        exit()
    except Exception as exc:
        print(f"Critical error during startup: {exc}")
        logging.exception(f"Critical error during startup: {exc}")
        exit()

    organizer.scan_and_organize()

if __name__ == '__main__':
    main()