import json
import os
import time
import threading
import sys
import traceback
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
                               QTextEdit, QMessageBox, QInputDialog, QProgressBar, QLineEdit)
from PySide6.QtCore import Qt, QSize, Signal, Slot, QThread, QObject
from PySide6.QtGui import QColor, QPalette, QFont

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Импорт ProxyManager
from proxy_manager import ProxyManager


class SimpleGameBot:
    """Бот для управления аккаунтами и серверами браузерной игры"""

    def __init__(self):
        self.accounts_file = "game_accounts.json"
        self.accounts = self.load_accounts()
        self.game_url = "https://ru.mlgame.org/"
        self.drivers = {}
        # Инициализируем ProxyManager
        self.proxy_manager = ProxyManager()

    def load_accounts(self):
        """Загрузка аккаунтов из JSON файла"""
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r', encoding='utf-8') as file:
                    return json.load(file)
            return []
        except Exception as e:
            print(f"Ошибка при загрузке аккаунтов: {e}")
            return []

    def save_accounts(self):
        """Сохранение аккаунтов в JSON файл"""
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as file:
                json.dump(self.accounts, file, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка при сохранении аккаунтов: {e}")
            return False

    def create_driver(self, account, headless=False):
        """Создание WebDriver с нужными настройками"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")

            # Установка headless режима, если требуется
            if headless:
                chrome_options.add_argument("--headless")
                print(f"Запуск браузера в скрытом режиме для {account['username']}")

            # Настройка прокси, если указан
            if account.get('proxy'):
                chrome_options.add_argument(f'--proxy-server={account["proxy"]}')
                print(f"Используется прокси: {account['proxy']}")

            # Добавление случайного User-Agent из ProxyManager
            user_agent = self.proxy_manager.get_random_user_agent()
            chrome_options.add_argument(f'--user-agent={user_agent}')
            print(f"Используется User-Agent: {user_agent}")

            # Определение базового пути приложения
            import sys
            import os

            if getattr(sys, 'frozen', False):
                # Путь для скомпилированного приложения
                base_path = os.path.dirname(sys.executable)
            else:
                # Путь для разработки
                base_path = os.path.dirname(os.path.abspath(__file__))

            # Настройка на хранение кэша, cookie и т.д. для каждого аккаунта в отдельной папке
            user_data_dir = os.path.join(base_path, f"chrome_data/{account['username']}")
            os.makedirs(user_data_dir, exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

            # Настройка на игнорирование ошибок сертификатов
            chrome_options.add_argument("--ignore-certificate-errors")
            chrome_options.add_argument("--ignore-ssl-errors")

            # Отключаем логи WebDriver
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

            print("Инициализация ChromeDriver...")

            try:
                # Поиск chromedriver.exe в нескольких местах
                chromedriver_locations = [
                    os.path.join(base_path, "chromedriver.exe"),  # Рядом с exe
                    os.path.join(base_path, "driver", "chromedriver.exe"),  # В подпапке driver
                    os.path.join(os.path.dirname(base_path), "chromedriver.exe"),  # Уровнем выше от exe
                    "chromedriver.exe"  # В текущей рабочей директории
                ]

                driver_found = False
                for driver_path in chromedriver_locations:
                    if os.path.exists(driver_path):
                        print(f"Найден ChromeDriver по пути: {driver_path}")
                        service = Service(executable_path=driver_path)
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                        driver_found = True
                        break

                # Если драйвер не найден ни в одном из мест, пробуем использовать WebDriverManager
                if not driver_found:
                    print("ChromeDriver не найден в стандартных местах, использование WebDriver Manager...")
                    driver_path = ChromeDriverManager().install()
                    print(f"Установлен ChromeDriver по пути: {driver_path}")
                    service = Service(executable_path=driver_path)
                    driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as chrome_error:
                print(f"Ошибка при инициализации ChromeDriver: {chrome_error}")
                # Резервный вариант - базовый инициализатор
                print("Использование базового инициализатора...")
                driver = webdriver.Chrome(options=chrome_options)

            driver.implicitly_wait(5)
            return driver
        except Exception as e:
            print(f"Критическая ошибка при создании драйвера: {e}")
            return None

    def login_account(self, driver, account):
        """Вход в аккаунт через форму авторизации"""
        try:
            # Переходим на главную страницу
            driver.get(self.game_url)

            # Проверяем, нужно ли авторизоваться
            if "loginForm" in driver.page_source:
                print(f"Авторизация для аккаунта {account['username']}...")

                # Ожидание загрузки страницы логина
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )

                # Ввод логина и пароля
                username_field = driver.find_element(By.ID, "username")
                username_field.clear()
                username_field.send_keys(account["username"])

                password_field = driver.find_element(By.ID, "password")
                password_field.clear()
                password_field.send_keys(account["password"])

                # Установка флажка "входить автоматически"
                try:
                    remember_me = driver.find_element(By.ID, "rememberMe")
                    if not remember_me.is_selected():
                        remember_me.click()
                except:
                    pass

                # Нажатие кнопки входа
                login_button = driver.find_element(By.ID, "loginButton")
                login_button.click()

                # Ожидание загрузки страницы выбора сервера
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "serversView"))
                )

                print(f"Выполнен вход для аккаунта {account['username']}")
                return True
            else:
                # Уже авторизован
                return True

        except Exception as e:
            print(f"Ошибка при входе в аккаунт: {e}")
            return False

    def update_account_servers(self, account_idx):
        """Обновление списка серверов для аккаунта через вход в игру"""
        if 0 <= account_idx < len(self.accounts):
            account = self.accounts[account_idx]

            print(f"Обновление серверов для аккаунта {account['username']}...")

            # Флаг, указывающий, был ли создан временный драйвер специально для этой операции
            temp_driver_created = False

            # Проверяем, есть ли уже запущенный драйвер
            driver = self.drivers.get(account['username'])
            if not driver:
                # Создаем новый драйвер в режиме headless для обновления серверов
                driver = self.create_driver(account, headless=True)
                temp_driver_created = True

                if not driver:
                    print("Не удалось создать драйвер")
                    return False

            try:
                # Авторизуемся, если необходимо
                if "mlgame.org" not in driver.current_url:
                    self.login_account(driver, account)

                # Проверяем, что мы на странице со списком серверов
                if "serversView" not in driver.page_source:
                    driver.get(self.game_url)
                    # Проверяем, нужно ли авторизоваться снова
                    if "loginForm" in driver.page_source:
                        self.login_account(driver, account)

                # Ждем загрузки списка серверов
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "serversView"))
                    )
                except TimeoutException:
                    print("Превышено время ожидания загрузки списка серверов")
                    driver.refresh()
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "serversView"))
                    )

                # Дополнительное ожидание для полной загрузки страницы
                time.sleep(3)

                # Получаем все блоки серверов
                server_blocks = driver.find_elements(By.CSS_SELECTOR, ".jewel.group.layout.vertical.gap-8x1px")

                servers = []
                server_names = set()  # Для отслеживания дублирующихся имен серверов

                for block in server_blocks:
                    try:
                        # Проверяем, что это блок сервера (содержит имя сервера)
                        try:
                            name_element = block.find_element(By.ID, "displayName")
                            if not name_element.text:
                                continue  # Пропускаем пустые блоки

                            server_name = name_element.text

                            # Пропускаем серверы с дублирующимися именами
                            if server_name in server_names:
                                print(f"Пропуск дублирующегося сервера: {server_name}")
                                continue

                            # Добавляем имя в отслеживаемый набор
                            server_names.add(server_name)
                        except NoSuchElementException:
                            continue

                        # Определяем, посещал ли пользователь сервер ранее
                        try:
                            enter_button = block.find_element(By.ID, "enterButton")
                            button_style = enter_button.get_attribute("style") or ""
                            button_class = enter_button.get_attribute("class") or ""

                            visited = "-1350px -184px" in button_style
                            disabled = "disabled" in button_class
                        except NoSuchElementException:
                            visited = False
                            disabled = True

                        # Получаем статус сервера (если есть)
                        server_state = ""
                        try:
                            state_element = block.find_element(By.ID, "serverState")
                            server_state = state_element.text
                        except NoSuchElementException:
                            pass

                        # Получаем статистику сервера
                        online_count = 0
                        active_count = 0
                        total_count = 0

                        try:
                            online_label = block.find_element(By.ID, "onlineLabel")
                            online_count = int(online_label.text) if online_label.text.isdigit() else 0
                        except:
                            pass

                        try:
                            active_label = block.find_element(By.ID, "activeLabel")
                            active_count = int(active_label.text) if active_label.text.isdigit() else 0
                        except:
                            pass

                        try:
                            total_label = block.find_element(By.ID, "totalLabel")
                            total_count = int(total_label.text) if total_label.text.isdigit() else 0
                        except:
                            pass

                        servers.append({
                            "name": server_name,
                            "visited": visited,
                            "disabled": disabled,
                            "state": server_state,
                            "online": online_count,
                            "active": active_count,
                            "total": total_count,
                            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    except Exception as e:
                        print(f"Ошибка при обработке сервера: {e}")

                # Обновляем информацию о серверах в аккаунте
                account['servers'] = servers
                self.save_accounts()

                # Если мы создали временный драйвер, закрываем его
                if temp_driver_created:
                    print(f"Закрытие временного браузера после обновления серверов для {account['username']}...")
                    driver.quit()
                else:
                    # Иначе сохраняем драйвер для повторного использования
                    self.drivers[account['username']] = driver

                print(f"Обновлено {len(servers)} серверов для аккаунта {account['username']}")
                return True

            except Exception as e:
                print(f"Ошибка при обновлении серверов: {e}")

                # Если мы создали временный драйвер, закрываем его даже при ошибке
                if temp_driver_created and driver:
                    try:
                        driver.quit()
                        print(f"Закрыт временный браузер после ошибки для {account['username']}")
                    except:
                        pass

                return False
        else:
            print("Неверный номер аккаунта")
            return False

    def enter_server(self, driver, server_name):
        """Вход на указанный сервер"""
        try:
            # Проверяем, что мы на странице со списком серверов
            if "serversView" not in driver.page_source:
                print("Переход на страницу со списком серверов...")
                driver.get(self.game_url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "serversView"))
                )

            # Ждем, чтобы убедиться, что страница полностью загружена
            time.sleep(1)

            # Ищем все элементы с названиями серверов
            server_name_elements = driver.find_elements(By.ID, "displayName")

            for element in server_name_elements:
                if element.text == server_name:
                    # Нашли нужный сервер, ищем блок сервера
                    parent_block = element
                    for _ in range(4):  # Поднимаемся на 4 уровня вверх
                        parent_block = parent_block.find_element(By.XPATH, "..")

                    # Находим кнопку входа в блоке
                    enter_button = parent_block.find_element(By.ID, "enterButton")

                    # Проверяем, не отключен ли сервер
                    if "disabled" in enter_button.get_attribute("class"):
                        print(f"Сервер {server_name} недоступен (отключен)")
                        return False

                    # Кликаем на кнопку входа
                    enter_button.click()
                    print(f"Выполнен вход на сервер {server_name}")

                    # Ожидаем загрузки игры
                    time.sleep(3)
                    return True

            print(f"Сервер {server_name} не найден в списке")
            return False

        except Exception as e:
            print(f"Ошибка при входе на сервер: {e}")
            return False

    def launch_account(self, account):
        """Запуск аккаунта и вход на последний выбранный сервер"""
        if not account.get('last_server'):
            print(f"Для аккаунта {account['username']} не выбран сервер")
            return False

        print(f"Запуск аккаунта {account['username']} на сервере {account['last_server']}...")

        # Проверяем, есть ли уже запущенный драйвер
        driver = self.drivers.get(account['username'])
        if not driver:
            # Создаем новый драйвер
            driver = self.create_driver(account)
            if not driver:
                print("Не удалось создать драйвер для запуска аккаунта")
                return False

        try:
            # Логинимся, если необходимо
            login_result = self.login_account(driver, account)
            if not login_result:
                print(f"Не удалось войти в аккаунт {account['username']}")
                return False

            # Входим на выбранный сервер
            server_result = self.enter_server(driver, account['last_server'])
            if not server_result:
                print(f"Не удалось войти на сервер {account['last_server']}")
                # Сохраняем драйвер для повторного использования
                self.drivers[account['username']] = driver
                return False

            # Сохраняем драйвер для повторного использования
            self.drivers[account['username']] = driver

            print(f"Аккаунт {account['username']} успешно запущен на сервере {account['last_server']}")
            return True

        except Exception as e:
            print(f"Ошибка при запуске аккаунта: {e}")
            # Если произошла ошибка, сохраняем драйвер для повторного использования
            self.drivers[account['username']] = driver
            return False

    def close_browser(self, account_idx):
        """Закрытие браузера для указанного аккаунта"""
        if 0 <= account_idx < len(self.accounts):
            account = self.accounts[account_idx]

            if account['username'] in self.drivers:
                try:
                    print(f"Закрытие браузера для аккаунта {account['username']}...")
                    self.drivers[account['username']].quit()
                    del self.drivers[account['username']]
                    print(f"Браузер для аккаунта {account['username']} закрыт")
                    return True
                except Exception as e:
                    print(f"Ошибка при закрытии браузера: {e}")
                    # Удаляем драйвер из списка даже при ошибке
                    if account['username'] in self.drivers:
                        del self.drivers[account['username']]
                    return False
            else:
                print(f"Для аккаунта {account['username']} нет запущенного браузера")
                return False
        else:
            print("Неверный номер аккаунта")
            return False

    def close_all_browsers(self):
        """Закрытие всех браузеров"""
        if not self.drivers:
            print("Нет запущенных браузеров")
            return True

        closed = 0
        errors = 0

        for username, driver in list(self.drivers.items()):
            try:
                print(f"Закрытие браузера для аккаунта {username}...")
                driver.quit()
                del self.drivers[username]
                closed += 1
            except Exception as e:
                print(f"Ошибка при закрытии браузера для {username}: {e}")
                # Удаляем драйвер из списка даже при ошибке
                if username in self.drivers:
                    del self.drivers[username]
                errors += 1

        print(f"Закрыто браузеров: {closed}, с ошибками: {errors}")
        return True

    # Методы для работы с прокси
    def update_proxies(self, force=False):
        """Обновление списка прокси через ProxyManager"""
        return self.proxy_manager.update_proxies(force)

    def get_random_proxy(self):
        """Получение случайного прокси"""
        return self.proxy_manager.get_random_proxy()

    def verify_proxies(self):
        """Проверка всех прокси в списке"""
        return self.proxy_manager.verify_proxies()

    def assign_random_proxy_to_account(self, account_idx):
        """Назначение случайного прокси аккаунту"""
        if 0 <= account_idx < len(self.accounts):
            proxy = self.get_random_proxy()
            if proxy:
                self.accounts[account_idx]['proxy'] = proxy
                self.save_accounts()
                print(f"Аккаунту {self.accounts[account_idx]['username']} назначен прокси: {proxy}")
                return True
            else:
                print("Нет доступных прокси")
                return False
        return False

    def add_manual_proxy(self, proxy_url):
        """Добавление прокси вручную"""
        return self.proxy_manager.add_manual_proxy(proxy_url)

    def get_proxy_stats(self):
        """Получение статистики по прокси"""
        return self.proxy_manager.get_proxy_stats()


# Рабочие потоки для асинхронного выполнения операций
class WorkerSignals(QObject):
    """Сигналы для потоков"""
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(str)


class Worker(QThread):
    """Базовый класс для рабочих потоков"""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        """Запуск функции в отдельном потоке"""
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


# Стилизованные виджеты для Qt
class StyledFrame(QFrame):
    """Стилизованный фрейм с тенью и закругленными углами"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            StyledFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                border: 1px solid #3d3d3d;
            }
        """)


class StyledButton(QPushButton):
    """Стилизованная кнопка"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1989e6;
            }
            QPushButton:pressed {
                background-color: #00559b;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #aaaaaa;
            }
        """)


class StyledRowFrame(QFrame):
    """Фрейм для строки в списке"""

    def __init__(self, is_header=False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        if is_header:
            self.setStyleSheet("""
                QFrame {
                    background-color: #333333;
                    border-radius: 4px;
                    padding: 4px;
                }
                QLabel {
                    color: white;
                    font-weight: bold;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #2a2a2a;
                    border-radius: 4px;
                    padding: 4px;
                    margin: 2px 0;
                }
                QFrame:hover {
                    background-color: #3a3a3a;
                }
                QLabel {
                    color: white;
                }
            """)


class StyledScrollArea(QScrollArea):
    """Стилизованная область прокрутки"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #232323;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #2d2d2d;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)


class AccountRow(StyledRowFrame):
    """Виджет строки аккаунта"""
    clicked = Signal(int)

    def __init__(self, account, idx, is_selected=False, parent=None):
        super().__init__(parent=parent)
        self.account = account
        self.idx = idx
        self.is_selected = is_selected

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Метки для данных аккаунта
        self.username_label = QLabel(account['username'])
        self.username_label.setMinimumWidth(150)

        status = "Запущен" if account['username'] in parent.bot.drivers else "Остановлен"
        self.status_label = QLabel(status)
        self.status_label.setMinimumWidth(100)

        server = account.get('last_server', '-')
        self.server_label = QLabel(server)

        layout.addWidget(self.username_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.server_label)

        # Отображение выделения
        self.update_selection(is_selected)

    def update_selection(self, is_selected):
        """Обновление состояния выделения"""
        self.is_selected = is_selected
        if is_selected:
            self.setStyleSheet("""
                QFrame {
                    background-color: #004e8c;
                    border-radius: 4px;
                    padding: 4px;
                    margin: 2px 0;
                }
                QLabel {
                    color: white;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #2a2a2a;
                    border-radius: 4px;
                    padding: 4px;
                    margin: 2px 0;
                }
                QFrame:hover {
                    background-color: #3a3a3a;
                }
                QLabel {
                    color: white;
                }
            """)

    def update_data(self, account):
        """Обновляет данные аккаунта"""
        self.account = account
        self.username_label.setText(account['username'])

        status = "Запущен" if account['username'] in self.parent().bot.drivers else "Остановлен"
        self.status_label.setText(status)

        server = account.get('last_server', '-')
        self.server_label.setText(server)

    def mousePressEvent(self, event):
        """Обработка клика на строке"""
        self.clicked.emit(self.idx)
        super().mousePressEvent(event)


class ServerRow(StyledRowFrame):
    """Виджет строки сервера"""
    clicked = Signal(int)

    def __init__(self, server, idx, is_selected=False, is_active=False, parent=None):
        super().__init__(parent=parent)
        self.server = server
        self.idx = idx
        self.is_selected = is_selected
        self.is_active = is_active

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Метки для данных сервера
        self.name_label = QLabel(server['name'])
        self.name_label.setMinimumWidth(150)

        visited = "✓" if server.get('visited', False) else "✗"
        self.visited_label = QLabel(visited)
        self.visited_label.setMinimumWidth(80)

        players = str(server.get('online', 0))
        self.players_label = QLabel(players)
        self.players_label.setMinimumWidth(80)

        state = server.get('state', '')
        self.state_label = QLabel(state)

        layout.addWidget(self.name_label)
        layout.addWidget(self.visited_label)
        layout.addWidget(self.players_label)
        layout.addWidget(self.state_label)

        # Отображение выделения
        self.update_selection(is_selected, is_active)

    def update_selection(self, is_selected, is_active=False):
        """Обновление состояния выделения"""
        self.is_selected = is_selected
        self.is_active = is_active

        if is_selected and is_active:
            # Выбран и активен (является last_server)
            self.setStyleSheet("""
                QFrame {
                    background-color: #004e8c;
                    border-radius: 4px;
                    padding: 4px;
                    margin: 2px 0;
                }
                QLabel {
                    color: white;
                }
            """)
        elif is_selected:
            # Только выбран
            self.setStyleSheet("""
                QFrame {
                    background-color: #0078d7;
                    border-radius: 4px;
                    padding: 4px;
                    margin: 2px 0;
                }
                QLabel {
                    color: white;
                }
            """)
        elif is_active:
            # Только активен (является last_server)
            self.setStyleSheet("""
                QFrame {
                    background-color: #005e20;
                    border-radius: 4px;
                    padding: 4px;
                    margin: 2px 0;
                }
                QLabel {
                    color: white;
                }
            """)
        else:
            # Обычное состояние
            self.setStyleSheet("""
                QFrame {
                    background-color: #2a2a2a;
                    border-radius: 4px;
                    padding: 4px;
                    margin: 2px 0;
                }
                QFrame:hover {
                    background-color: #3a3a3a;
                }
                QLabel {
                    color: white;
                }
            """)

    def mousePressEvent(self, event):
        """Обработка клика на строке"""
        self.clicked.emit(self.idx)
        super().mousePressEvent(event)


class LoadingOverlay(QWidget):
    """Наложение с индикатором загрузки"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Полупрозрачный фон
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0, 150))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        # Создаем индикатор загрузки и надпись
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        self.message = QLabel("Загрузка...")
        self.message.setStyleSheet("color: white; font-size: 16px; background: transparent;")
        self.message.setAlignment(Qt.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Бесконечная анимация
        self.progress.setFixedSize(250, 20)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 10px;
                text-align: center;
                background-color: #333333;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 10px;
            }
        """)

        self.layout.addWidget(self.message)
        self.layout.addWidget(self.progress)

        self.hide()

    def showEvent(self, event):
        """Обработка события показа виджета"""
        # Устанавливаем размер и позицию наложения
        self.setGeometry(self.parent().rect())
        super().showEvent(event)

    def set_message(self, message):
        """Обновление сообщения"""
        self.message.setText(message)


class GameBotQt(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()

        # Инициализация бота
        self.bot = SimpleGameBot()

        # Переменные для хранения состояния
        self.selected_account_idx = None
        self.selected_server_idx = None

        # Словари для хранения ссылок на виджеты строк
        self.account_rows = {}
        self.server_rows = {}

        # Настройка окна
        self.init_ui()

        # Подключение перенаправления вывода
        self.setup_output_redirect()

        # Загрузка аккаунтов
        self.load_accounts()

        # Настройка обработчика закрытия окна
        self.closeEvent = self.on_close_event

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        # Настройка основного окна
        self.setWindowTitle("MyLands - Бот")
        self.setMinimumSize(QSize(900, 600))

        # Установка максимизированного окна при запуске
        self.setWindowState(Qt.WindowMaximized)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: white;
            }
            QLabel {
                color: white;
            }
        """)

        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Главный горизонтальный макет
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Разделитель для панелей
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Левая панель (аккаунты)
        self.create_accounts_panel(splitter)

        # Правая панель
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Верхняя часть правой панели (серверы)
        self.create_servers_panel(right_layout)

        # Нижняя часть правой панели (лог и управление)
        self.create_control_panel(right_layout)

        # Добавляем указание авторства в нижний угол
        author_frame = QFrame(right_panel)
        author_layout = QHBoxLayout(author_frame)
        author_layout.setContentsMargins(0, 0, 5, 0)
        author_layout.setAlignment(Qt.AlignRight)

        author_label = QLabel("© Александр Гончаров")
        author_label.setStyleSheet("""
            QLabel {
                color: #555555;
                font-size: 9px;
                font-style: italic;
            }
        """)
        author_layout.addWidget(author_label)

        # Добавляем фрейм с авторством в правую панель
        right_layout.addWidget(author_frame)

        splitter.addWidget(right_panel)

        # Установка начальных размеров панелей
        splitter.setSizes([300, 600])

        # Наложение для индикатора загрузки
        self.loading_overlay = LoadingOverlay(self)

    def create_accounts_panel(self, parent):
        """Создание панели аккаунтов"""
        # Фрейм для панели аккаунтов
        accounts_panel = StyledFrame()
        accounts_layout = QVBoxLayout(accounts_panel)
        accounts_layout.setContentsMargins(10, 10, 10, 10)
        accounts_layout.setSpacing(10)

        # Заголовок
        title_layout = QHBoxLayout()
        title_label = QLabel("Аккаунты")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        accounts_layout.addLayout(title_layout)

        # Заголовки столбцов
        header_frame = StyledRowFrame(is_header=True)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 5, 10, 5)

        username_header = QLabel("Логин")
        username_header.setMinimumWidth(150)

        status_header = QLabel("Статус")
        status_header.setMinimumWidth(100)

        server_header = QLabel("Сервер")

        header_layout.addWidget(username_header)
        header_layout.addWidget(status_header)
        header_layout.addWidget(server_header)

        accounts_layout.addWidget(header_frame)

        # Список аккаунтов
        accounts_scroll = StyledScrollArea()
        self.accounts_container = QWidget()
        self.accounts_container.setObjectName("accountsContainer")
        self.accounts_container.setStyleSheet("""
            #accountsContainer {
                background-color: #232323;
            }
        """)

        self.accounts_layout = QVBoxLayout(self.accounts_container)
        self.accounts_layout.setContentsMargins(0, 0, 0, 0)
        self.accounts_layout.setSpacing(5)
        self.accounts_layout.addStretch()

        accounts_scroll.setWidget(self.accounts_container)
        accounts_layout.addWidget(accounts_scroll)

        # Кнопки управления аккаунтами
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        add_btn = StyledButton("Добавить")
        add_btn.clicked.connect(self.add_account)

        delete_btn = StyledButton("Удалить")
        delete_btn.clicked.connect(self.delete_account)

        # Кнопка для назначения прокси
        proxy_btn = StyledButton("Назначить прокси")
        proxy_btn.clicked.connect(self.assign_proxy)

        buttons_layout.addWidget(add_btn)
        buttons_layout.addWidget(delete_btn)
        buttons_layout.addWidget(proxy_btn)

        accounts_layout.addLayout(buttons_layout)

        parent.addWidget(accounts_panel)

    def create_servers_panel(self, parent_layout):
        """Создание панели серверов"""
        # Фрейм для панели серверов
        servers_panel = StyledFrame()
        servers_layout = QVBoxLayout(servers_panel)
        servers_layout.setContentsMargins(10, 10, 10, 10)
        servers_layout.setSpacing(10)

        # Заголовок
        title_layout = QHBoxLayout()
        title_label = QLabel("Серверы")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        servers_layout.addLayout(title_layout)

        # Заголовки столбцов
        header_frame = StyledRowFrame(is_header=True)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 5, 10, 5)

        name_header = QLabel("Название")
        name_header.setMinimumWidth(150)

        visited_header = QLabel("Посещен")
        visited_header.setMinimumWidth(80)

        players_header = QLabel("Игроки")
        players_header.setMinimumWidth(80)

        state_header = QLabel("Статус")

        header_layout.addWidget(name_header)
        header_layout.addWidget(visited_header)
        header_layout.addWidget(players_header)
        header_layout.addWidget(state_header)

        servers_layout.addWidget(header_frame)

        # Список серверов
        servers_scroll = StyledScrollArea()
        self.servers_container = QWidget()
        self.servers_container.setObjectName("serversContainer")
        self.servers_container.setStyleSheet("""
            #serversContainer {
                background-color: #232323;
            }
        """)

        self.servers_layout = QVBoxLayout(self.servers_container)
        self.servers_layout.setContentsMargins(0, 0, 0, 0)
        self.servers_layout.setSpacing(5)
        self.servers_layout.addStretch()

        # Добавляем надпись для пустого списка
        self.empty_servers_label = QLabel("Выберите аккаунт для отображения серверов")
        self.empty_servers_label.setAlignment(Qt.AlignCenter)
        self.empty_servers_label.setStyleSheet("color: #aaaaaa; margin: 20px;")
        self.servers_layout.insertWidget(0, self.empty_servers_label)

        servers_scroll.setWidget(self.servers_container)
        servers_layout.addWidget(servers_scroll)

        # Кнопки управления серверами
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        refresh_btn = StyledButton("Обновить серверы")
        refresh_btn.clicked.connect(self.refresh_servers)

        select_btn = StyledButton("Выбрать сервер")
        select_btn.clicked.connect(self.select_server)

        buttons_layout.addWidget(refresh_btn)
        buttons_layout.addWidget(select_btn)

        servers_layout.addLayout(buttons_layout)

        parent_layout.addWidget(servers_panel, 2)  # Вес 2 (более крупный)

    def create_control_panel(self, parent_layout):
        """Создание панели управления"""
        # Фрейм для панели управления
        control_panel = StyledFrame()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(10, 10, 10, 10)
        control_layout.setSpacing(10)

        # Заголовок
        title_layout = QHBoxLayout()
        title_label = QLabel("Управление")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        control_layout.addLayout(title_layout)

        # Лог
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                font-family: Consolas, monospace;
            }
        """)
        control_layout.addWidget(self.log_text)

        # Кнопки управления (ряд 1)
        buttons_layout1 = QHBoxLayout()
        buttons_layout1.setSpacing(10)

        launch_btn = StyledButton("Запустить аккаунт")
        launch_btn.clicked.connect(self.launch_account)

        launch_all_btn = StyledButton("Запустить все")
        launch_all_btn.clicked.connect(self.launch_all_accounts)

        buttons_layout1.addWidget(launch_btn)
        buttons_layout1.addWidget(launch_all_btn)

        control_layout.addLayout(buttons_layout1)

        # Кнопки управления (ряд 2)
        buttons_layout2 = QHBoxLayout()
        buttons_layout2.setSpacing(10)

        close_btn = StyledButton("Закрыть браузер")
        close_btn.clicked.connect(self.close_browser)

        close_all_btn = StyledButton("Закрыть все браузеры")
        close_all_btn.clicked.connect(self.close_all_browsers)

        # Кнопка для обновления прокси
        update_proxies_btn = StyledButton("Обновить прокси")
        update_proxies_btn.clicked.connect(self.update_proxies)

        buttons_layout2.addWidget(close_btn)
        buttons_layout2.addWidget(close_all_btn)
        buttons_layout2.addWidget(update_proxies_btn)

        control_layout.addLayout(buttons_layout2)

        parent_layout.addWidget(control_panel, 1)  # Вес 1 (менее крупный)

    def setup_output_redirect(self):
        """Настройка перенаправления вывода в текстовое поле"""

        class LogRedirector:
            def __init__(self, text_widget):
                self.text_widget = text_widget
                self.buffer = ""

            def write(self, string):
                self.buffer += string
                if '\n' in self.buffer:
                    lines = self.buffer.split('\n')
                    self.buffer = lines[-1]
                    for line in lines[:-1]:
                        if line.strip():
                            self.text_widget.append(line)
                            # Прокрутка вниз
                            scrollbar = self.text_widget.verticalScrollBar()
                            scrollbar.setValue(scrollbar.maximum())

            def flush(self):
                pass

        sys.stdout = LogRedirector(self.log_text)

    def show_loading(self, message="Загрузка..."):
        """Показывает индикатор загрузки"""
        self.loading_overlay.set_message(message)
        self.loading_overlay.show()
        QApplication.processEvents()  # Обработка событий для обновления интерфейса

    def hide_loading(self):
        """Скрывает индикатор загрузки"""
        self.loading_overlay.hide()
        QApplication.processEvents()  # Обработка событий для обновления интерфейса

    def load_accounts(self):
        """Загрузка аккаунтов в интерфейс"""
        # Очистка существующих виджетов
        for row in self.account_rows.values():
            self.accounts_layout.removeWidget(row)
            row.deleteLater()

        self.account_rows = {}

        # Позиция перед растяжкой в конце (для правильного порядка)
        position = self.accounts_layout.count() - 1

        # Добавление строк аккаунтов
        for i, account in enumerate(self.bot.accounts):
            is_selected = (i == self.selected_account_idx)
            row = AccountRow(account, i, is_selected, parent=self)
            row.clicked.connect(self.on_account_select)

            self.accounts_layout.insertWidget(position, row)
            self.account_rows[i] = row

    def load_servers(self, account_idx):
        """Загрузка серверов для выбранного аккаунта"""
        # Показываем индикатор загрузки
        self.show_loading("Загрузка серверов...")

        # Создаем и запускаем рабочий поток
        self.server_worker = Worker(self._load_servers_worker, account_idx)
        self.server_worker.signals.result.connect(self._on_servers_loaded)
        self.server_worker.signals.error.connect(self._on_servers_error)
        self.server_worker.start()

    def _load_servers_worker(self, account_idx):
        """Рабочая функция для загрузки серверов (выполняется в отдельном потоке)"""
        # Если аккаунт не выбран, выходим
        if account_idx is None or account_idx >= len(self.bot.accounts):
            return None, None

        account = self.bot.accounts[account_idx]
        servers = account.get('servers', [])

        # Если серверов нет, попробуем загрузить их
        if not servers:
            # Пробуем обновить серверы
            try:
                result = self.bot.update_account_servers(account_idx)
                if result:
                    print(f"Серверы для {account['username']} успешно загружены")
                    # Перезагружаем серверы
                    servers = account.get('servers', [])
                else:
                    print(f"Не удалось загрузить серверы для {account['username']}")
            except Exception as e:
                print(f"Ошибка при загрузке серверов: {e}")

        return servers, account

    def _on_servers_loaded(self, result):
        """Обработчик завершения загрузки серверов"""
        servers, account = result

        # Скрываем индикатор загрузки
        self.hide_loading()

        # Проверяем результат
        if servers is None or account is None:
            self.empty_servers_label.setText("Выберите аккаунт для отображения серверов")
            self.empty_servers_label.show()
            return

        # Отображаем серверы
        self._display_servers(servers, account)

    def _on_servers_error(self, error_msg):
        """Обработчик ошибки при загрузке серверов"""
        # Скрываем индикатор загрузки
        self.hide_loading()

        # Выводим сообщение об ошибке
        print(f"Ошибка при загрузке серверов: {error_msg}")
        QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить серверы: {error_msg}")

        # Показываем сообщение о пустом списке
        self.empty_servers_label.setText("Ошибка при загрузке серверов")
        self.empty_servers_label.show()

    def _display_servers(self, servers, account):
        """Отображение серверов в интерфейсе"""
        # Очистка существующих виджетов
        for row in self.server_rows.values():
            self.servers_layout.removeWidget(row)
            row.deleteLater()

        self.server_rows = {}

        # Если серверов нет, показываем сообщение
        if not servers:
            self.empty_servers_label.setText("Нет доступных серверов")
            self.empty_servers_label.show()
            return

        # Скрываем сообщение о пустом списке
        self.empty_servers_label.hide()

        # Позиция перед растяжкой в конце (для правильного порядка)
        position = self.servers_layout.count() - 1

        # Добавление строк серверов
        for i, server in enumerate(servers):
            is_selected = (i == self.selected_server_idx)
            is_active = (server['name'] == account.get('last_server', ''))

            row = ServerRow(server, i, is_selected, is_active, parent=self)
            row.clicked.connect(self.on_server_select)

            self.servers_layout.insertWidget(position, row)
            self.server_rows[i] = row

    def update_account_row(self, idx):
        """Обновление строки аккаунта"""
        if idx not in self.account_rows:
            return

        row = self.account_rows[idx]
        account = self.bot.accounts[idx]
        row.update_data(account)

    def on_account_select(self, idx):
        """Обработчик выбора аккаунта"""
        # Снимаем выделение с текущего аккаунта
        if self.selected_account_idx is not None and self.selected_account_idx in self.account_rows:
            self.account_rows[self.selected_account_idx].update_selection(False)

        # Устанавливаем новый выбранный аккаунт
        self.selected_account_idx = idx
        self.selected_server_idx = None

        # Выделяем новый аккаунт
        if idx in self.account_rows:
            self.account_rows[idx].update_selection(True)

        # Загружаем серверы для выбранного аккаунта
        self.load_servers(idx)

    def on_server_select(self, idx):
        """Обработчик выбора сервера"""
        # Снимаем выделение с текущего сервера
        if self.selected_server_idx is not None and self.selected_server_idx in self.server_rows:
            # Проверяем, является ли этот сервер last_server
            account = self.bot.accounts[self.selected_account_idx]
            server = account.get('servers', [])[self.selected_server_idx]
            is_active = (server['name'] == account.get('last_server', ''))

            self.server_rows[self.selected_server_idx].update_selection(False, is_active)

        # Устанавливаем новый выбранный сервер
        self.selected_server_idx = idx

        # Выделяем новый сервер
        if idx in self.server_rows:
            account = self.bot.accounts[self.selected_account_idx]
            server = account.get('servers', [])[idx]
            is_active = (server['name'] == account.get('last_server', ''))

            self.server_rows[idx].update_selection(True, is_active)

    def add_account(self):
        """Добавление нового аккаунта"""
        try:
            # Запрос логина
            username, ok = QInputDialog.getText(self, "Новый аккаунт", "Введите логин:")
            if not ok or not username:
                return

            # Запрос пароля
            password, ok = QInputDialog.getText(self, "Новый аккаунт", "Введите пароль:", QLineEdit.Password)
            if not ok or not password:
                return

            # Запрос прокси (опционально)
            proxy, ok = QInputDialog.getText(self, "Новый аккаунт", "Введите прокси (опционально):")
            if not ok:
                return

            # Создание аккаунта
            account = {
                "username": username,
                "password": password,
                "servers": [],
                "last_server": None
            }

            if proxy:
                account["proxy"] = proxy

            # Добавление аккаунта
            self.bot.accounts.append(account)
            self.bot.save_accounts()

            # Обновление списка
            idx = len(self.bot.accounts) - 1
            position = self.accounts_layout.count() - 1

            row = AccountRow(account, idx, False, parent=self)
            row.clicked.connect(self.on_account_select)

            self.accounts_layout.insertWidget(position, row)
            self.account_rows[idx] = row

            print(f"Аккаунт {username} успешно добавлен")
        except Exception as e:
            print(f"Ошибка при добавлении аккаунта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить аккаунт: {e}")

    def delete_account(self):
        """Удаление выбранного аккаунта"""
        if self.selected_account_idx is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите аккаунт для удаления")
            return

        account = self.bot.accounts[self.selected_account_idx]
        reply = QMessageBox.question(
            self, "Удаление аккаунта",
            f"Вы уверены, что хотите удалить аккаунт {account['username']}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Закрываем браузер, если он запущен
            if account['username'] in self.bot.drivers:
                self.bot.close_browser(self.selected_account_idx)

            # Удаляем строку из интерфейса
            if self.selected_account_idx in self.account_rows:
                row = self.account_rows[self.selected_account_idx]
                self.accounts_layout.removeWidget(row)
                row.deleteLater()
                del self.account_rows[self.selected_account_idx]

            # Удаляем аккаунт из модели
            del self.bot.accounts[self.selected_account_idx]
            self.bot.save_accounts()

            # Обновляем индексы оставшихся строк
            new_account_rows = {}
            for old_idx, row in self.account_rows.items():
                if old_idx > self.selected_account_idx:
                    new_idx = old_idx - 1
                    row.idx = new_idx
                    new_account_rows[new_idx] = row
                else:
                    new_account_rows[old_idx] = row

            self.account_rows = new_account_rows

            # Сбрасываем выбранный аккаунт и сервер
            self.selected_account_idx = None
            self.selected_server_idx = None

            # Очищаем список серверов
            for row in self.server_rows.values():
                self.servers_layout.removeWidget(row)
                row.deleteLater()

            self.server_rows = {}

            # Показываем сообщение о пустом списке серверов
            self.empty_servers_label.setText("Выберите аккаунт для отображения серверов")
            self.empty_servers_label.show()

            print(f"Аккаунт {account['username']} удален")

    def refresh_servers(self):
        """Обновление списка серверов для выбранного аккаунта"""
        if self.selected_account_idx is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите аккаунт для обновления серверов")
            return

        # Показываем индикатор загрузки
        self.show_loading("Обновление серверов...")

        # Создаем и запускаем рабочий поток
        self.refresh_worker = Worker(self._refresh_servers_worker, self.selected_account_idx)
        self.refresh_worker.signals.result.connect(self._on_servers_refreshed)
        self.refresh_worker.signals.error.connect(self._on_servers_error)
        self.refresh_worker.start()

    def _refresh_servers_worker(self, account_idx):
        """Рабочая функция для обновления серверов (выполняется в отдельном потоке)"""
        account = self.bot.accounts[account_idx]
        print(f"Обновление серверов для {account['username']}...")

        # Обновляем серверы (будет использовать скрытый браузер)
        result = self.bot.update_account_servers(account_idx)

        if result:
            print(f"Серверы для {account['username']} обновлены")
            # Возвращаем обновленные серверы
            return account.get('servers', []), account
        else:
            print(f"Ошибка при обновлении серверов для {account['username']}")
            raise Exception("Не удалось обновить серверы")

    def _on_servers_refreshed(self, result):
        """Обработчик завершения обновления серверов"""
        servers, account = result

        # Скрываем индикатор загрузки
        self.hide_loading()

        # Обновляем интерфейс
        self._display_servers(servers, account)
        self.update_account_row(self.selected_account_idx)

    def select_server(self):
        """Выбор сервера для аккаунта"""
        if self.selected_account_idx is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите аккаунт")
            return

        if self.selected_server_idx is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите сервер")
            return

        # Получение данных аккаунта и сервера
        account = self.bot.accounts[self.selected_account_idx]
        servers = account.get('servers', [])

        if self.selected_server_idx >= len(servers):
            return

        server = servers[self.selected_server_idx]

        # Проверка доступности сервера
        if server.get('disabled', False):
            reply = QMessageBox.question(
                self, "Предупреждение",
                f"Сервер {server['name']} отмечен как недоступный. Всё равно выбрать?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Запоминаем старый выбранный сервер
        old_server_name = account.get('last_server')

        # Устанавливаем новый выбранный сервер
        account['last_server'] = server['name']
        self.bot.save_accounts()

        # Обновляем отображение серверов
        for idx, row in self.server_rows.items():
            server_name = servers[idx]['name']
            is_selected = (idx == self.selected_server_idx)
            is_active = (server_name == account['last_server'])

            row.update_selection(is_selected, is_active)

        # Обновляем строку аккаунта
        self.update_account_row(self.selected_account_idx)

        print(f"Для аккаунта {account['username']} выбран сервер {server['name']}")

    def launch_account(self):
        """Запуск выбранного аккаунта"""
        if self.selected_account_idx is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите аккаунт для запуска")
            return

        # Показываем индикатор загрузки
        self.show_loading("Запуск аккаунта...")

        # Создаем и запускаем рабочий поток
        self.launch_worker = Worker(self._launch_account_worker, self.selected_account_idx)
        self.launch_worker.signals.result.connect(self._on_account_launched)
        self.launch_worker.signals.error.connect(self._on_launch_error)
        self.launch_worker.start()

    def _launch_account_worker(self, account_idx):
        """Рабочая функция для запуска аккаунта (выполняется в отдельном потоке)"""
        account = self.bot.accounts[account_idx]
        print(f"Запуск аккаунта {account['username']}...")

        # Запускаем аккаунт
        result = self.bot.launch_account(account)

        if result:
            print(f"Аккаунт {account['username']} успешно запущен")
            return True, account_idx
        else:
            print(f"Ошибка при запуске аккаунта {account['username']}")
            raise Exception(f"Не удалось запустить аккаунт {account['username']}")

    def _on_account_launched(self, result):
        """Обработчик завершения запуска аккаунта"""
        success, account_idx = result

        # Скрываем индикатор загрузки
        self.hide_loading()

        # Обновляем строку аккаунта
        self.update_account_row(account_idx)

    def _on_launch_error(self, error_msg):
        """Обработчик ошибки при запуске аккаунта"""
        # Скрываем индикатор загрузки
        self.hide_loading()

        # Выводим сообщение об ошибке
        QMessageBox.warning(self, "Ошибка", f"Не удалось запустить аккаунт: {error_msg}")

        # Обновляем строку аккаунта (статус мог измениться)
        if self.selected_account_idx is not None:
            self.update_account_row(self.selected_account_idx)

    def launch_all_accounts(self):
        """Запуск всех аккаунтов"""
        if not self.bot.accounts:
            QMessageBox.warning(self, "Предупреждение", "Нет аккаунтов для запуска")
            return

        # Показываем индикатор загрузки
        self.show_loading("Запуск всех аккаунтов...")

        # Создаем и запускаем рабочий поток
        self.launch_all_worker = Worker(self._launch_all_accounts_worker)
        self.launch_all_worker.signals.progress.connect(self._on_launch_all_progress)
        self.launch_all_worker.signals.result.connect(self._on_all_accounts_launched)
        self.launch_all_worker.signals.error.connect(self._on_launch_error)
        self.launch_all_worker.start()

    def _launch_all_accounts_worker(self):
        """Рабочая функция для запуска всех аккаунтов (выполняется в отдельном потоке)"""
        print("Запуск всех аккаунтов...")

        launched = 0
        errors = 0
        updated_accounts = []

        for i, account in enumerate(self.bot.accounts):
            if account.get("last_server"):
                self.launch_all_worker.signals.progress.emit(f"Запуск аккаунта {account['username']}...")
                print(f"Запуск аккаунта {account['username']}...")

                result = self.bot.launch_account(account)
                if result:
                    launched += 1
                else:
                    errors += 1

                # Добавляем индекс аккаунта для обновления в интерфейсе
                updated_accounts.append(i)

                # Небольшая пауза между запусками
                time.sleep(1)
            else:
                print(f"Для аккаунта {account['username']} не выбран сервер. Пропускаю.")

        print(f"Итоги запуска: успешно - {launched}, с ошибками - {errors}")
        return launched, errors, updated_accounts

    def _on_launch_all_progress(self, message):
        """Обработчик прогресса при запуске всех аккаунтов"""
        # Обновляем сообщение индикатора загрузки
        self.loading_overlay.set_message(message)

    def _on_all_accounts_launched(self, result):
        """Обработчик завершения запуска всех аккаунтов"""
        launched, errors, updated_accounts = result

        # Скрываем индикатор загрузки
        self.hide_loading()

        # Обновляем строки аккаунтов
        for idx in updated_accounts:
            self.update_account_row(idx)

        # Выводим сообщение о результатах
        QMessageBox.information(
            self, "Запуск аккаунтов",
            f"Запуск аккаунтов завершен.\nУспешно: {launched}\nС ошибками: {errors}"
        )

    def close_browser(self):
        """Закрытие браузера для выбранного аккаунта"""
        if self.selected_account_idx is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите аккаунт")
            return

        # Показываем индикатор загрузки
        self.show_loading("Закрытие браузера...")

        # Создаем и запускаем рабочий поток
        self.close_worker = Worker(self._close_browser_worker, self.selected_account_idx)
        self.close_worker.signals.result.connect(self._on_browser_closed)
        self.close_worker.signals.error.connect(self._on_close_error)
        self.close_worker.start()

    def _close_browser_worker(self, account_idx):
        """Рабочая функция для закрытия браузера (выполняется в отдельном потоке)"""
        account = self.bot.accounts[account_idx]
        print(f"Закрытие браузера для {account['username']}...")

        # Закрываем браузер
        result = self.bot.close_browser(account_idx)

        if result:
            print(f"Браузер для {account['username']} закрыт")
            return True, account_idx
        else:
            print(f"Ошибка при закрытии браузера для {account['username']}")
            raise Exception(f"Не удалось закрыть браузер для {account['username']}")

    def _on_browser_closed(self, result):
        """Обработчик завершения закрытия браузера"""
        success, account_idx = result

        # Скрываем индикатор загрузки
        self.hide_loading()

        # Обновляем строку аккаунта
        self.update_account_row(account_idx)

    def _on_close_error(self, error_msg):
        """Обработчик ошибки при закрытии браузера"""
        # Скрываем индикатор загрузки
        self.hide_loading()

        # Выводим сообщение об ошибке
        QMessageBox.warning(self, "Ошибка", f"Ошибка при закрытии браузера: {error_msg}")

        # Обновляем строку аккаунта (статус мог измениться)
        if self.selected_account_idx is not None:
            self.update_account_row(self.selected_account_idx)

    def close_all_browsers(self):
        """Закрытие всех браузеров"""
        if not self.bot.drivers:
            QMessageBox.warning(self, "Предупреждение", "Нет запущенных браузеров")
            return

        # Показываем индикатор загрузки
        self.show_loading("Закрытие всех браузеров...")

        # Создаем и запускаем рабочий поток
        self.close_all_worker = Worker(self._close_all_browsers_worker)
        self.close_all_worker.signals.result.connect(self._on_all_browsers_closed)
        self.close_all_worker.signals.error.connect(self._on_close_error)
        self.close_all_worker.start()

    def _close_all_browsers_worker(self):
        """Рабочая функция для закрытия всех браузеров (выполняется в отдельном потоке)"""
        print("Закрытие всех браузеров...")

        # Закрываем все браузеры
        result = self.bot.close_all_browsers()

        if result:
            print("Все браузеры закрыты")
            # Возвращаем список аккаунтов, которые нужно обновить
            return True, list(range(len(self.bot.accounts)))
        else:
            print("Ошибка при закрытии браузеров")
            raise Exception("Не удалось закрыть все браузеры")

    def _on_all_browsers_closed(self, result):
        """Обработчик завершения закрытия всех браузеров"""
        success, account_indices = result

        # Скрываем индикатор загрузки
        self.hide_loading()

        # Обновляем строки аккаунтов
        for idx in account_indices:
            self.update_account_row(idx)

    # Методы для работы с прокси
    def update_proxies(self):
        """Обновление списка прокси"""
        # Показываем индикатор загрузки
        self.show_loading("Обновление списка прокси...")

        # Создаем и запускаем рабочий поток
        def update_proxies_thread():
            print("Обновление списка прокси...")
            result = self.bot.update_proxies(force=True)

            # Проверка результата
            if result:
                print("Список прокси успешно обновлен")
                stats = self.bot.get_proxy_stats()
                print(f"Статистика прокси: всего - {stats['total']}, рабочих - {stats['working']}")
            else:
                print("Не удалось обновить список прокси")

            # Скрываем индикатор загрузки
            self.hide_loading()

        self.update_proxies_worker = Worker(update_proxies_thread)
        self.update_proxies_worker.signals.finished.connect(self.hide_loading)
        self.update_proxies_worker.start()

    def assign_proxy(self):
        """Назначение прокси выбранному аккаунту"""
        if self.selected_account_idx is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите аккаунт для назначения прокси")
            return

        # Показываем индикатор загрузки
        self.show_loading("Назначение прокси...")

        # Создаем и запускаем рабочий поток
        def assign_proxy_thread():
            result = self.bot.assign_random_proxy_to_account(self.selected_account_idx)
            return result

        self.assign_proxy_worker = Worker(assign_proxy_thread)
        self.assign_proxy_worker.signals.result.connect(self._on_proxy_assigned)
        self.assign_proxy_worker.signals.error.connect(self._on_proxy_error)
        self.assign_proxy_worker.start()

    def _on_proxy_assigned(self, result):
        """Обработчик завершения назначения прокси"""
        # Скрываем индикатор загрузки
        self.hide_loading()

        if result:
            # Обновляем строку аккаунта
            self.update_account_row(self.selected_account_idx)
            account = self.bot.accounts[self.selected_account_idx]
            QMessageBox.information(self, "Прокси", f"Прокси {account.get('proxy')} успешно назначен")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось назначить прокси. Возможно, список прокси пуст.")

    def _on_proxy_error(self, error_msg):
        """Обработчик ошибки при назначении прокси"""
        # Скрываем индикатор загрузки
        self.hide_loading()

        # Выводим сообщение об ошибке
        QMessageBox.warning(self, "Ошибка", f"Ошибка при назначении прокси: {error_msg}")

    def on_close_event(self, event):
        """Обработчик закрытия окна"""
        reply = QMessageBox.question(
            self, "Выход",
            "Закрыть все браузеры и выйти?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            # Показываем индикатор загрузки
            self.show_loading("Закрытие всех браузеров...")

            def close_all_and_exit():
                # Закрываем все браузеры
                self.bot.close_all_browsers()

                # Восстанавливаем стандартный вывод
                sys.stdout = sys.__stdout__

                # Принимаем событие закрытия
                event.accept()

            # Создаем и запускаем рабочий поток
            self.exit_worker = Worker(lambda: close_all_and_exit())
            self.exit_worker.start()
        else:
            # Отклоняем событие закрытия
            event.ignore()


def main():
    # Создание приложения Qt
    app = QApplication(sys.argv)

    # Установка темной темы
    app.setStyle("Fusion")

    # Создание и отображение основного окна
    window = GameBotQt()
    window.showMaximized()  # Используем showMaximized() вместо show() или showFullScreen()

    # Запуск цикла обработки событий
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        print("Запуск бота для управления аккаунтами игры...")
        main()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()