import aiohttp
import uuid
import json
import logging
import random
from datetime import timedelta
from typing import Optional
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
            logger.debug(f"🔍 [update_inbound] Data keys: {list(data.keys())}")
            
            # Логируем settings если они есть
            if "settings" in data:
                try:
                    settings = json.loads(data["settings"])
                    clients = settings.get("clients", [])
                    logger.info(f"🔍 [update_inbound] Total clients: {len(clients)}")
                    # Логируем expiryTime для каждого клиента
                    for i, client in enumerate(clients):
                        email = client.get("email", "unknown")
                        expiry_time = client.get("expiryTime", "not set")
                        logger.info(f"🔍 [update_inbound] Client {i}: {email}, expiryTime: {expiry_time}")
                except:
                    logger.warning("⚠️ Could not parse settings for logging")
            
            async with self.session.post(url, json=data) as resp:
                logger.info(f"🔍 [update_inbound] Response status: {resp.status}")
                if resp.status != 200:
                    logger.error(f"🛑 Update inbound failed with status: {resp.status}")
                    text = await resp.text()
                    logger.error(f"🛑 Response text: {text[:200]}")
                    return False
                
                try:
                    response = await resp.json()
                    logger.info(f"🔍 [update_inbound] Response: {response}")
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
    
    async def create_vless_profile(self, telegram_id: int, expiry_time: int = 0):
        """Создание нового клиента для пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            expiry_time: Время истечения в timestamp (0 = бессрочно)
        """
        logger.info(f"🔍 [create_vless_profile] Creating profile for user {telegram_id} with expiry_time: {expiry_time}")
        
        if not await self.login():
            logger.error("🛑 Login failed before creating profile")
            return None
        
        # Если время истечения в прошлом, устанавливаем в 0 (истекло)
        if expiry_time < 0:
            logger.warning(f"⚠️ Expiry time is in the past ({expiry_time}), setting to 0")
            expiry_time = 0
        
        logger.info(f"🔍 [create_vless_profile] Final expiry_time to send: {expiry_time}")
        
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
                "expiryTime": expiry_time * 1000,  # 3x-ui ожидает миллисекунды!
                "enable": True,
                "tgId": "",
                "subId": sub_id,
                "reset": 0,
                "fingerprint": config.REALITY_FINGERPRINT,
                "publicKey": config.REALITY_PUBLIC_KEY,
                "shortId": config.REALITY_SHORT_ID,
                "spiderX": config.REALITY_SPIDER_X
            }
            
            # ЭКСТРЕННАЯ ПРОВЕРКА: если timestamp всё ещё неправильный, устанавливаем в 0
            if expiry_time < 1577836800:  # 1 января 2020 года
                logger.error(f"🚨 EMERGENCY: Expiry time is too small ({expiry_time}), setting to 0!")
                new_client["expiryTime"] = 0
            elif expiry_time > 2000000000:  # Больше 2033 года
                logger.error(f"🚨 EMERGENCY: Expiry time is too large ({expiry_time}), setting to 0!")
                new_client["expiryTime"] = 0
            
            logger.info(f"🔍 [create_vless_profile] Final expiryTime in client (ms): {new_client['expiryTime']}")
            
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
            }
            
            return await self.update_inbound(config.INBOUND_ID, update_data)
        except Exception as e:
            logger.exception(f"🛑 Delete client error: {e}")
            return False
    
    async def update_client_expiry(self, email: str, expiry_time: int):
        """Обновление времени истечения подписки клиента
        
        Args:
            email: Email клиента
            expiry_time: Новое время истечения в timestamp (0 = бессрочно)
        """
        logger.info(f"🔍 [update_client_expiry] Updating client {email} with expiry_time: {expiry_time}")
        
        if not await self.login():
            return False
        
        # Если время истечения в прошлом, устанавливаем в 0 (истекло)
        if expiry_time < 0:
            logger.warning(f"⚠️ Expiry time is in the past ({expiry_time}), setting to 0")
            expiry_time = 0
        
        logger.info(f"🔍 [update_client_expiry] Final expiry_time to send: {expiry_time}")
        
        try:
            # Получаем данные инбаунда
            inbound = await self.get_inbound(config.INBOUND_ID)
            if not inbound:
                return False
            
            settings = json.loads(inbound["settings"])
            clients = settings.get("clients", [])
            
            # Находим и обновляем клиента
            updated = False
            for client in clients:
                if client["email"] == email:
                    # ЭКСТРЕННАЯ ПРОВЕРКА: если timestamp всё ещё неправильный, устанавливаем в 0
                    final_expiry_time = expiry_time
                    if expiry_time < 1577836800:  # 1 января 2020 года
                        logger.error(f"🚨 EMERGENCY: Expiry time is too small ({expiry_time}), setting to 0!")
                        final_expiry_time = 0
                    elif expiry_time > 2000000000:  # Больше 2033 года
                        logger.error(f"🚨 EMERGENCY: Expiry time is too large ({expiry_time}), setting to 0!")
                        final_expiry_time = 0
                    
                    client["expiryTime"] = final_expiry_time * 1000  # 3x-ui ожидает миллисекунды!
                    updated = True
                    logger.info(f"✅ Updated expiry time for {email}: {final_expiry_time * 1000} ms")
                    break
            
            if not updated:
                logger.warning(f"⚠️ Client {email} not found for expiry update")
                return False
            
            settings["clients"] = clients
            
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
                "allocate": inbound.get("allocate", "")
            }
            
            return await self.update_inbound(config.INBOUND_ID, update_data)
        except Exception as e:
            logger.exception(f"🛑 Update client expiry error: {e}")
            return False
    
    async def get_user_stats(self, email: str):
        """Получение статистики по email"""
        if not await self.login():
            logger.error("🛑 Login failed before getting stats")
           # return {"upload": 0, "download": 0}
            return 0
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
    
    async def get_all_clients(self):
        """Получает всех клиентов из inbound"""
        if not await self.login():
            logger.error("🛑 Login failed before getting clients")
            return None
        
        try:
            inbound = await self.get_inbound(config.INBOUND_ID)
            if not inbound:
                logger.error(f"🛑 Inbound {config.INBOUND_ID} not found")
                return None
            
            settings = json.loads(inbound["settings"])
            clients = settings.get("clients", [])
            
            logger.info(f"📋 Retrieved {len(clients)} clients from 3x-ui")
            return clients
        except Exception as e:
            logger.exception(f"🛑 Get all clients error: {e}")
            return None

async def create_vless_profile(telegram_id: int, expiry_time: int = 0):
    """Создание VLESS профиля с указанием времени истечения
    
    Args:
        telegram_id: Telegram ID пользователя
        expiry_time: Время истечения в timestamp (0 = бессрочно)
    """
    api = XUIAPI()
    try:
        return await api.create_vless_profile(telegram_id, expiry_time)
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

async def update_client_expiry(email: str, expiry_time: int):
    """Обновление времени истечения подписки клиента в 3x-ui
    
    Args:
        email: Email клиента
        expiry_time: Новое время истечения в timestamp (0 = бессрочно)
    """
    api = XUIAPI()
    try:
        return await api.update_client_expiry(email, expiry_time)
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
    return f"{config.SUBSCRIPTION_URL_BASE.rstrip('/')}:{config.XUI_SUB_PORT}/sub/{sub_id}"
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

def get_safe_expiry_timestamp(subscription_end) -> int:
    """Безопасно получает timestamp из даты окончания подписки
    
    Args:
        subscription_end: Дата окончания подписки (datetime объект или строка)
        
    Returns:
        Timestamp в секундах (0 если истекла или дата некорректна)
    """
    from datetime import datetime
    
    logger.info(f"🔍 [get_safe_expiry_timestamp] Input: {subscription_end}, type: {type(subscription_end)}")
    
    if subscription_end is None:
        logger.warning("⚠️ Subscription end is None")
        return 0
    
    # Конвертируем строку в datetime если нужно
    if isinstance(subscription_end, str):
        try:
            subscription_end = datetime.fromisoformat(subscription_end)
            logger.info(f"🔄 [get_safe_expiry_timestamp] Конвертирована строка в datetime: {subscription_end}")
        except Exception as e:
            logger.error(f"🛑 [get_safe_expiry_timestamp] Ошибка конвертации строки в datetime: {e}, value: {subscription_end}")
            return 0
    
    # Проверяем, что subscription_end является datetime объектом
    if not isinstance(subscription_end, datetime):
        logger.error(f"🛑 [get_safe_expiry_timestamp] subscription_end не является datetime: {type(subscription_end)}, value: {subscription_end}")
        return 0
    
    now = datetime.utcnow()
    logger.info(f"🔍 [get_safe_expiry_timestamp] Now: {now}, Diff: {subscription_end - now}")
    
    # Проверяем на валидность даты (слишком старая или слишком далекая в будущем)
    if subscription_end < datetime(2020, 1, 1):
        logger.warning(f"⚠️ Subscription end date is too old: {subscription_end}")
        return 0  # Считаем истекшей
    
    # Проверяем на слишком далекое будущее (более 10 лет)
    if subscription_end > now + timedelta(days=3650):
        logger.warning(f"⚠️ Subscription end date is too far in the future: {subscription_end}")
        return 0
    
    # Если дата в прошлом или настоящем, возвращаем 0 (истекла)
    if subscription_end <= now:
        logger.info(f"🔍 [get_safe_expiry_timestamp] Subscription expired or now, returning 0")
        return 0
    
    # Иначе возвращаем корректный timestamp
    try:
        timestamp = int(subscription_end.timestamp())
        logger.info(f"🔍 [get_safe_expiry_timestamp] Calculated timestamp: {timestamp}")
        
        # Дополнительная проверка на отрицательные или слишком маленькие значения
        if timestamp < 0:
            logger.warning(f"⚠️ Negative timestamp detected: {timestamp}, date: {subscription_end}")
            return 0
        
        # Проверяем на слишком маленькие значения (меньше года с 2020)
        if timestamp < 1577836800:  # 1 января 2020 года в timestamp
            logger.warning(f"⚠️ Timestamp is too small: {timestamp}, date: {subscription_end}")
            return 0
        
        logger.info(f"✅ [get_safe_expiry_timestamp] Final timestamp: {timestamp}")
        return timestamp
    except Exception as e:
        logger.error(f"🛑 Error converting date to timestamp: {e}, date: {subscription_end}")
        return 0

async def force_update_profile_expiry(email: str, subscription_end) -> bool:
    """Принудительно обновляет время истечения существующего профиля
    
    Args:
        email: Email клиента
        subscription_end: Новая дата окончания подписки
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        logger.info(f"🔍 [force_update_profile_expiry] Starting for email: {email}, subscription_end: {subscription_end}")
        
        # Получаем безопасный timestamp
        expiry_time = get_safe_expiry_timestamp(subscription_end)
        logger.info(f"🔄 Force updating profile {email} with expiry_time: {expiry_time}")
        
        # Обновляем в 3x-ui
        result = await update_client_expiry(email, expiry_time)
        
        if result:
            logger.info(f"✅ Successfully force updated profile {email}")
        else:
            logger.error(f"🛑 Failed to force update profile {email}")
        
        return result
    except Exception as e:
        logger.error(f"🛑 Error force updating profile {email}: {e}")
        return False

async def check_and_fix_subscriptions() -> dict:
    """Проверяет и исправляет расхождения между 3x-ui и базой данных
    
    Returns:
        Словарь со статистикой проверки
    """
    api = XUIAPI()
    try:
        # Получаем всех клиентов из 3x-ui
        clients_3xui = await api.get_all_clients()
        if not clients_3xui:
            return {"error": "Failed to get clients from 3x-ui"}
        
        # Получаем всех пользователей из базы данных
        from database import get_users_with_profiles
        users_db = await get_users_with_profiles()
        
        # Создаём маппинг email → пользователь
        users_map = {}
        for user in users_db:
            if user.vless_profile_data:
                try:
                    profile_data = safe_json_loads(user.vless_profile_data, default={})
                    email = profile_data.get("email")
                    if email:
                        users_map[email] = user
                except Exception as e:
                    logger.error(f"🛑 Error parsing profile data for user {user.telegram_id}: {e}")
        
        # Статистика
        stats = {
            "total_3xui": len(clients_3xui),
            "total_db": len(users_db),
            "matched": 0,
            "mismatch": 0,
            "fixed": 0,
            "not_in_db": 0,
            "details": []
        }
        
        # Проверяем каждого клиента из 3x-ui
        for client in clients_3xui:
            email = client.get("email")
            expiry_time_3xui = client.get("expiryTime", 0)
            
            # Пропускаем Base клиента
            if email == "Base":
                continue
            
            if not email:
                continue
            
            # Конвертируем миллисекунды в секунды
            expiry_time_3xui_seconds = expiry_time_3xui // 1000 if expiry_time_3xui > 0 else 0
            
            # Проверяем, есть ли пользователь в базе
            if email not in users_map:
                stats["not_in_db"] += 1
                stats["details"].append({
                    "email": email,
                    "status": "not_in_db",
                    "expiry_3xui": expiry_time_3xui_seconds,
                    "expiry_db": None
                })
                continue
            
            # Получаем пользователя из базы
            user = users_map[email]
            
            # Конвертируем дату из базы в timestamp
            try:
                from datetime import datetime
                if isinstance(user.subscription_end, str):
                    sub_end_db = datetime.fromisoformat(user.subscription_end)
                else:
                    sub_end_db = user.subscription_end
                
                expiry_time_db = int(sub_end_db.timestamp()) if sub_end_db > datetime.utcnow() else 0
                
                # Сравниваем (допускаем разницу в 1 минуту из-за округления)
                diff = abs(expiry_time_3xui_seconds - expiry_time_db)
                
                if diff <= 60:  # Разница менее минуты - считаем совпадением
                    stats["matched"] += 1
                    stats["details"].append({
                        "email": email,
                        "telegram_id": user.telegram_id,
                        "status": "matched",
                        "expiry_3xui": expiry_time_3xui_seconds,
                        "expiry_db": expiry_time_db,
                        "diff": diff
                    })
                else:
                    stats["mismatch"] += 1
                    logger.warning(f"⚠️ Mismatch for {email}: 3x-ui={expiry_time_3xui_seconds}, DB={expiry_time_db}, diff={diff}")
                    
                    # Исправляем
                    try:
                        result = await force_update_profile_expiry(email, user.subscription_end)
                        if result:
                            stats["fixed"] += 1
                            stats["details"].append({
                                "email": email,
                                "telegram_id": user.telegram_id,
                                "status": "fixed",
                                "expiry_3xui": expiry_time_3xui_seconds,
                                "expiry_db": expiry_time_db,
                                "diff": diff
                            })
                        else:
                            stats["details"].append({
                                "email": email,
                                "telegram_id": user.telegram_id,
                                "status": "fix_failed",
                                "expiry_3xui": expiry_time_3xui_seconds,
                                "expiry_db": expiry_time_db,
                                "diff": diff
                            })
                    except Exception as e:
                        logger.error(f"🛑 Error fixing subscription for {email}: {e}")
                        stats["details"].append({
                            "email": email,
                            "telegram_id": user.telegram_id,
                            "status": "fix_error",
                            "expiry_3xui": expiry_time_3xui_seconds,
                            "expiry_db": expiry_time_db,
                            "diff": diff,
                            "error": str(e)
                        })
            except Exception as e:
                logger.error(f"🛑 Error processing user {user.telegram_id}: {e}")
        
        logger.info(f"📊 Subscription check completed: {stats}")
        return stats
        
    except Exception as e:
        logger.exception(f"🛑 Error in check_and_fix_subscriptions: {e}")
        return {"error": str(e)}
    finally:
        await api.close()

# ========== Функции для временных профилей ==========

async def create_temp_profile(session_id: str) -> Optional[dict]:
    """Создание временного профиля для web сервера
    
    Args:
        session_id: Уникальный идентификатор сессии
        
    Returns:
        Данные профиля или None в случае ошибки
    """
    from datetime import timedelta
    
    logger.info(f"🔍 Creating temp profile for session {session_id}")
    
    api = XUIAPI()
    try:
        # Вычисляем время истечения (текущее + 30 минут)
        expiry_time = int((datetime.utcnow() + timedelta(minutes=30)).timestamp())
        logger.info(f"🔍 Temp profile expiry time: {expiry_time}")
        
        # Получаем данные временного инбаунда
        inbound = await api.get_inbound(config.TEMP_INBOUND_ID)
        if not inbound:
            logger.error(f"🛑 Temp inbound {config.TEMP_INBOUND_ID} not found")
            return None
        
        settings = json.loads(inbound["settings"])
        clients = settings.get("clients", [])
        
        client_id = str(uuid.uuid4())
        email = f"temp_{session_id}_{random.randint(1000, 9999)}"
        
        # Получаем flow из инбаунда
        flow = await api._get_flow_from_inbound(inbound)
        
        # Генерируем sub_id
        sub_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"temp_{session_id}"))
        
        new_client = {
            "id": client_id,
            "flow": flow,
            "email": email,
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": expiry_time * 1000,  # 3x-ui ожидает миллисекунды!
            "enable": True,
            "tgId": "",
            "subId": sub_id,
            "reset": 0,
            "fingerprint": config.TEMP_REALITY_FINGERPRINT,
            "publicKey": config.TEMP_REALITY_PUBLIC_KEY,
            "shortId": config.TEMP_REALITY_SHORT_ID,
            "spiderX": config.TEMP_REALITY_SPIDER_X
        }
        
        logger.info(f"🔍 Creating temp client: {email}, expiryTime: {new_client['expiryTime']}")
        
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
        
        if await api.update_inbound(config.TEMP_INBOUND_ID, update_data):
            logger.info(f"✅ Temp profile created successfully: {email}")
            return {
                "client_id": client_id,
                "email": email,
                "port": inbound["port"],
                "security": "reality",
                "remark": inbound["remark"],
                "sni": config.TEMP_REALITY_SNI,
                "pbk": config.TEMP_REALITY_PUBLIC_KEY,
                "fp": config.TEMP_REALITY_FINGERPRINT,
                "sid": config.TEMP_REALITY_SHORT_ID,
                "spx": config.TEMP_REALITY_SPIDER_X,
                "sub_id": sub_id,
                "expiry_time": expiry_time
            }
        return None
    except Exception as e:
        logger.exception(f"🛑 Create temp profile error: {e}")
        return None
    finally:
        await api.close()


async def delete_temp_profile(email: str) -> bool:
    """Удаление временного профиля
    
    Args:
        email: Email клиента для удаления
        
    Returns:
        True если успешно, False если ошибка
    """
    logger.info(f"🔍 Deleting temp profile: {email}")
    
    api = XUIAPI()
    try:
        # Получаем данные временного инбаунда
        inbound = await api.get_inbound(config.TEMP_INBOUND_ID)
        if not inbound:
            return False
        
        settings = json.loads(inbound["settings"])
        clients = settings.get("clients", [])
        
        # Фильтруем клиентов
        new_clients = [c for c in clients if c["email"] != email]
        
        # Если не было изменений
        if len(new_clients) == len(clients):
            logger.warning(f"⚠️ Temp profile {email} not found")
            return False
        
        settings["clients"] = new_clients
        
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
        
        result = await api.update_inbound(config.TEMP_INBOUND_ID, update_data)
        if result:
            logger.info(f"✅ Temp profile deleted successfully: {email}")
        else:
            logger.error(f"🛑 Failed to delete temp profile: {email}")
        
        return result
    except Exception as e:
        logger.exception(f"🛑 Delete temp profile error: {e}")
        return False
    finally:
        await api.close()


def generate_vless_url_temp(profile_data: dict) -> str:
    """Генерирует VLESS URL для временного профиля
    
    Args:
        profile_data: Данные профиля
        
    Returns:
        VLESS URL строка
    """
    remark = profile_data.get('remark', 'Temp Profile')
    email = profile_data['email']
    fragment = f"{remark}-{email}" if remark else email
    
    return (
        f"vless://{profile_data['client_id']}@{config.XUI_HOST}:{profile_data['port']}"
        f"?type=tcp&security=reality"
        f"&pbk={config.TEMP_REALITY_PUBLIC_KEY}"
        f"&fp={config.TEMP_REALITY_FINGERPRINT}"
        f"&sni={config.TEMP_REALITY_SNI}"
        f"&sid={config.TEMP_REALITY_SHORT_ID}"
        f"&spx={config.TEMP_REALITY_SPIDER_X}"
        f"#{fragment}"
    )


async def cleanup_expired_temp_profiles():
    """Очистка истекших временных профилей
    
    Returns:
        Количество удаленных профилей
    """
    from datetime import timedelta
    
    logger.info("🧹 Starting cleanup of expired temp profiles...")
    
    api = XUIAPI()
    deleted_count = 0
    
    try:
        # Получаем всех клиентов из временного инбаунда
        inbound = await api.get_inbound(config.TEMP_INBOUND_ID)
        if not inbound:
            logger.error(f"🛑 Temp inbound {config.TEMP_INBOUND_ID} not found")
            return 0
        
        settings = json.loads(inbound["settings"])
        clients = settings.get("clients", [])
        
        # Находим истекшие профили (email начинается с "temp_")
        now = datetime.utcnow()
        expired_clients = []
        
        for client in clients:
            email = client.get("email", "")
            if not email.startswith("temp_"):
                continue
            
            expiry_time_ms = client.get("expiryTime", 0)
            if expiry_time_ms == 0:
                continue
            
            expiry_time = expiry_time_ms / 1000  # Конвертируем в секунды
            expiry_datetime = datetime.fromtimestamp(expiry_time)
            
            if expiry_datetime <= now:
                expired_clients.append(email)
                logger.info(f"🗑️ Found expired temp profile: {email} (expired at {expiry_datetime})")
        
        # Удаляем истекшие профили
        if expired_clients:
            new_clients = [c for c in clients if c["email"] not in expired_clients]
            settings["clients"] = new_clients
            
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
            
            result = await api.update_inbound(config.TEMP_INBOUND_ID, update_data)
            if result:
                deleted_count = len(expired_clients)
                logger.info(f"✅ Successfully deleted {deleted_count} expired temp profiles")
            else:
                logger.error(f"🛑 Failed to delete expired temp profiles")
        else:
            logger.info("✅ No expired temp profiles found")
        
        return deleted_count
        
    except Exception as e:
        logger.exception(f"🛑 Error during temp profile cleanup: {e}")
        return 0
    finally:
        await api.close()
