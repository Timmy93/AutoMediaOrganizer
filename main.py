import grp
import logging
import os
import pwd
import time
from datetime import datetime
import schedule
from src.MediaOrganizer import MediaOrganizer
from src.Tools import reload_generic_config, config_dir, MissingConfigException


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

        uid, gid = os.getuid(), os.getgid()
        user = pwd.getpwuid(uid).pw_name
        group = grp.getgrgid(gid).gr_name

        print(f"Running as {user}:{group} ({uid}:{gid})")
        logger.info(f"Running as {user}:{group} ({uid}:{gid})")

        organizer = MediaOrganizer(config)
        organizer.setup_db()
    except MissingConfigException as exc:
        print(f"Cannot load config - Error: {exc}")
        logging.error(f"Cannot load config - Error: {exc}")
        exit()
    except Exception as exc:
        print(f"Critical error during startup: {exc}")
        logging.exception(f"Critical error during startup: {exc}")
        exit()

    organizer.scan_and_organize()

    # Funzione wrapper per il logging
    def scheduled_scan():
        try:
            logger.info(f"Starting scheduled scan at {datetime.now()}")
            organizer.scan_and_organize()
            logger.info(f"Scan completed at {datetime.now()}")
        except Exception as exc:
            logger.exception(f"Error during scheduled scan: {exc}")

    # Configurazione schedule
    SCAN_INTERVAL_HOURS = config.get('scan', {}).get('frequency_minutes')  # Modifica questo valore

    # Esegui subito il primo scan
    logger.info("Running initial scan...")
    scheduled_scan()

    if SCAN_INTERVAL_HOURS is None:
        logger.warning("Scan interval not set in configuration. Scheduled scans will not be set up.")
        print("Scan interval not set in configuration. Scheduled scans will not be set up.")
        return
    else:
        # Programma gli scan successivi
        schedule.every(SCAN_INTERVAL_HOURS).minutes.do(scheduled_scan)
        logger.info(f"Scheduled scans every {SCAN_INTERVAL_HOURS} hours")

        # Loop principale
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Controlla ogni minuto
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user (Ctrl+C)")
            print("\nScheduler stopped by user")

if __name__ == '__main__':
    main()