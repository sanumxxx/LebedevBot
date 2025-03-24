import json
import os
import time
import threading
import sys
import traceback
import nest_asyncio
import random
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
                               QTextEdit, QMessageBox, QInputDialog, QProgressBar, QLineEdit,
                               QCheckBox)
from PySide6.QtCore import Qt, QSize, Signal, Slot, QThread, QObject
from PySide6.QtGui import QColor, QPalette, QFont

# Импорт Playwright
from playwright.sync_api import sync_playwright, Page, Browser, Error, TimeoutError

# Применяем патч для поддержки асинхронных операций в разных потоках
nest_asyncio.apply()

# Импорт ProxyManager
from proxy_manager import ProxyManager


class SimpleGameBot:
    """Бот для управления аккаунтами и серверами браузерной игры"""

    def __init__(self):
        self.accounts_file = "game_accounts.json"
        self.accounts = self.load_accounts()
        self.game_url = "https://ru.mlgame.org/"
        self.browsers = {}  # Хранит экземпляры браузеров
        self.pages = {}  # Хранит страницы для каждого аккаунта
        self.playwright = None
        self.minimal_mode = True  # Минимальный режим по умолчанию
        # Инициализируем ProxyManager
        self.proxy_manager = ProxyManager()

    def _get_playwright(self):
        """Получение экземпляра Playwright с учетом потока выполнения"""
        try:
            # Создаем новый экземпляр для текущего потока
            playwright = sync_playwright().start()
            print("Playwright успешно инициализирован")
            return playwright
        except Exception as e:
            print(f"Ошибка при инициализации Playwright: {e}")
            return None

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

    def create_browser(self, account, headless=False, playwright_instance=None):
        """Создание браузера Playwright с нужными настройками"""
        try:
            # Используем переданный экземпляр Playwright или создаем новый
            playwright = playwright_instance
            if playwright is None:
                playwright = self._get_playwright()
                if playwright is None:
                    print("Не удалось инициализировать Playwright")
                    return None, None, None

            # Определение базового пути приложения
            if getattr(sys, 'frozen', False):
                # Путь для скомпилированного приложения
                base_path = os.path.dirname(sys.executable)
            else:
                # Путь для разработки
                base_path = os.path.dirname(os.path.abspath(__file__))

            # Настройка на хранение данных для каждого аккаунта в отдельной папке
            user_data_dir = os.path.join(base_path, f"chrome_data/{account['username']}")
            os.makedirs(user_data_dir, exist_ok=True)

            # Получение случайного User-Agent
            user_agent = self.proxy_manager.get_random_user_agent()
            print(f"Используется User-Agent: {user_agent}")

            # Настройки для браузера
            browser_args = [
                "--start-maximized",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-gpu",
                "--no-sandbox",
                "--ignore-certificate-errors",
                "--ignore-ssl-errors",
                "--disable-web-security",  # Отключаем проверки безопасности
                "--disable-features=IsolateOrigins,site-per-process",  # Отключаем изоляцию
                "--disable-site-isolation-trials",  # Отключаем изоляцию сайтов
                "--disable-blink-features=AutomationControlled",  # Скрываем автоматизацию
                "--aggressive-cache-discard",  # Отключаем кэш
                "--disable-cache",  # Отключаем кэш
                "--disable-application-cache",  # Отключаем кэш приложений
                "--disable-infobars",  # Скрываем инфо панели
                "--window-size=1920,1080",  # Фиксированный размер окна
                "--lang=ru-RU,ru",  # Устанавливаем русский язык
                "--disable-extensions",  # Отключаем расширения
                "--disable-dev-shm-usage",  # Отключаем использование /dev/shm
                "--disable-accelerated-2d-canvas",  # Отключаем ускорение 2D
                "--disable-default-apps",  # Отключаем приложения по умолчанию
                "--no-first-run",  # Отключаем первый запуск
            ]

            # Добавление прокси, если указан
            proxy_config = None
            if account.get('proxy'):
                proxy_url = account['proxy']
                # Playwright использует другой формат настройки прокси
                proxy_parts = proxy_url.replace('http://', '').split(':')
                if len(proxy_parts) == 2:
                    proxy_config = {
                        "server": proxy_url
                    }
                print(f"Используется прокси: {proxy_url}")
            elif not headless:
                # Если прокси не задан и браузер не в скрытом режиме,
                # попробуем использовать случайный прокси
                random_proxy = self.proxy_manager.get_random_proxy()
                if random_proxy:
                    proxy_config = {
                        "server": random_proxy
                    }
                    print(f"Используется случайный прокси: {random_proxy}")

            # В минимальном режиме не загружаем изображения и другие ресурсы
            if self.minimal_mode:
                print("Включен минимальный режим - отключаем загрузку изображений и других ресурсов")
                browser_args.extend([
                    "--disable-images",
                    "--blink-settings=imagesEnabled=false"
                ])

            # Создаем браузер с нужными параметрами
            browser = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                proxy=proxy_config,
                user_agent=user_agent,
                args=browser_args,
                ignore_https_errors=True,
                timeout=15000,  # 15 секунд таймаут для запуска
                viewport={"width": 1280, "height": 720},
                java_script_enabled=True
            )

            # Создаем новую страницу в браузере
            page = browser.new_page()

            # Устанавливаем очень короткие таймауты в минимальном режиме
            if self.minimal_mode:
                page.set_default_timeout(500000)  # 5 секунд таймаут для операций
                page.set_default_navigation_timeout(1000000)  # 10 секунд для навигации
            else:
                page.set_default_timeout(1500000)  # 15 секунд таймаут для операций
                page.set_default_navigation_timeout(2000000)  # 20 секунд для навигации

            # Установка дополнительных обработчиков JavaScript
            page.add_init_script("""
                // Переопределение объектов для скрытия автоматизации
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });

                // Определение случайных функций для имитации реального пользователя
                window.navigator.chrome = {
                    runtime: {}
                };

                // Скрытие автоматизации
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // Скрытие WebDriver
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)

            print(f"Браузер успешно создан для {account['username']}")

            return browser, page, playwright
        except Exception as e:
            print(f"Критическая ошибка при создании браузера: {e}")
            # Закрываем Playwright, если он был создан в этой функции
            if playwright_instance is None and playwright is not None:
                try:
                    playwright.stop()
                except:
                    pass
            return None, None, None

    def login_account(self, page, account):
        """Вход в аккаунт через форму авторизации"""
        try:
            print(f"Выполняем вход для аккаунта {account['username']}...")

            # Разные способы загрузки в зависимости от режима
            if self.minimal_mode:
                # Минимальный режим: прямое действие без ожидания загрузки страницы
                try:
                    print("Минимальный режим: загрузка без ожидания")
                    # Пробуем загрузить страницу без ожидания полной загрузки
                    try:
                        print("Попытка быстрой загрузки...")
                        page.goto(self.game_url, timeout=5000, wait_until="commit")
                    except TimeoutError:
                        print("Таймаут загрузки, продолжаем работу с тем, что есть")
                        # Если произошел таймаут, продолжаем работу с тем, что уже загружено
                        pass

                    # Проверяем состояние страницы, используя JavaScript
                    try:
                        # Проверяем, нужна ли авторизация (есть ли форма логина)
                        form_exists = page.evaluate("""() => {
                            return document.getElementById('loginForm') !== null;
                        }""")

                        if form_exists:
                            print("Форма авторизации найдена, выполняем вход...")

                            # Вводим логин и пароль с помощью JavaScript напрямую
                            page.evaluate(f"""(username, password) => {{
                                const usernameField = document.getElementById('username');
                                const passwordField = document.getElementById('password');
                                if (usernameField) usernameField.value = username;
                                if (passwordField) passwordField.value = password;

                                // Устанавливаем флажок "запомнить меня"
                                const rememberMe = document.getElementById('rememberMe');
                                if (rememberMe && !rememberMe.checked) rememberMe.checked = true;

                                // Нажимаем кнопку входа
                                const loginButton = document.getElementById('loginButton');
                                if (loginButton) loginButton.click();
                            }}""", account["username"], account["password"])

                            # Короткая пауза для обработки входа
                            time.sleep(2)

                            # Проверяем, удалось ли войти (исчезла ли форма логина)
                            try:
                                login_success = page.evaluate("""() => {
                                    return document.getElementById('loginForm') === null;
                                }""")

                                if login_success:
                                    print(f"Вход выполнен успешно для {account['username']}")
                                    return True
                                else:
                                    print("Форма логина все еще отображается, вход не выполнен")
                                    return False
                            except:
                                print("Не удалось проверить результат входа")
                                return False

                        else:
                            # Проверяем, есть ли список серверов
                            servers_exist = page.evaluate("""() => {
                                return document.getElementById('serversView') !== null;
                            }""")

                            if servers_exist:
                                print(f"Аккаунт {account['username']} уже авторизован")
                                return True
                            else:
                                print("Ни форма логина, ни список серверов не найдены")
                                return False
                    except Exception as js_error:
                        print(f"Ошибка при выполнении JavaScript: {js_error}")
                        return False

                except Exception as quick_error:
                    print(f"Ошибка при быстром входе: {quick_error}")
                    return False
            else:
                # Стандартный режим: обычный вход с ожиданиями
                try:
                    print("Стандартный режим: загрузка с ожиданием")
                    page.goto(self.game_url, wait_until='domcontentloaded', timeout=10000)
                except Exception as e:
                    print(f"Ошибка при загрузке главной страницы: {e}")
                    return False

                # Проверяем наличие формы логина
                try:
                    login_form_exists = page.is_visible("#loginForm", timeout=5000)
                    if login_form_exists:
                        print(f"Форма авторизации найдена для аккаунта {account['username']}...")

                        # Быстрый ввод логина и пароля
                        page.fill("#username", account["username"])
                        page.fill("#password", account["password"])

                        # Установка флажка "входить автоматически"
                        try:
                            remember_me = page.query_selector("#rememberMe")
                            if remember_me and not remember_me.is_checked():
                                remember_me.check()
                        except:
                            pass

                        # Быстрое нажатие на кнопку входа
                        page.click("#loginButton")

                        # Ждем появления списка серверов с коротким таймаутом
                        try:
                            page.wait_for_selector("#serversView", timeout=5000)
                            print(f"Выполнен вход для аккаунта {account['username']}")
                            return True
                        except Exception as e:
                            print(f"Ошибка при ожидании загрузки страницы серверов: {e}")
                            return False
                    else:
                        # Уже авторизован, проверяем, есть ли список серверов
                        servers_view_exists = page.is_visible("#serversView", timeout=3000)
                        if servers_view_exists:
                            print(f"Аккаунт {account['username']} уже авторизован")
                            return True
                        else:
                            # Быстрое обновление страницы
                            page.reload(wait_until='domcontentloaded', timeout=10000)

                            # Проверяем еще раз после обновления
                            servers_view_exists = page.is_visible("#serversView", timeout=3000)
                            if servers_view_exists:
                                print(f"После обновления страницы обнаружен список серверов")
                                return True
                            else:
                                print(f"После обновления страницы не найден список серверов")
                                return False
                except Exception as e:
                    print(f"Исключение при авторизации: {e}")
                    return False

        except Exception as e:
            print(f"Ошибка при входе в аккаунт: {e}")
            return False

    def update_account_servers(self, account_idx):
        """Обновление списка серверов для аккаунта через вход в игру"""
        if 0 <= account_idx < len(self.accounts):
            account = self.accounts[account_idx]

            print(f"Обновление серверов для аккаунта {account['username']}...")

            # Получаем экземпляр Playwright для этого потока
            playwright = self._get_playwright()
            if not playwright:
                print("Не удалось инициализировать Playwright")
                return False

            # Флаг, указывающий, был ли создан временный браузер специально для этой операции
            temp_browser_created = False

            # Проверяем, есть ли уже запущенный браузер
            browser = self.browsers.get(account['username'])
            page = self.pages.get(account['username'])

            if not browser or not page:
                # Создаем новый браузер в режиме headless для обновления серверов
                print("Создание временного браузера для обновления серверов...")
                browser, page, _ = self.create_browser(account, headless=True, playwright_instance=playwright)
                temp_browser_created = True

                if not browser or not page:
                    print("Не удалось создать браузер")
                    playwright.stop()
                    return False

            try:
                # Авторизуемся
                login_success = self.login_account(page, account)
                if not login_success:
                    print(f"Не удалось авторизоваться для аккаунта {account['username']}")
                    # Если в аккаунте уже есть серверы, используем их
                    if account.get('servers'):
                        print(f"Используем кэшированный список серверов ({len(account['servers'])} шт)")
                        if temp_browser_created:
                            browser.close()
                            playwright.stop()
                        return True
                    raise Exception("Ошибка авторизации")

                # В зависимости от режима, используем разные способы получения серверов
                servers = []

                if self.minimal_mode:
                    # Минимальный режим: получение серверов с помощью JavaScript
                    try:
                        print("Минимальный режим: получение серверов через JavaScript")
                        # Используем JavaScript для извлечения данных серверов
                        server_data = page.evaluate("""() => {
                            const servers = [];
                            const blocks = document.querySelectorAll(".jewel.group.layout.vertical.gap-8x1px");

                            for (const block of blocks) {
                                try {
                                    const nameEl = block.querySelector("#displayName");
                                    if (!nameEl || !nameEl.textContent.trim()) continue;

                                    const serverName = nameEl.textContent.trim();

                                    // Проверяем кнопку входа
                                    const enterButton = block.querySelector("#enterButton");
                                    const buttonStyle = enterButton ? enterButton.getAttribute("style") || "" : "";
                                    const buttonClass = enterButton ? enterButton.getAttribute("class") || "" : "";

                                    const visited = buttonStyle.includes("-1350px -184px");
                                    const disabled = buttonClass.includes("disabled");

                                    // Получаем статус сервера
                                    const stateEl = block.querySelector("#serverState");
                                    const serverState = stateEl ? stateEl.textContent.trim() : "";

                                    // Получаем счетчики
                                    const onlineLabel = block.querySelector("#onlineLabel");
                                    const activeLabel = block.querySelector("#activeLabel");
                                    const totalLabel = block.querySelector("#totalLabel");

                                    const online = onlineLabel && !isNaN(parseInt(onlineLabel.textContent)) 
                                        ? parseInt(onlineLabel.textContent) : 0;
                                    const active = activeLabel && !isNaN(parseInt(activeLabel.textContent)) 
                                        ? parseInt(activeLabel.textContent) : 0;
                                    const total = totalLabel && !isNaN(parseInt(totalLabel.textContent)) 
                                        ? parseInt(totalLabel.textContent) : 0;

                                    servers.push({
                                        name: serverName,
                                        visited: visited,
                                        disabled: disabled,
                                        state: serverState,
                                        online: online,
                                        active: active,
                                        total: total
                                    });
                                } catch (error) {
                                    console.error("Ошибка при обработке сервера:", error);
                                }
                            }
                            return servers;
                        }""")

                        if server_data:
                            print(f"Получено {len(server_data)} серверов через JavaScript")

                            # Добавляем метку времени к каждому серверу
                            for server in server_data:
                                server["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            servers = server_data
                        else:
                            print("Не удалось получить серверы через JavaScript")
                    except Exception as js_error:
                        print(f"Ошибка при получении серверов через JavaScript: {js_error}")
                else:
                    # Стандартный режим: получение серверов через селекторы
                    print("Стандартный режим: получение серверов через селекторы")
                    try:
                        # Проверяем, видим ли мы список серверов
                        servers_view_visible = page.is_visible("#serversView", timeout=5000)
                        if not servers_view_visible:
                            print("Список серверов не виден, пробуем обновить страницу")
                            page.reload(wait_until='domcontentloaded', timeout=10000)
                            servers_view_visible = page.is_visible("#serversView", timeout=5000)

                            if not servers_view_visible:
                                print("Список серверов не найден после обновления")
                                # Если в аккаунте уже есть серверы, используем их
                                if account.get('servers'):
                                    print(f"Используем кэшированный список серверов ({len(account['servers'])} шт)")
                                    if temp_browser_created:
                                        browser.close()
                                        playwright.stop()
                                    return True
                                raise Exception("Список серверов не найден")

                        # Получаем все блоки серверов
                        server_blocks = page.query_selector_all(".jewel.group.layout.vertical.gap-8x1px")
                        print(f"Найдено блоков серверов: {len(server_blocks)}")

                        server_names = set()  # Для отслеживания дублирующихся имен серверов

                        for block in server_blocks:
                            try:
                                # Проверяем, что это блок сервера (содержит имя сервера)
                                name_element = block.query_selector("#displayName")
                                if not name_element or not name_element.inner_text():
                                    continue  # Пропускаем пустые блоки

                                server_name = name_element.inner_text()

                                # Пропускаем серверы с дублирующимися именами
                                if server_name in server_names:
                                    continue

                                # Добавляем имя в отслеживаемый набор
                                server_names.add(server_name)

                                # Определяем, посещал ли пользователь сервер ранее
                                try:
                                    enter_button = block.query_selector("#enterButton")
                                    button_style = enter_button.get_attribute("style") or ""
                                    button_class = enter_button.get_attribute("class") or ""

                                    visited = "-1350px -184px" in button_style
                                    disabled = "disabled" in button_class
                                except:
                                    visited = False
                                    disabled = True

                                # Получаем статус сервера (если есть)
                                server_state = ""
                                try:
                                    state_element = block.query_selector("#serverState")
                                    if state_element:
                                        server_state = state_element.inner_text()
                                except:
                                    pass

                                # Получаем статистику сервера
                                online_count = 0
                                active_count = 0
                                total_count = 0

                                try:
                                    online_label = block.query_selector("#onlineLabel")
                                    if online_label and online_label.inner_text().isdigit():
                                        online_count = int(online_label.inner_text())
                                except:
                                    pass

                                try:
                                    active_label = block.query_selector("#activeLabel")
                                    if active_label and active_label.inner_text().isdigit():
                                        active_count = int(active_label.inner_text())
                                except:
                                    pass

                                try:
                                    total_label = block.query_selector("#totalLabel")
                                    if total_label and total_label.inner_text().isdigit():
                                        total_count = int(total_label.inner_text())
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
                    except Exception as selector_error:
                        print(f"Ошибка при получении серверов через селекторы: {selector_error}")

                # Если не получили ни одного сервера, но есть кэшированные - используем их
                if not servers and account.get('servers'):
                    print(f"Список серверов пуст, используем кэшированные данные ({len(account['servers'])} шт)")
                    if temp_browser_created:
                        browser.close()
                        playwright.stop()
                    return True

                # Обновляем информацию о серверах в аккаунте, если получили хотя бы один сервер
                if servers:
                    account['servers'] = servers
                    self.save_accounts()
                    print(f"Обновлено {len(servers)} серверов для аккаунта {account['username']}")
                else:
                    print("Не найдено ни одного сервера!")

                # Если мы создали временный браузер, закрываем его
                if temp_browser_created:
                    print(f"Закрытие временного браузера после обновления серверов для {account['username']}...")
                    browser.close()
                    playwright.stop()
                else:
                    # Иначе сохраняем браузер и страницу для повторного использования
                    self.browsers[account['username']] = browser
                    self.pages[account['username']] = page
                    # В этом случае НЕ закрываем playwright, так как он используется другими браузерами

                print(f"Обновление серверов для аккаунта {account['username']} завершено успешно")
                return True

            except Exception as e:
                print(f"Ошибка при обновлении серверов: {e}")

                # Если мы создали временный браузер, закрываем его даже при ошибке
                if temp_browser_created:
                    try:
                        if browser:
                            browser.close()
                        playwright.stop()
                        print(f"Закрыт временный браузер после ошибки для {account['username']}")
                    except Exception as close_error:
                        print(f"Ошибка при закрытии временного браузера: {close_error}")

                # Если в аккаунте уже есть серверы, используем их и возвращаем успех
                if account.get('servers'):
                    print(f"Ошибка обновления, используем кэшированный список серверов ({len(account['servers'])} шт)")
                    return True

                return False
        else:
            print("Неверный номер аккаунта")
            return False

    def enter_server(self, page, server_name):
        """Вход на указанный сервер"""
        try:
            print(f"Вход на сервер {server_name}...")

            # Разные подходы в зависимости от режима
            if self.minimal_mode:
                # Минимальный режим: используем JavaScript напрямую
                try:
                    # Проверяем, что мы на странице со списком серверов
                    servers_view_exists = page.evaluate("""() => {
                        return document.getElementById('serversView') !== null;
                    }""")

                    if not servers_view_exists:
                        print("Список серверов не найден, пробуем перейти на главную страницу")

                        # Пробуем загрузить страницу без ожидания полной загрузки
                        try:
                            page.goto(self.game_url, timeout=5000, wait_until="commit")
                        except TimeoutError:
                            print("Таймаут загрузки, продолжаем работу с тем, что есть")
                            pass

                        # Проверяем еще раз
                        servers_view_exists = page.evaluate("""() => {
                            return document.getElementById('serversView') !== null;
                        }""")

                        if not servers_view_exists:
                            print("Список серверов не найден после перехода на главную")
                            return False

                    # Используем JavaScript для поиска и клика по кнопке входа
                    server_entered = page.evaluate("""(serverName) => {
                        // Ищем все элементы с названиями серверов
                        const nameElements = document.querySelectorAll('#displayName');

                        for (const element of nameElements) {
                            if (element.textContent.trim() === serverName) {
                                // Нашли нужный сервер, ищем родительский блок (4 уровня вверх)
                                let parent = element;
                                for (let i = 0; i < 4; i++) {
                                    parent = parent.parentElement;
                                    if (!parent) break;
                                }

                                if (!parent) continue;

                                // Находим кнопку входа в блоке
                                const enterButton = parent.querySelector('#enterButton');
                                if (!enterButton) return false;

                                // Проверяем, не отключен ли сервер
                                if (enterButton.classList.contains('disabled')) {
                                    console.log(`Сервер ${serverName} недоступен (отключен)`);
                                    return false;
                                }

                                // Кликаем на кнопку входа
                                enterButton.click();
                                return true;
                            }
                        }

                        console.log(`Сервер ${serverName} не найден в списке`);
                        return false;
                    }""", server_name)

                    if server_entered:
                        print(f"Выполнен вход на сервер {server_name}")
                        # Короткая пауза для инициации загрузки игры
                        time.sleep(1)
                        return True
                    else:
                        print(f"Не удалось войти на сервер {server_name}")
                        return False

                except Exception as js_error:
                    print(f"Ошибка при входе на сервер через JavaScript: {js_error}")
                    return False

            else:
                # Стандартный режим: используем селекторы
                # Проверяем, что мы на странице со списком серверов, без длительного ожидания
                if not page.is_visible("#serversView", timeout=3000):
                    print("Переход на страницу со списком серверов...")
                    page.goto(self.game_url, wait_until='domcontentloaded', timeout=10000)
                    if not page.is_visible("#serversView", timeout=3000):
                        print("Не удалось найти список серверов")
                        return False

                # Ищем все элементы с названиями серверов
                found = False
                server_name_elements = page.query_selector_all("#displayName")

                for element in server_name_elements:
                    if element.inner_text() == server_name:
                        # Нашли нужный сервер, ищем блок сервера (поднимаемся на 4 уровня вверх)
                        parent_block = element
                        for _ in range(4):
                            parent_block = parent_block.evaluate("el => el.parentElement")
                            if not parent_block:
                                break

                        # Если не смогли найти родительский блок, пропускаем
                        if not parent_block:
                            continue

                        # Находим кнопку входа в блоке
                        enter_button = page.evaluate("""(parentBlock, serverName) => {
                            const button = parentBlock.querySelector("#enterButton");
                            if (!button) return null;

                            // Проверяем, не отключен ли сервер
                            if (button.classList.contains("disabled")) {
                                console.log(`Сервер ${serverName} недоступен (отключен)`);
                                return null;
                            }
                            return button;
                        }""", parent_block, server_name)

                        if not enter_button:
                            print(f"Сервер {server_name} недоступен (отключен)")
                            return False

                        # Кликаем на кнопку входа
                        page.evaluate("button => button.click()", enter_button)
                        print(f"Выполнен вход на сервер {server_name}")

                        # Короткое ожидание вместо долгого
                        time.sleep(1)
                        found = True
                        return True

                if not found:
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

        # Получаем экземпляр Playwright для этого потока
        playwright = self._get_playwright()
        if not playwright:
            print("Не удалось инициализировать Playwright")
            return False

        # Проверяем, есть ли уже запущенный браузер
        browser = self.browsers.get(account['username'])
        page = self.pages.get(account['username'])

        if not browser or not page:
            # Создаем новый браузер
            browser, page, _ = self.create_browser(account, playwright_instance=playwright)
            if not browser or not page:
                print("Не удалось создать браузер для запуска аккаунта")
                playwright.stop()
                return False

        try:
            # Логинимся, если необходимо
            login_result = self.login_account(page, account)
            if not login_result:
                print(f"Не удалось войти в аккаунт {account['username']}")
                playwright.stop()
                return False

            # Входим на выбранный сервер
            server_result = self.enter_server(page, account['last_server'])
            if not server_result:
                print(f"Не удалось войти на сервер {account['last_server']}")
                # Сохраняем браузер для повторного использования
                self.browsers[account['username']] = browser
                self.pages[account['username']] = page
                # НЕ закрываем playwright, так как он используется браузером
                return False

            # Сохраняем браузер для повторного использования
            self.browsers[account['username']] = browser
            self.pages[account['username']] = page

            print(f"Аккаунт {account['username']} успешно запущен на сервере {account['last_server']}")
            # НЕ закрываем playwright, так как он используется браузером
            return True

        except Exception as e:
            print(f"Ошибка при запуске аккаунта: {e}")
            # Если произошла ошибка, сохраняем браузер для повторного использования
            self.browsers[account['username']] = browser
            self.pages[account['username']] = page
            # НЕ закрываем playwright, так как он используется браузером
            return False

    def close_browser(self, account_idx):
        """Закрытие браузера для указанного аккаунта"""
        if 0 <= account_idx < len(self.accounts):
            account = self.accounts[account_idx]

            if account['username'] in self.browsers:
                try:
                    print(f"Закрытие браузера для аккаунта {account['username']}...")
                    self.browsers[account['username']].close()
                    del self.browsers[account['username']]
                    if account['username'] in self.pages:
                        del self.pages[account['username']]
                    print(f"Браузер для аккаунта {account['username']} закрыт")
                    return True
                except Exception as e:
                    print(f"Ошибка при закрытии браузера: {e}")
                    # Удаляем браузер из списка даже при ошибке
                    if account['username'] in self.browsers:
                        del self.browsers[account['username']]
                    if account['username'] in self.pages:
                        del self.pages[account['username']]
                    return False
            else:
                print(f"Для аккаунта {account['username']} нет запущенного браузера")
                return False
        else:
            print("Неверный номер аккаунта")
            return False

    def close_all_browsers(self):
        """Закрытие всех браузеров"""
        if not self.browsers:
            print("Нет запущенных браузеров")
            return True

        closed = 0
        errors = 0

        for username, browser in list(self.browsers.items()):
            try:
                print(f"Закрытие браузера для аккаунта {username}...")
                browser.close()
                del self.browsers[username]
                if username in self.pages:
                    del self.pages[username]
                closed += 1
            except Exception as e:
                print(f"Ошибка при закрытии браузера для {username}: {e}")
                # Удаляем браузер из списка даже при ошибке
                if username in self.browsers:
                    del self.browsers[username]
                if username in self.pages:
                    del self.pages[username]
                errors += 1

        print(f"Закрыто браузеров: {closed}, с ошибками: {errors}")

        # В этой реализации экземпляры Playwright не хранятся глобально,
        # поэтому здесь не нужно их освобождать

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

        status = "Запущен" if account['username'] in parent.bot.browsers else "Остановлен"
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

        status = "Запущен" if account['username'] in self.parent().bot.browsers else "Остановлен"
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

        # Добавление флажка для минимального режима
        settings_frame = QFrame(right_panel)
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        self.minimal_mode_checkbox = QCheckBox("Минимальный режим (для медленного интернета)")
        self.minimal_mode_checkbox.setChecked(self.bot.minimal_mode)
        self.minimal_mode_checkbox.stateChanged.connect(self.toggle_minimal_mode)
        self.minimal_mode_checkbox.setStyleSheet("color: white;")

        settings_layout.addWidget(self.minimal_mode_checkbox)
        right_layout.insertWidget(0, settings_frame)

    def toggle_minimal_mode(self, state):
        """Переключение минимального режима"""
        self.bot.minimal_mode = bool(state)
        print(f"Минимальный режим {'включен' if self.bot.minimal_mode else 'выключен'}")

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
            if account['username'] in self.bot.browsers:
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

        try:
            # Обновляем серверы
            result = self.bot.update_account_servers(account_idx)

            if result:
                print(f"Серверы для {account['username']} обновлены")
                # Возвращаем обновленные серверы
                return account.get('servers', []), account
            else:
                print(f"Ошибка при обновлении серверов для {account['username']}")
                raise Exception("Не удалось обновить серверы")
        except Exception as e:
            print(f"Исключение при обновлении серверов: {e}")
            raise Exception(f"Ошибка при обновлении серверов: {e}")

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
        if not self.bot.browsers:
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