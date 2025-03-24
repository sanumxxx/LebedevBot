import json
import os
import random
import requests
from datetime import datetime, timedelta


class ProxyManager:
    def __init__(self):
        self.proxies_file = "proxies.json"
        self.proxies = self.load_proxies()
        self.user_agents = self.get_user_agents()
        self.last_update = None

    def load_proxies(self):
        """Загрузка списка прокси из JSON файла"""
        try:
            if os.path.exists(self.proxies_file):
                with open(self.proxies_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    return data.get("proxies", [])
            return []
        except Exception as e:
            print(f"Ошибка при загрузке прокси: {e}")
            return []

    def save_proxies(self, proxies):
        """Сохранение списка прокси в JSON файл"""
        try:
            with open(self.proxies_file, 'w', encoding='utf-8') as file:
                json.dump({"proxies": proxies, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                          file, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка при сохранении прокси: {e}")
            return False

    def update_proxies(self, force=False):
        """Обновление списка прокси из бесплатных источников"""
        # Проверяем, нужно ли обновлять (не чаще раза в день)
        if not force and self.last_update and datetime.now() - self.last_update < timedelta(days=1):
            print("Обновление прокси не требуется, последнее обновление:", self.last_update)
            return False

        proxies = []
        try:
            # Источник 1: Прокси из открытых API (примеры)
            sources = [
                "https://www.proxy-list.download/api/v1/get?type=http",
                "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
                "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
                "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
                "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
            ]

            for source in sources:
                try:
                    print(f"Получение прокси из источника: {source}")
                    response = requests.get(source, timeout=10)
                    if response.status_code == 200:
                        content = response.text
                        # Извлекаем прокси из содержимого
                        lines = content.strip().split('\n')
                        for line in lines:
                            if ':' in line:
                                ip, port = line.strip().split(':')
                                proxy = f"http://{ip}:{port}"
                                if self.check_proxy(proxy):
                                    proxies.append({
                                        "url": proxy,
                                        "type": "http",
                                        "source": source,
                                        "added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "working": True
                                    })
                except Exception as e:
                    print(f"Ошибка при получении прокси из {source}: {e}")

            # Сохраняем обновленный список
            if proxies:
                self.proxies = proxies
                self.save_proxies(proxies)
                self.last_update = datetime.now()
                print(f"Обновлено {len(proxies)} прокси")
                return True
            else:
                print("Не удалось получить новые прокси")
                return False

        except Exception as e:
            print(f"Ошибка при обновлении прокси: {e}")
            return False

    def check_proxy(self, proxy_url, timeout=5):
        """Проверка работоспособности прокси"""
        try:
            proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
            response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=timeout)
            return response.status_code == 200
        except:
            return False

    def verify_proxies(self):
        """Проверка всех прокси в списке"""
        working_proxies = []

        for proxy in self.proxies:
            try:
                if self.check_proxy(proxy["url"]):
                    proxy["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    proxy["working"] = True
                    working_proxies.append(proxy)
                else:
                    proxy["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    proxy["working"] = False
            except Exception as e:
                print(f"Ошибка при проверке прокси {proxy['url']}: {e}")
                proxy["working"] = False

        # Обновляем список только рабочими прокси
        self.proxies = working_proxies
        self.save_proxies(working_proxies)

        print(f"Проверено прокси: {len(self.proxies)} рабочих")
        return len(working_proxies)

    def get_random_proxy(self):
        """Получение случайного рабочего прокси"""
        working_proxies = [p for p in self.proxies if p.get("working", False)]
        if working_proxies:
            return random.choice(working_proxies)["url"]
        else:
            # Если нет рабочих прокси, попробуем обновить
            if self.update_proxies(force=True) and self.proxies:
                return random.choice(self.proxies)["url"]
        return None

    def get_user_agents(self):
        """Возвращает список популярных User-Agent строк для эмуляции разных браузеров"""
        return [
            # Chrome на Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",

            # Firefox на Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",

            # Edge на Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",

            # Chrome на macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

            # Safari на macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",

            # Chrome на Linux
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

            # Firefox на Linux
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",

            # Android Chrome
            "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.44 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",

            # iOS Safari
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        ]

    def get_random_user_agent(self):
        """Получение случайного User-Agent"""
        return random.choice(self.user_agents)

    def get_browser_profile(self):
        """Возвращает случайный профиль для браузера (прокси + User-Agent)"""
        return {
            "proxy": self.get_random_proxy(),
            "user_agent": self.get_random_user_agent()
        }

    def add_manual_proxy(self, proxy_url, proxy_type="http"):
        """Добавление прокси вручную"""
        if self.check_proxy(proxy_url):
            new_proxy = {
                "url": proxy_url,
                "type": proxy_type,
                "source": "manual",
                "added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "working": True
            }
            self.proxies.append(new_proxy)
            self.save_proxies(self.proxies)
            return True
        return False

    def get_proxy_stats(self):
        """Получение статистики по прокси"""
        return {
            "total": len(self.proxies),
            "working": len([p for p in self.proxies if p.get("working", False)]),
            "last_update": self.last_update.strftime("%Y-%m-%d %H:%M:%S") if self.last_update else None
        }