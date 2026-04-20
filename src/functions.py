import aiohttp
import uuid
import json
import logging
import random
from config import config
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class XUIAPI:
    def __init__(self):
        self.session = None
        self.cookie_jar = aiohttp.CookieJar(unsafe=True)  # Разрешаем небезопасные куки
        self.auth_cookies = None

    async def login(self):
        """Аутентификация в 3x-UI API"""
        try:
            # Создаем новую сессию с общей куки-банкой и настройкой SSL
            connector = aiohttp.TCPConnector(ssl=config.XUI_VERIFY_SSL)
            self.session = aiohttp.ClientSession(
                connector=connector,
                cookie_jar=self.cookie_jar,
                trust_env=True  # Доверять переменным окружения для прокси
            )
            
            auth_data = {
                "username": config.XUI_USERNAME,
                "password": config.XUI_PASSWORD
            }
            
            # Формируем URL с учетом базового пути
            base_url = config.XUI_API_URL.rstrip('/')
            # base_path = config.XUI_BASE_PATH.strip('/')
            # if base_path:
            #     base_url = f"{base_url}/{base_path}"
            login_url = f"{base_url}/login"
            
            logger.info(f"ℹ️  Trying login to {login_url} with user: {config.XUI_USERNAME}")
            
            async with self.session.post(login_url, data=auth_data) as resp:
                if resp.status != 200:
                    logger.error(f"🛑 Login failed with status: {resp.status}")
                    return False
                
                # Проверяем JSON ответ
                try:
                    response = await resp.json()
                    if response.get("success"):
                        logger.info("✅ Login successful")
                        # Сохраняем куки для последующих запросов
                        self.auth_cookies = self.cookie_jar
                        logger.debug(f"⚙️ Auth cookies: {self.auth_cookies}")
                        return True
                    else:
                        logger.error(f"🛑 Login failed: {response.get('msg')}")
                        return False
                except:
                    # Если ответ не JSON, проверяем текст
                    text = await resp.text()
                    if "success" in text.lower():
                        logger.warning("⚠️ Login successful (text response)")
                        # Сохраняем куки для последующих запросов
                        self.auth_cookies = self.cookie_jar
                        logger.debug(f"⚙️ Auth cookies: {self.auth_cookies}")
                        return True
                    logger.error(f"🛑 Login failed. Response text: {text[:100]}...")
                    return False
        except Exception as e:
            logger.exception(f"🛑 Login error: {e}")
            return False

    async def get_inbound(self, inbound_id: int):
        """Получение данных инбаунда"""
        try:
            base_url = config.XUI_API_URL.rstrip('/')
            base_path = config.XUI_BASE_PATH.strip('/')
            if base_path:
                base_url = f"{base_url}/{base_path}"
            url = f"{base_url}/api/inbounds/get/{inbound_id}"
            
            logger.info(f"ℹ️  Getting inbound data from: {url}")
            logger.debug(f"⚙️ Using cookies: {self.cookie_jar}")
            
            async with self.session.get(url) as resp:
                logger.debug(f"⚙️ Response status: {resp.status}")
                logger.debug(f"⚙️ Response cookies: {resp.cookies}")
                
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"🛑 Get inbound failed: status={resp.status}, response={text[:100]}...")
                    return None
                
                try:
                    data = await resp.json()
                    if data.get("success"):
                        logger.debug(f'⚙️ Data: {str(data)}')
                        return data.get("obj")
                    else:
                        logger.error(f"🛑 Get inbound failed: {data.get('msg')}")
                        return None
                except:
                    text = await resp.text()
                    logger.error(f"🛑 Get inbound response error: {text[:100]}...")
                    return None
        except Exception as e:
            logger.exception(f"🛑 Get inbound error: {e}")
            return None

    async def update_inbound(self, inbound_id: int, data: dict):
        """Обновление инбаунда"""
        try:
            base_url = config.XUI_API_URL.rstrip('/')
            base_path = config.XUI_BASE_PATH.strip('/')
            if base_path:
                base_url = f"{base_url}/{base_path}"
            url = f"{base_url}/api/inbounds/update/{inbound_id}"
            
            logger.info(f"ℹ️  Updating inbound at: {url}")
            
            async with self.session.post(url, json=data) as resp:
                if resp.status != 200:
                    logger.error(f"🛑 Update inbound failed with status: {resp.status}")
                    return False
                
                try:
                    response = await resp.json()
                    return response.get("success", False)
                except:
                    text = await resp.text()
                    return "success" in text.lower()
        except Exception as e:
            logger.exception(f"🛑 Update inbound error: {e}")
            return False

    async def _get_flow_from_inbound(self, inbound: dict) -> str:
        """Получает flow из настроек инбаунда или streamSettings"""
        try:
            # Пробуем получить из settings
            settings = json.loads(inbound.get("settings", "{}"))
            
            # Сначала проверяем streamSettings для Reality
            stream_settings = json.loads(inbound.get("streamSettings", "{}"))
            reality_settings = stream_settings.get("realitySettings", {})
            
            # Если есть Reality настройки, проверяем flow
            if reality_settings:
                # Проверяем settings -> clients на наличие flow
                clients = settings.get("clients", [])
                if clients and len(clients) > 0:
                    existing_flow = clients[0].get("flow", "")
                    if existing_flow:
                        return existing_flow
                
                # Если в streamSettings есть flow
                return reality_settings.get("flow", "")
            
            # Проверяем наличие flow в существующих клиентах
            clients = settings.get("clients", [])
            if clients and len(clients) > 0:
                existing_flow = clients[0].get("flow", "")
                if existing_flow:
                    return existing_flow
            
        except Exception as e:
            logger.warning(f"⚠️ Could not get flow from inbound: {e}")
        
        return ""
    
    async def create_vless_profile(self, telegram_id: int):
        """Создание нового клиента для пользователя"""
        if not await self.login():
            logger.error("🛑 Login failed before creating profile")
            return None
        
        inbound = await self.get_inbound(config.INBOUND_ID)
        if not inbound:
            logger.error(f"🛑 Inbound {config.INBOUND_ID} not found")
            return None
        
        try:
            settings = json.loads(inbound["settings"])
            clients = settings.get("clients", [])
            
            client_id = str(uuid.uuid4())
            email = f"user_{telegram_id}_{random.randint(1000,9999)}"
            
            # Получаем flow из инбаунда
            flow = await self._get_flow_from_inbound(inbound)
            
            # Обновленные настройки для Reality
            # Генерируем постоянный UUID для subscription на основе telegram_id
            sub_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_{telegram_id}"))
            
            new_client = {
                "id": client_id,
                "flow": flow,
                "email": email,
                "limitIp": 0,
                "totalGB": 0,
                "expiryTime": 0,
                "enable": True,
                "tgId": "",
                "subId": sub_id,
                "reset": 0,
                "fingerprint": config.REALITY_FINGERPRINT,
                "publicKey": config.REALITY_PUBLIC_KEY,
                "shortId": config.REALITY_SHORT_ID,
                "spiderX": config.REALITY_SPIDER_X
            }
            
            clients.append(new_client)
            settings["clients"] = clients
            
            update_data = {
                "up": inbound["up"],
                "down": inbound["down"],
                "total": inbound["total"],
                "remark": inbound["remark"],
                "enable": inbound["enable"],
                "expiryTime": inbound["expiryTime"],
                "listen": inbound["listen"],
                "port": inbound["port"],
                "protocol": inbound["protocol"],
                "settings": json.dumps(settings, indent=2),
                "streamSettings": inbound["streamSettings"],
                "sniffing": inbound["sniffing"],
            }
            
            if await self.update_inbound(config.INBOUND_ID, update_data):
                return {
                    "client_id": client_id,
                    "email": email,
                    "port": inbound["port"],
                    "security": "reality",
                    "remark": inbound["remark"],
                    "sni": config.REALITY_SNI,
                    "pbk": config.REALITY_PUBLIC_KEY,
                    "fp": config.REALITY_FINGERPRINT,
                    "sid": config.REALITY_SHORT_ID,
                    "spx": config.REALITY_SPIDER_X,
                    "sub_id": sub_id
                }
            return None
        except Exception as e:
            logger.exception(f"🛑 Create profile error: {e}")
            return None

    async def create_static_client(self, profile_name: str):
        """Создание статического клиента"""
        if not await self.login():
            logger.error("🛑 Login failed before creating static client")
            return None
        
        inbound = await self.get_inbound(config.INBOUND_ID)
        if not inbound:
            logger.error(f"🛑 Inbound {config.INBOUND_ID} not found")
            return None
        
        try:
            settings = json.loads(inbound["settings"])
            clients = settings.get("clients", [])
            
            client_id = str(uuid.uuid4())
            
            # Генерируем постоянный UUID для subscription на основе имени профиля
            sub_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"static_{profile_name}"))
            
            # Получаем flow из инбаунда
            flow = await self._get_flow_from_inbound(inbound)
            
            # Обновленные настройки для Reality
            new_client = {
                "id": client_id,
                "flow": flow,
                "email": profile_name,
                "limitIp": 0,
                "totalGB": 0,
                "expiryTime": 0,
                "enable": True,
                "tgId": "",
                "subId": sub_id,
                "reset": 0,
                "fingerprint": config.REALITY_FINGERPRINT,
                "publicKey": config.REALITY_PUBLIC_KEY,
                "shortId": config.REALITY_SHORT_ID,
                "spiderX": config.REALITY_SPIDER_X
            }
            
            clients.append(new_client)
            settings["clients"] = clients
            
            update_data = {
                "up": inbound["up"],
                "down": inbound["down"],
                "total": inbound["total"],
                "remark": inbound["remark"],
                "enable": inbound["enable"],
                "expiryTime": inbound["expiryTime"],
                "listen": inbound["listen"],
                "port": inbound["port"],
                "protocol": inbound["protocol"],
                "settings": json.dumps(settings, indent=2),
                "streamSettings": inbound["streamSettings"],
                "sniffing": inbound["sniffing"],
            }
            
            if await self.update_inbound(config.INBOUND_ID, update_data):
                return {
                    "client_id": client_id,
                    "email": profile_name,
                    "port": inbound["port"],
                    # Указываем тип безопасности как reality
                    "security": "reality",
                    "remark": inbound["remark"],
                    # Добавляем необходимые параметры для Reality
                    "sni": config.REALITY_SNI,
                    "pbk": config.REALITY_PUBLIC_KEY,
                    "fp": config.REALITY_FINGERPRINT,
                    "sid": config.REALITY_SHORT_ID,
                    "spx": config.REALITY_SPIDER_X,
                    "sub_id": sub_id
                }
            return None
        except Exception as e:
            logger.exception(f"🛑 Create static client error: {e}")
            return None

    async def delete_client(self, email: str):
        """Удаление клиента по email"""
        if not await self.login():
            return False
        
        try:
            # Получаем данные инбаунда
            inbound = await self.get_inbound(config.INBOUND_ID)
            if not inbound:
                return False
            
            settings = json.loads(inbound["settings"])
            clients = settings.get("clients", [])
            
            # Фильтруем клиентов
            new_clients = [c for c in clients if c["email"] != email]
            
            # Если не было изменений
            if len(new_clients) == len(clients):
                return False
            
            settings["clients"] = new_clients
            
            # Формируем данные для обновления
            update_data = {
                "up": inbound["up"],
                "down": inbound["down"],
                "total": inbound["total"],
                "remark": inbound["remark"],
                "enable": inbound["enable"],
                "expiryTime": inbound["expiryTime"],
                "listen": inbound["listen"],
                "port": inbound["port"],
                "protocol": inbound["protocol"],
                "settings": json.dumps(settings, indent=2),
                "streamSettings": inbound["streamSettings"],
                "sniffing": inbound["sniffing"],
                "allocate": inbound["allocate"]
            }
            
            return await self.update_inbound(config.INBOUND_ID, update_data)
        except Exception as e:
            logger.exception(f"🛑 Delete client error: {e}")
            return False
    
    async def get_user_stats(self, email: str):
        """Получение статистики по email"""
        if not await self.login():
            logger.error("🛑 Login failed before getting stats")
            return {"upload": 0, "download": 0}
        
        try:
            base_url = config.XUI_API_URL.rstrip('/')
            base_path = config.XUI_BASE_PATH.strip('/')
            if base_path:
                base_url = f"{base_url}/{base_path}"
            url = f"{base_url}/api/inbounds/getClientTraffics/{email}"
            
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return {"upload": 0, "download": 0}
                
                try:
                    data = await resp.json()
                    if data.get("success"):
                        client_data = data.get("obj")
                        if isinstance(client_data, dict):
                            return {
                                "upload": client_data.get("up", 0),
                                "download": client_data.get("down", 0)
                            }
                except:
                    return {"upload": 0, "download": 0}
        except Exception as e:
            logger.error(f"🛑 Stats error: {e}")
        return {"upload": 0, "download": 0}
    
    async def get_global_stats(self, inbound_id: int):
        """Получение статистики по email"""
        if not await self.login():
            logger.error("🛑 Login failed before getting stats")
            return {"upload": 0, "download": 0}
        
        try:
            base_url = config.XUI_API_URL.rstrip('/')
            base_path = config.XUI_BASE_PATH.strip('/')
            if base_path:
                base_url = f"{base_url}/{base_path}"
            url = f"{base_url}/api/inbounds/get/{inbound_id}"
            
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return {"upload": 0, "download": 0}
                
                try:
                    data = await resp.json()
                    if data.get("success"):
                        client_data = data.get("obj")
                        if isinstance(client_data, dict):
                            return {
                                "upload": client_data.get("up", 0),
                                "download": client_data.get("down", 0)
                            }
                except:
                    return {"upload": 0, "download": 0}
        except Exception as e:
            logger.error(f"🛑 Stats error: {e}")
        return {"upload": 0, "download": 0}

    async def get_online_users(self):
        if not await self.login():
            logger.error("🛑 Login failed before getting stats")
            return {"upload": 0, "download": 0}
        
        try:
            base_url = config.XUI_API_URL.rstrip('/')
            base_path = config.XUI_BASE_PATH.strip('/')
            if base_path:
                base_url = f"{base_url}/{base_path}"
            url = f"{base_url}/api/inbounds/onlines"
            
            async with self.session.post(url) as resp:
                if resp.status != 200:
                    return 0

                
                try:
                    data = await resp.json()
                    logger.debug(data)
                    online = 0
                    if data.get("success"):
                        users = data.get("obj")
                        if isinstance(users, list):
                            for user in users:
                                if str(user).startswith("user_"):
                                    online += 1
                        return online
                except:
                    return 0
        except Exception as e:
            logger.error(f"🛑 Stats error: {e}")
        return {"upload": 0, "download": 0}

    async def close(self):
        if self.session:
            await self.session.close()

async def create_vless_profile(telegram_id: int):
    api = XUIAPI()
    try:
        return await api.create_vless_profile(telegram_id)
    finally:
        await api.close()

async def create_static_client(profile_name: str):
    api = XUIAPI()
    try:
        return await api.create_static_client(profile_name)
    finally:
        await api.close()

async def delete_client_by_email(email: str):
    api = XUIAPI()
    try:
        return await api.delete_client(email)
    finally:
        await api.close()

async def get_global_stats():
    api = XUIAPI()
    try:
        return await api.get_global_stats(config.INBOUND_ID)
    finally:
        await api.close()

async def get_online_users():
    api = XUIAPI()
    try:
        return await api.get_online_users()
    finally:
        await api.close()

async def get_user_stats(email: str):
    api = XUIAPI()
    try:
        return await api.get_user_stats(email)
    finally:
        await api.close()

def generate_sub_url(sub_id: str) -> str:
    """Генерирует ссылку на подписку"""
    if not config.SUBSCRIPTION_URL_BASE:
        # Пытаемся сформировать на основе XUI_API_URL, но с портом для подписок
        # Извлекаем схему и хост из XUI_API_URL
        from urllib.parse import urlparse
        parsed = urlparse(config.XUI_API_URL)
        scheme = parsed.scheme or "http"
        host = parsed.hostname or "localhost"
        return f"{scheme}://{host}:{config.XUI_SUB_PORT}/sub/{sub_id}"
    return f"{config.SUBSCRIPTION_URL_BASE.rstrip('/')}/{sub_id}"

def generate_vless_url(profile_data: dict) -> str:
    remark = profile_data.get('remark', '')
    email = profile_data['email']
    fragment = f"{remark}-{email}" if remark else email
    
    return (
        f"vless://{profile_data['client_id']}@{config.XUI_HOST}:{profile_data['port']}"
        f"?type=tcp&security=reality"
        f"&pbk={config.REALITY_PUBLIC_KEY}"
        f"&fp={config.REALITY_FINGERPRINT}"
        f"&sni={config.REALITY_SNI}"
        f"&sid={config.REALITY_SHORT_ID}"
        f"&spx={config.REALITY_SPIDER_X}"
        f"#{fragment}"
    )