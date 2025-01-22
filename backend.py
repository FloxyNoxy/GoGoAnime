import hashlib
import io
import re
import threading
import requests
import json
import os
from bs4 import BeautifulSoup
from dataclasses import dataclass
from colorama import Fore
import subprocess
from threading import Semaphore
import logging
import datetime
import shutil
from tqdm import tqdm
import shlex
import concurrent.futures

# Create a folder for logs if it doesn't exist
log_folder = 'zzz_logs'
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

# Get the current date and time for logging
current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = os.path.join(log_folder, f"app_{current_time}.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename=log_filename,
    filemode="w",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Terminal output symbols
OK = f"{Fore.RESET}[{Fore.GREEN}+{Fore.RESET}] "
ERR = f"{Fore.RESET}[{Fore.RED}-{Fore.RESET}] "
IN = f"{Fore.RESET}[{Fore.LIGHTBLUE_EX}>{Fore.RESET}] "

# Global configurations
CONFIG = None
screenlock = Semaphore(value=1)

def config_check():
    """Check for config.json and validate required keys are set."""
    config_path = os.path.join(os.getcwd(), 'config.json')
    if not os.path.exists(config_path):
        logging.error("config.json not found")
        print("config.json file not found")
        exit(0)

    with open(config_path, "r") as f:
        config = json.load(f)[0]

    if not config.get("GoGoAnime_Username"):
        logging.error("GoGoAnime_Username not set in config.json")
        print("GoGoAnime_Username not set in config.json")
        exit(0)
    if not config.get("GoGoAnime_Password"):
        logging.error("GoGoAnime_Password not set in config.json")
        print("GoGoAnime_Password not set in config.json")
        exit(0)

    logging.info("Config loaded successfully")
    return config

# def move_file(file, shows, download_history, config):
#     """Move file to the correct directory based on the show's season."""
#     file_name = strip_name(file)
#     show_name, _, tail = file_name.partition('Episode ')
#     episode_number = tail.replace('.Mp4', '').strip()

#     try:
#         if episode_number and int(episode_number) < 10:
#             tail = tail.rjust(1 + len(tail), '0')
#     except ValueError:
#         logging.error('Failed to process episode number')
#         print('Failed to process episode number')

#     updated_file_name = f"{show_name}Episode {tail}"
#     source_file = os.path.join(os.getcwd(), updated_file_name)

#     season_folder_map = {
#         "2nd": "Season 2",
#         "3rd": "Season 3",
#         "season-2": "Season 2",
#         "season-3": "Season 3"
#     }
#     destination_folder = None

#     for key, value in season_folder_map.items():
#         if key in file:
#             updated_show_name, _, _ = file_name.partition(f" {key} ")
#             destination_folder = os.path.join(os.getcwd(), updated_show_name, value)
#             break

#     if not destination_folder:
#         destination_folder = os.path.join(os.getcwd(), show_name)

#     if config.get("FileException_AnimeName") in file:
#         updated_show_name, _, _ = file_name.partition(config.get("FileException_PartitionBy"))
#         destination_folder = os.path.join(os.getcwd(), updated_show_name + config.get("FileException_SeasonDir"))

#     destination_folder = destination_folder.rstrip()
#     if not os.path.exists(destination_folder):
#         os.makedirs(destination_folder)

#     try:
#         for ep in shows:
#             if not read_download_history(ep, download_history):
#                 write_show_to_download_history(ep, download_history)
#                 logging.info(f'Completed download for {ep}')
#         shutil.move(source_file, destination_folder)
#     except Exception as error:
#         logging.error(f'Failed to move file from: {source_file} to: {destination_folder}')
#         logging.error(f"Exception: {error}")
#         print(f'Failed to move file from: {source_file} to: {destination_folder}')
#         print(f"Exception: {error}")

def strip_name(filename: str) -> str:
    """Clean and format the filename."""
    directory, _, tail = filename.rpartition('/')
    clean_name = "".join(re.split(r"\(|\)|\[|\]", tail)[::2])
    clean_name = clean_name.replace("-", " ").title().strip()
    return directory + '/' + clean_name

# def rename_file(files, episode_start, title, folder):
    
#     for file in files:
#         base, ext = os.path.splitext(file)
#         episode_number = f"{episode_start:02d}"
#         new_name = f"{folder}/{title} - Episode {episode_number}{ext}"
#         episode_start += 1
#         # Check if the file exists before renaming
#         if not os.path.isfile(file):
#             print(f"File '{file}' does not exist.")
#             return

#         try:
#             # Rename the file
#             os.rename(file, new_name)
#         except Exception as e:
#             print(f"Failed to rename file: {e}")

def load_download_history():
    """Load the downloadHistory.json, create it if it doesn't exist."""
    history_file = "./downloadHistory.json"
    if not os.path.isfile(history_file):
        with io.open(history_file, "w") as db_file:
            db_file.write(json.dumps([]))
    with open(history_file, "r") as db_file:
        return json.load(db_file)

def write_show_to_download_history(show: dict, download_history: list):
    """Write the showName and latestEpisode to the downloadHistory.json file."""
    dh_filename = f"{show['showName']} - {show['latestEpisode']}"
    download_history.append(dh_filename)
    with io.open("./downloadHistory.json", "w") as db_file:
        json.dump(download_history, db_file)
    return download_history

def read_download_history(file_name_object: dict, download_history: list) -> bool:
    """Check if the show episode exists in the download history."""
    dh_filename = f"{file_name_object['showName']} - {file_name_object['latestEpisode']}"
    return dh_filename in download_history

def max_concurrent_downloads(max_conn: int) -> int:
    """Limit the maximum concurrent downloads to 6."""
    return min(max_conn, 6)

def truncate_filename(filename: str, max_length: int) -> str:
    """Truncate the filename if it exceeds the maximum length."""
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        hash_part = hashlib.md5(name.encode()).hexdigest()
        truncated_name = name[:max_length - len(ext) - len(hash_part) - 1] + '_' + hash_part
        return truncated_name + ext
    return filename

def determine_folder(title):
    """Determines the folder path based on the title and season."""
    config = config_check()
    season_exceptions = config.get("SeasonNameExceptions", {})
    for incorrect, correct in season_exceptions.items():
        if incorrect in title:
            title = correct
    
    if "2Nd" in title:
        title, _, _ = title.partition(' 2Nd')
        return os.path.join(os.getcwd(), title + '/Season 2')
    elif "3Rd" in title:
        title, _, _ = title.partition(' 3Rd')
        return os.path.join(os.getcwd(), title + '/Season 3')
    elif "4Th" in title:
        title, _, _ = title.partition(' 4Th')
        return os.path.join(os.getcwd(), title + '/Season 4')
    elif "5Th" in title:
        title, _, _ = title.partition(' 5Th')
        return os.path.join(os.getcwd(), title + '/Season 5')
    elif "6Th" in title:
        title, _, _ = title.partition(' 6Th')
        return os.path.join(os.getcwd(), title + '/Season 6')
    elif "7Th" in title:
        title, _, _ = title.partition(' 7Th')
        return os.path.join(os.getcwd(), title + '/Season 7')
    elif "8Th" in title:
        title, _, _ = title.partition(' 8Th')
        return os.path.join(os.getcwd(), title + '/Season 8')
    elif "Season 2" in title:
        title, _, _ = title.partition(' Season 2')
        return os.path.join(os.getcwd(), title + '/Season 2')
    elif "Season 3" in title:
        title, _, _ = title.partition(' Season 3')
        return os.path.join(os.getcwd(), title + '/Season 3')
    elif "Season 4" in title:
        title, _, _ = title.partition(' Season 4')
        return os.path.join(os.getcwd(), title + '/Season 4')
    elif "Season 5" in title:
        title, _, _ = title.partition(' Season 5')
        return os.path.join(os.getcwd(), title + '/Season 5')
    elif "Season 6" in title:
        title, _, _ = title.partition(' Season 6')
        return os.path.join(os.getcwd(), title + '/Season 6')
    elif "Season 7" in title:
        title, _, _ = title.partition(' Season 7')
        return os.path.join(os.getcwd(), title + '/Season 7')
    elif "Season 8" in title:
        title, _, _ = title.partition(' Season 8')
        return os.path.join(os.getcwd(), title + '/Season 8')
    else:
        return os.path.join(os.getcwd(), title + '/Season 1')

def determine_episode_range(choice, all_episodes):
    """Determines the range of episodes to download."""
    if choice == "n":
        while True:
            try:
                episode_start = int(input(f"{IN}Episode start > "))
                episode_end = int(input(f"{IN}Episode end > "))
                if episode_start <= 0 or episode_end <= 0:
                    CustomMessage(f"{ERR}episode_start or episode_end cannot be less than or equal to 0").print_error()
                elif episode_start > all_episodes or episode_end > all_episodes:
                    CustomMessage(f"{ERR}episode_start or episode_end cannot be more than {all_episodes}").print_error()
                elif episode_end < episode_start:
                    CustomMessage(f"{ERR}episode_end cannot be less than episode_start").print_error()
                else:
                    return episode_start, episode_end
            except ValueError:
                print(f"{ERR}Invalid input. Please try again.")
    return 1, all_episodes

def check_downloads(title, folder, episode_start, episode_end):
    """Check if all downloaded files match the expected naming pattern.

    Args:
        title (str): The title of the anime.
        folder (str): The folder where files are downloaded.
        total_episodes (int): Total number of episodes expected.

    Returns:
        bool: True if all files are correctly named, False otherwise.
    """
    expected_files = set()
    for episode in range(episode_start, episode_end + 1):
        # Format episode number with leading zero if necessary
        episode_number = f"{episode:02}"
        filename_pattern = f"{title} - Episode {episode_number}.mp4"
        expected_files.add(filename_pattern)

    # Get list of actual files in the folder
    actual_files = set()
    for file in os.listdir(folder):
        if file.endswith(".mp4"):
            file_size = os.path.getsize(f"{folder}/{file}")
            if file_size is 0:
                os.remove(f"{folder}/{file}")
            else:
                actual_files.add(file)
                

    # Compare expected and actual files
    missing_files = expected_files - actual_files
    missing_episodes = []
    if missing_files:
        episode_pattern = re.compile(r"Episode (\d{2})")
        for missing_file in missing_files:
            match = episode_pattern.search(missing_file)
            if match:
                missing_episodes.append(int(match.group(1)))
    else: 
        print(f"Missing episodes: {sorted(missing_episodes)}")
        return None

    # Return list of missing episode numbers
    return sorted(missing_episodes)


@dataclass(init=True)
class GogoAnime:
    config: object
    name: str
    episode_quality: str
    folder: str
    all_episodes: int
    episode_start: int
    episode_end: int
    title: str
    printed: bool = False

    def get_gogoanime_auth_cookie(self) -> str:
        session = requests.session()
        page = session.get(
            f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/login.html"
        )
        soup = BeautifulSoup(page.content, "html.parser")
        meta_path = soup.select('meta[name="csrf-token"]')
        csrf_token = meta_path[0].attrs["content"]

        url = f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/login.html"
        payload = f"email={self.config.get('GoGoAnime_Username')}&password={self.config.get('GoGoAnime_Password')}&_csrf={csrf_token}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
            "authority": "gogo-cdn.com",
            "referer": f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/",
            "content-type": "application/x-www-form-urlencoded",
        }
        session.headers = headers

        r = session.post(url, data=payload, headers=headers)

        if r.status_code == 200:
            return session.cookies.get_dict().get("auth")
        else:
            print("ldldl")

    def user_logged_in_check(self):
        page = requests.get(
            f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/one-piece-episode-1",
            cookies=dict(auth=GogoAnime.get_gogoanime_auth_cookie(self)),
        )
        soup = BeautifulSoup(page.content, "html.parser")
        loginCheck = soup(text=re.compile("Logout"))
        if len(loginCheck) == 0:
            raise Exception(
                "User is not logged in, make sure account has been activated"
            )

    def get_episodes(self):
        """Retrieve a list of episodes."""
        print(f"{IN}Retrieving episodes for: {self.name}")

        # Correct the gogoanime_id format before making the request
        title = self.title
        try:
            # Request from the first episode to the last, returning the list
            response = requests.get(
                f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/category/{title}"
            )
            soup = BeautifulSoup(response.content, "html.parser")
            items = soup.find_all("a", {"class": "episode-number"})
            episodes = []

            if items:
                for item in items:
                    ep_num = int(re.search(r'\d+', item.text).group())
                    episodes.append(
                        {
                            "Episode": ep_num,
                            "link": item.get("href"),
                            "skip": False,
                            "showName": self.name,
                            "quality": self.episode_quality,
                        }
                    )
            else:
                raise CustomMessage(f"{ERR}Episode links not found")
            return episodes
        except CustomMessage as msg:
            print(msg)
            logging.error(msg)
        except Exception as error:
            print(f"{ERR}An unexpected error occurred while retrieving episodes.")
            logging.error("An unexpected error occurred while retrieving episodes.")
            logging.error(f"Exception: {error}")
            return []
    
    def get_links(self, episodes=None, source=None):
        if source:
            source_ep = f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/{self.name}-episode-"
            episode_links = [f"{source_ep}{i}" for i in episodes] if episodes else [f"{source_ep}{i}" for i in range(self.episode_start, self.episode_end + 1)]
            episode_links.insert(0, source)
        else:
            source_ep = f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/{self.name}-episode-"
            episode_links = [f"{source_ep}{i}" for i in episodes] if episodes else [f"{source_ep}{i}" for i in range(self.episode_start, self.episode_end + 1)]
        return episode_links

    def get_download_link(self, url):
        page = requests.get(
            url,
            cookies=dict(auth=self.get_gogoanime_auth_cookie()),
        )
        quality_arr = ["1080", "720", "640", "480"]
        soup = BeautifulSoup(page.content, "html.parser")
        try:
            for link in soup.find_all("a", href=True, string=re.compile(self.episode_quality)):
                return link["href"]
            ep_num = url.rsplit("-", 1)[1]
            print(f"{self.episode_quality} not found for ep{ep_num} checking for next best")
            for q in quality_arr:
                for link in soup.find_all("a", href=True, string=re.compile(q)):
                    print(f"{q} found.")
                    return link["href"]
            raise CustomMessage(f"No matching download found for {url}.")
        except Exception as err:
            print(f"No matching download found for link: {url}")
        return None
            # raise CustomMessage(str(err))
        
    def get_show_from_bookmark(self):
        print(f"{IN}Loading shows from bookmarks")
        bookmarkList = []
        a = dict(auth=GogoAnime.get_gogoanime_auth_cookie(self))
        resp = requests.get(
            f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/user/bookmark",
            cookies=a,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("div", attrs={"class": "article_bookmark"})
        splitTableLines = table.text.split("Remove")
        for rows in splitTableLines:
            fullRow = " ".join(rows.split())
            if "Anime name" in fullRow:
                fullRow = fullRow.replace("Anime name Latest", "")
                splitRow = fullRow.split("Latest")
            elif fullRow == "Status":
                break
            else:
                fullRow = fullRow.replace("Status ", "")
                splitRow = fullRow.split("Latest")
            animeName = splitRow[0].strip().encode("ascii", "ignore").decode()
            animeName = re.sub("[^A-Za-z0-9 ]+", "", animeName)
            animeName = animeName.title().strip()
            animeDownloadName = animeName.replace(" ", "-").lower()
            episodeNum = splitRow[-1].split()[-1]
            with open("./config.json", "r") as f:
                CONFIG = json.load(f)
            for value in CONFIG:
                if 'LinkException_AnimeName' in value and 'LinkExceptionCorrection_Link' in value:
                    anime_name = value['LinkException_AnimeName']
                    anime_link = value['LinkExceptionCorrection_Link']
                    if anime_name in animeDownloadName:
                        animeDownloadName = anime_link
            try:
                bookmarkList.append(
                    {
                        "showName": animeName,
                        "latestEpisode": int(episodeNum),
                        "downloadURL": f"https://anitaku.{self.config.get('CurrentGoGoAnimeDomain')}/{animeDownloadName}-episode-{str(episodeNum)}",
                    }
                )
            except:
                logging.error("Invalid episode number - " + episodeNum + " for " + animeName)
                print("Invalid episode number - " + episodeNum + " for " + animeName)
        with open("bookmarkList.json", "w") as f:
            json.dump(bookmarkList, f)
        return bookmarkList

    

    def file_downloader(self, file_list: dict, episodes: list, overwrite_downloads: bool = None, max_workers: int = 1):
        if overwrite_downloads is None:
            overwrite = self.config.get("OverwriteDownloads")
        else:
            overwrite = overwrite_downloads

        max_workers = self.config.get("MaxConcurrentDownloads", max_workers)

        downloaded_files = []
        total_files = len(file_list)

        # if len(file_list) != len(episodes):
        #     raise ValueError("The number of files in file_list must match the number of episodes in the episodes list.")
        # Create a mapping of episode numbers to URLs
        episode_map = {episode: file for episode, file in zip(episodes, file_list)}

        summary_bar = tqdm(total=total_files, desc="Total Progress", ncols=100, unit="file", position=0)

        lock = threading.Lock()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            position = 1
            for episode_number, link in episode_map.items():
                if link:
                    # Pass episode number with the download task
                    future = executor.submit(download_file, link, self.folder, self.title, episode_number, summary_bar, lock, position)
                    futures[future] = episode_number
                    position += 1

            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        downloaded_files.append(result)
                except Exception as e:
                    logging.error(f"Error downloading file: {e}")

        summary_bar.close()

        return downloaded_files


def download_file(link, folder, title, episode_number, summary_bar, lock, position):
    inner_bar = tqdm(total=100, desc=f"Episode {episode_number}", position=position + 1, leave=False, ncols=100, unit="B", unit_scale=True, unit_divisor=1024)

    command = f"wget --content-disposition --progress=dot:giga -P {shlex.quote(folder)} {shlex.quote(link)}"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, universal_newlines=True)

    downloaded_filename = None
    try:
        for line in process.stderr:
            progress_match = re.search(r'(\d+)%', line)
            if progress_match:
                percentage = int(progress_match.group(1))
                inner_bar.n = percentage
                inner_bar.refresh()

            if "Saving to:" in line:
                downloaded_filename = line.split("‘")[1].split("’")[0].strip()

    finally:
        process.stdout.close()
        process.stderr.close()
        returncode = process.wait()
        inner_bar.close()

    if returncode == 0 and downloaded_filename:
        cleaned_filename = os.path.join(folder, downloaded_filename.replace("‘", "").replace("’", ""))
        if os.path.isfile(cleaned_filename):
            with lock:
                summary_bar.update(1)
            # Use the episode number to rename the file correctly
            new_name = f"{folder}/{title} - Episode {episode_number:02d}.mp4"
            os.rename(cleaned_filename, new_name)
            return new_name
        else:
            logging.error(f"File does not exist: {cleaned_filename}")
    else:
        logging.error(f"Failed to download {link}")

    with lock:
        summary_bar.update(1)
    return None


class CustomMessage(Exception):
    """Custom exception to handle specific error messages."""
    pass

def main():
    config = config_check()
    # Get inputs from the user
    name = input("Enter the anime name: ").strip()
    episode_quality = input("Enter the episode quality (e.g., 720p): ").strip()
    folder = input("Enter the folder to save episodes: ").strip()
    all_episodes = int(input("Download all episodes? (1 for Yes, 0 for No): "))
    episode_start = 0
    episode_end = 0
    if not all_episodes:
        episode_start = int(input("Enter the start episode number: ").strip())
        episode_end = int(input("Enter the end episode number: ").strip())
    title = name.lower().replace(" ", "-")

    downloader = GogoAnime(
        config=config,
        name=name,
        episode_quality=episode_quality,
        folder=folder,
        all_episodes=all_episodes,
        episode_start=episode_start,
        episode_end=episode_end,
        title=title,
    )

    try:
        episodes = downloader.get_episodes()
        if episodes:
            downloader.download_episodes(episodes, current_time)
        else:
            raise CustomMessage("No episodes were found for the specified title.")
    except CustomMessage as msg:
        print(msg)
        logging.error(msg)
    except Exception as e:
        print(f"{ERR}An unexpected error occurred in the main function.")
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
