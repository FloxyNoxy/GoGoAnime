import json
import io
import os
import re
import shutil
import time
import datetime
from backend import *

# Create a folder for logs if it doesn't exist
log_folder = 'zzz_logs'
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

# Get the current date and time
current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Construct the filename with the current date and time inside the log folder
log_filename = os.path.join(log_folder, f"app_{current_time}.log")

# Configure logging with the constructed filename
logging.basicConfig(
    level=logging.INFO,
    filename=log_filename,
    filemode="w",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

OK = f"{Fore.RESET}[{Fore.GREEN}+{Fore.RESET}] "
ERR = f"{Fore.RESET}[{Fore.RED}-{Fore.RESET}] "
IN = f"{Fore.RESET}[{Fore.LIGHTBLUE_EX}>{Fore.RESET}] "

def get_corrected_url(original_url, url_exceptions):
    """Checks and corrects the URL if any exception applies."""
    for wrong_part, correct_part in url_exceptions.items():
        if wrong_part in original_url:
            original_url = original_url.replace(wrong_part, correct_part)
    return original_url


def main():
    dh = load_download_history()
    config = config_check()
    # retryLimit = config.get("DownloadRetries")
    url_exceptions = config.get("URLExceptions", {})
    tempdownloader = GogoAnime(
                config,
                1,
                config.get("CLIQuality"),
                config.get("CLIDownloadLocation"),
                1,
                1,
                1,
                config.get("CLIDownloadLocation"),
            )
    list = tempdownloader.get_show_from_bookmark()

    for ep in list:
        if read_download_history(ep, dh):
            showName = ep["showName"] + " - " + str(ep["latestEpisode"])
            print(f"{IN}{showName} already downloaded")
        else:
            show = ep["showName"]
            episode = ep["latestEpisode"]
            folder = determine_folder(show)
            if not os.path.exists(folder):
                os.makedirs(folder)
            downloader = GogoAnime(
                config,
                show,
                config.get("CLIQuality"),
                folder,
                1,
                episode,
                episode,
                show,
            )
            print(
                f"{IN}Scraping DL for "
                + ep["showName"]
                + " Ep "
                + str(ep["latestEpisode"])
            )
            episodes = [episode]
            corrected_url = get_corrected_url(ep["downloadURL"], url_exceptions)
            link = [downloader.get_download_link(corrected_url)]
            if None not in link:
                downloader.file_downloader(link, episodes)

            retry_limit = 3
            while retry_limit > 0:
                all_files = check_downloads(show, folder, episode, episode)
                if all_files is None:
                    print("The file was successfully downloaded and named.")
                    write_show_to_download_history(ep, dh)
                    retry_limit = 0
                else:

                    print("Download failed")
                    print("Retrying")
                    
                    retry_limit -= 1
                    episodes = [episode]
                    print(
                            f"{IN}Scraping DL for "
                            + ep["showName"]
                            + " Ep "
                            + str(ep["latestEpisode"])
                        )
                    corrected_url = get_corrected_url(ep["downloadURL"], url_exceptions)
                    link = [downloader.get_download_link(corrected_url)]
                    if None not in link:
                        downloader.file_downloader(link, episodes)
                    

            
if __name__ == "__main__":
    main()
