from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetAdminLogRequest
from telethon.tl.types import InputChannel, ChannelAdminLogEventsFilter
import asyncio
from datetime import datetime, timedelta
import pytz

# Конфигурация
API_ID = ''
API_HASH = ''
CHAT_IDS = []  # ID чатов с префиксом -100
REPORT_CHAT_ID =   # Чат для отправки отчетов
ADMIN_ID = IDHere  # Ваш ID для тестовых команд

# Хэштеги для чатов
CHAT_HASHTAGS = {
    YOUR_CHAT_ID : '#ХЭШТЭГ',
    YOUR_CHAT_ID: '#ХЭШТЭГ',
    YOUR_CHAT_ID: '#ХЭШТЭГ'
}

# Часовые пояса
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
UFA_TZ = pytz.timezone('Asia/Yekaterinburg')

client = TelegramClient('userbot_session', API_ID, API_HASH)

class BanMonitor:
    def __init__(self):
        self.last_check_times = {}
        print("Инициализация BanMonitor завершена")

    async def check_bans(self):
        """Основной цикл проверки банов"""
        while True:
            try:
                for chat_id in CHAT_IDS:
                    await self.process_chat_bans(chat_id)
                await asyncio.sleep(60)
            except Exception as e:
                print(f"[ОШИБКА В check_bans]: {str(e)}", flush=True)
                await asyncio.sleep(300)

    async def process_chat_bans(self, chat_id):
        """Обработка банов в конкретном чате"""
        try:
            print(f"Проверяем баны в чате {chat_id}...")
            
            last_check = self.last_check_times.get(chat_id, datetime.now(pytz.utc) - timedelta(minutes=5))
            
            try:
                channel = await client.get_entity(chat_id)
                input_channel = InputChannel(channel.id, channel.access_hash)
            except Exception as e:
                print(f"[ОШИБКА ПОЛУЧЕНИЯ КАНАЛА {chat_id}]: {str(e)}", flush=True)
                return

            try:
                result = await client(GetAdminLogRequest(
                    channel=input_channel,
                    q='',
                    max_id=0,
                    min_id=0,
                    limit=100,
                    events_filter=ChannelAdminLogEventsFilter(
                        kick=True,
                        ban=True
                    )
                ))
            except Exception as e:
                print(f"[ОШИБКА ЗАПРОСА ЛОГОВ {chat_id}]: {str(e)}", flush=True)
                return

            new_events = [
                event for event in result.events 
                if event.date.replace(tzinfo=pytz.utc) > last_check.replace(tzinfo=pytz.utc)
            ]

            if not new_events:
                print(f"Новых банов в чате {chat_id} не обнаружено", flush=True)
                return

            last_event_time = None
            for event in new_events:
                event_time = event.date.replace(tzinfo=pytz.utc)
                
                banned_user_id = self._get_banned_user_id(event)
                if not banned_user_id:
                    continue

                try:
                    banned_user = await client.get_entity(banned_user_id)
                    admin_user = await client.get_entity(event.user_id)
                    
                    await self.send_ban_report(
                        chat_id=chat_id,
                        banned_user=banned_user,
                        admin_user=admin_user,
                        ban_time=event.date
                    )
                    print(f"Отправлен отчет о бане пользователя {banned_user_id} в чате {chat_id}", flush=True)

                except Exception as e:
                    print(f"[ОШИБКА ОБРАБОТКИ СОБЫТИЯ {chat_id}]: {str(e)}", flush=True)

                if not last_event_time or event_time > last_event_time:
                    last_event_time = event_time

            self.last_check_times[chat_id] = last_event_time if last_event_time else datetime.now(pytz.utc) - timedelta(seconds=1)
            
        except Exception as e:
            print(f"[КРИТИЧЕСКАЯ ОШИБКА В process_chat_bans {chat_id}]: {str(e)}", flush=True)

    def _get_banned_user_id(self, event):
        """Получаем ID забаненного пользователя из события"""
        try:
            if not hasattr(event.action, 'prev_participant'):
                return None
                
            prev_part = event.action.prev_participant
            if hasattr(prev_part, 'user_id'):
                return prev_part.user_id
            elif hasattr(prev_part, 'peer') and hasattr(prev_part.peer, 'user_id'):
                return prev_part.peer.user_id
                
            return None
        except Exception as e:
            print(f"[ОШИБКА В _get_banned_user_id]: {str(e)}", flush=True)
            return None

    async def send_ban_report(self, chat_id, banned_user, admin_user, ban_time):
        """Отправка отчета о бане с username и ID"""
        try:
            hashtag = CHAT_HASHTAGS.get(chat_id, '')
            
            ban_time = ban_time.replace(tzinfo=pytz.utc)
            moscow_time = ban_time.astimezone(MOSCOW_TZ)
            
            time_info = (
                f"⏰ Время:\n"
                f"Москва: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"UTC: {ban_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Формируем информацию о забаненном
            banned_name = banned_user.first_name or ""
            if banned_user.last_name:
                banned_name += f" {banned_user.last_name}"
            banned_username = f"@{banned_user.username}" if banned_user.username else "нет username"
            banned_id = f"ID: {banned_user.id}"

            # Формируем информацию об админе
            admin_name = admin_user.first_name or ""
            if admin_user.last_name:
                admin_name += f" {admin_user.last_name}"
            admin_username = f"@{admin_user.username}" if admin_user.username else "нет username"
            admin_id = f"ID: {admin_user.id}"

            report_text = (
                f"🛑 Обнаружен бан {hashtag}\n\n"
                f"👤 Забанен:\n"
                f"Имя: {banned_name.strip()}\n"
                f"Username: {banned_username}\n"
                f"{banned_id}\n\n"
                f"🛡 Администратор:\n"
                f"Имя: {admin_name.strip()}\n"
                f"Username: {admin_username}\n"
                f"{admin_id}\n\n"
                f"{time_info}"
            )

            await client.send_message(
                entity=REPORT_CHAT_ID,
                message=report_text
            )
            
        except Exception as e:
            print(f"[ОШИБКА ОТПРАВКИ ОТЧЕТА]: {str(e)}", flush=True)
            raise

async def main():
    try:
        await client.start()
        print("Бот успешно запущен", flush=True)
        
        ban_monitor = BanMonitor()
        asyncio.create_task(ban_monitor.check_bans())
        
        @client.on(events.NewMessage(pattern='/test_ban', from_users=ADMIN_ID))
        async def test_ban_report(event):
            try:
                test_time = datetime.now(pytz.utc)
                await ban_monitor.send_ban_report(
                    chat_id=CHAT_IDS[0],
                    banned_user=type('', (), {
                        'first_name': 'TestUser',
                        'last_name': 'Testovich',
                        'username': 'test_user',
                        'id': 123456789
                    }),
                    admin_user=type('', (), {
                        'first_name': 'TestAdmin',
                        'last_name': 'Adminov',
                        'username': 'test_admin',
                        'id': 987654321
                    }),
                    ban_time=test_time
                )
                await event.reply("✅ Тестовый отчет отправлен")
                print("Тестовый отчет успешно отправлен", flush=True)
            except Exception as e:
                await event.reply(f"❌ Ошибка: {str(e)}")
                print(f"[ОШИБКА ТЕСТОВОГО ОТЧЕТА]: {str(e)}", flush=True)
        
        print("Ожидание событий...", flush=True)
        await client.run_until_disconnected()
    except Exception as e:
        print(f"[ГЛАВНАЯ ОШИБКА]: {str(e)}", flush=True)
    finally:
        await client.disconnect()
        print("Бот остановлен", flush=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА]: {str(e)}", flush=True)