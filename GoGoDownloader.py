from itertools import count
import re
import sys
import requests # type: ignore
import ctypes
import os
from backend import *
from bs4 import BeautifulSoup # type: ignore
from colorama import Fore # type: ignore
import logging

OK = f"{Fore.RESET}[{Fore.GREEN}+{Fore.RESET}] "
ERR = f"{Fore.RESET}[{Fore.RED}-{Fore.RESET}] "
IN = f"{Fore.RESET}[{Fore.LIGHTBLUE_EX}>{Fore.RESET}] "

try:
    ctypes.windll.kernel32.SetConsoleTitleW("GoGo Downloader")
except AttributeError:
    pass

def gogodownloader(config):
    CURRENT_DOMAIN = config["CurrentGoGoAnimeDomain"]
    os.system("cls" if os.name == "nt" else "clear")
    
    while True:
        print(f""" {Fore.LIGHTBLUE_EX}
         ______      ______                                      
        / ____/___  / ____/___                                   
       / / __/ __ \/ / __/ __ \                                  
      / /_/ / /_/ / /_/ / /_/ /                                  
      \__________/\____/\____/      __                __         
         / __ \____ _      ______  / /___  ____ _____/ /__  _____
        / / / / __ \ | /| / / __ \/ / __ \/ __ `/ __  / _ \/ ___/
       / /_/ / /_/ / |/ |/ / / / / / /_/ / /_/ / /_/ /  __/ /    
      /_____/\____/|__/|__/_/ /_/_/\____/\__,_/\__,_/\___/_/     
                          {Fore.RED}   
    """)
        while True:
            name = input(f"{IN}Enter anime name > ").lower()
            if "exit" in name:
                sys.exit()                
            logging.info("episode searched for " + name)
            if "-" in name:
                title = name.replace("-", " ").title().strip()
            else:
                title = name.title().strip()
            title = re.sub("[^A-Za-z0-9 ]+", "", title)
            source = f"https://anitaku.{CURRENT_DOMAIN}/category/{name}"
            with requests.get(source) as res:
                if res.status_code == 200:
                    soup = BeautifulSoup(res.content, "html.parser")
                    all_episodes = soup.find("ul", {"id": "episode_page"})
                    all_episodes = int(list(filter(None, "-".join(all_episodes.get_text().splitlines()).split("-")))[-1].strip())
                    break
                else:
                    print(f"{ERR}Error 404: Anime not found. Please try again.")
        
        while True:
            quality = input(f"{IN}Enter episode quality (1.SD/360P|2.SD/480P|3.HD/720P|4.FULLHD/1080P) > ")
            if quality in ["1", ""]:
                episode_quality = "360"
                break
            elif quality == "2":
                episode_quality = "480"
                break
            elif quality == "3":
                episode_quality = "720"
                break
            elif quality == "4":
                episode_quality = "1080"
                break
            else:
                print(f"{ERR}Invalid input. Please try again.")
            logging.info("quality selected " + episode_quality)
        
        print(f"{OK}Title: {Fore.LIGHTCYAN_EX}{title}")
        print(f"{OK}Episode/s: {Fore.LIGHTCYAN_EX}{all_episodes}")
        print(f"{OK}Quality: {Fore.LIGHTCYAN_EX}{episode_quality}")
        print(f"{OK}Link: {Fore.LIGHTCYAN_EX}{source}")

        folder = determine_folder(title)
        if not os.path.exists(folder):
            os.makedirs(folder)

        choice = "y"

        if all_episodes != 1:
            while True:
                choice = input(f"{IN}Do you want to download all episode? (y/n) > ").lower()
                if choice in ["y", "n"]:
                    break
                else:
                    print(f"{ERR}Invalid input. Please try again.")

        episode_start, episode_end = determine_episode_range(choice, all_episodes)
        gogo = GogoAnime(
            config,
            name,
            episode_quality,
            folder,
            all_episodes,
            episode_start,
            episode_end,
            title,
        )

        gogo.user_logged_in_check()
        source = f"https://anitaku.{CURRENT_DOMAIN}/{name}"
        with requests.get(source) as res:
            soup = BeautifulSoup(res.content, "html.parser")
            episode_zero = soup.find("h1", {"class": "entry-title"})  # value: 404

        if choice == "n" or episode_zero is not None:
            source = None

        episodes = list(range(episode_start, episode_end + 1))

        dl_links = []
        episode_links = gogo.get_links(episodes , source)
        print(f"{OK}Scraping Links")
        for link in episode_links:
            dl_links.append(gogo.get_download_link(link))

        gogo.file_downloader(dl_links, episodes)
        # print(f"Downloaded episode names: {result}")

        # if config["CleanUpFileName"]:
        #     rename_file(result, episode_start, title, folder)
        retry_limit = 3
        while retry_limit > 0:
            all_files = check_downloads(title, folder, episode_start, episode_end)
            if all_files is None:
                print("All files were successfully downloaded and named.")
                retry_limit = 0
            else:

                print("Some files are missing or incorrectly named.")
                print("Retrying")
                episode_links.clear()
                dl_links.clear()
                retry_limit -= 1
                episode_links = gogo.get_links(episodes , source)
                print(f"{OK}Scraping Links")
                for link in episode_links:
                    dl_links.append(gogo.get_download_link(link))
                gogo.file_downloader(dl_links, all_files)
            

        use_again = input(f"{IN}Do you want to use the app again? (y|n) > ").lower()
        if use_again == "y":
            os.system("cls" if os.name == "nt" else "clear")
        else:
            break

if __name__ == "__main__":
    config = config_check()
    gogodownloader(config)
