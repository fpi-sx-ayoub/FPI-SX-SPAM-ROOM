import requests, os, sys, jwt, json, binascii, time, urllib3, xKEys, base64, datetime, re, socket, threading
import psutil
from protobuf_decoder.protobuf_decoder import Parser
from byte import *
from byte import xSendTeamMsg, xSEndMsg
from byte import Auth_Chat
from xHeaders import *
from datetime import datetime
from google.protobuf.timestamp_pb2 import Timestamp
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from threading import Thread
from black9 import openroom, spmroom
import telebot
from telebot import types
import logging
import queue
from collections import defaultdict
import multiprocessing
import ctypes
import gc

# تعطيل تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  

TOKEN = "8443614481:AAFY9v8pMpu1IdclVQg6wa-zMzxEqq5a5pc"
ADMIN_IDS = [7375963526]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# تخزين الحسابات المتصلة
connected_clients = {}
connected_clients_lock = threading.Lock()
account_pools = {}  # تجمعات الحسابات

# إدارة السبام النشط
active_spam_targets = {}
active_room_spam_targets = {}
active_spam_lock = threading.Lock()
spam_workers_active = {}
spam_stats = defaultdict(lambda: {'sent': 0, 'errors': 0, 'last_reset': datetime.now()})

spam_initiators = {}
spam_initiators_lock = threading.Lock()
spam_start_times = {}
spam_start_times_lock = threading.Lock()

# إعدادات TURBO SPEED القصوى 🚀 مع 200 حساب
MAX_WORKERS = 1000  # 1000 عامل متوازي
BURST_SIZE = 500    # 500 رسالة في الدفعة
TURBO_WORKERS_PER_TARGET = 5  # 5 عمال توربو لكل هدف
SPAM_DURATION_MINUTES = 5  # مدة السبام 5 دقائق ثابتة
SPAM_DURATION_SECONDS = SPAM_DURATION_MINUTES * 60  # 300 ثانية
BATCH_SIZE = 50     # 50 حساب في كل دفعة
CONNECTIONS_PER_ACCOUNT = 3  # 3 اتصالات لكل حساب

# الرابط الخاص بجلب معلومات اللاعب
PLAYER_INFO_API = "https://fpi-sx-team.vercel.app/player_info"
API_UID = "4614605884"
API_PASSWORD = "B2D0254C2D73888A90D91A62D4FF151F3CDFCDA8315B21428DA34A2187BEDAE0"
API_SERVER = "ME"

# Queues للمهام - سعة غير محدودة
spam_queue = queue.Queue(maxsize=0)
room_spam_queue = queue.Queue(maxsize=0)
command_queue = queue.Queue(maxsize=0)

# إحصائيات الأداء
performance_stats = {
    'total_messages_sent': 0,
    'messages_per_second': 0,
    'active_connections': 0,
    'start_time': datetime.now()
}
stats_lock = threading.Lock()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_player_info(target_id):
    """
    جلب معلومات اللاعب من الرابط المحدد
    يتم وضع الأيدي المستهدف في مكان friend_uid
    """
    try:
        # تجهيز الباراميترات
        params = {
            "uid": API_UID,
            "password": API_PASSWORD,
            "friend_uid": target_id,  # هنا يتم وضع الأيدي المستهدف
            "server_name": API_SERVER
        }
        
        print(f"🔍 جلب معلومات اللاعب {target_id}...")
        
        # إرسال الطلب
        response = requests.get(
            PLAYER_INFO_API, 
            params=params, 
            timeout=10, 
            verify=False
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ تم جلب بيانات اللاعب {target_id}")
            
            # استخراج المعلومات من الاستجابة
            # ملاحظة: أسماء الحقول قد تختلف حسب استجابة الـ API الفعلية
            player_name = data.get('name') or data.get('username') or data.get('nickname') or 'غير معروف'
            player_level = data.get('level') or data.get('lvl') or '?'
            player_likes = data.get('likes') or data.get('total_likes') or '0'
            player_region = data.get('region') or data.get('server') or API_SERVER
            
            return player_name, player_level, player_likes, player_region
        else:
            print(f"⚠️ فشل جلب البيانات. Status code: {response.status_code}")
            return None, None, None, None
            
    except requests.exceptions.Timeout:
        print(f"⏰Timeout في جلب بيانات اللاعب {target_id}")
        return None, None, None, None
    except requests.exceptions.ConnectionError:
        print(f"🔌خطأ في الاتصال لجلب بيانات اللاعب {target_id}")
        return None, None, None, None
    except json.JSONDecodeError:
        print(f"📄خطأ في قراءة JSON لبيانات اللاعب {target_id}")
        return None, None, None, None
    except Exception as e:
        print(f"❌ خطأ غير متوقع في جلب بيانات اللاعب {target_id}: {e}")
        return None, None, None, None

class TurboAccountPool:
    """تجمع حسابات توربو - يدير اتصالات متعددة لكل حساب"""
    
    def __init__(self, accounts, pool_size=CONNECTIONS_PER_ACCOUNT):
        self.accounts = accounts
        self.pool_size = pool_size
        self.connections = []
        self.pool_lock = threading.Lock()
        self.current_index = 0
        self.setup_connections()
    
    def setup_connections(self):
        """إنشاء اتصالات متعددة لكل حساب"""
        print(f"🔧 إنشاء تجمع اتصالات لـ {len(self.accounts)} حساب...")
        for account in self.accounts:
            account_connections = []
            for i in range(self.pool_size):
                try:
                    client = FF_CLient(account['id'], account['password'])
                    if client.key and client.iv:
                        account_connections.append(client)
                        time.sleep(0.1)  # تأخير بسيط بين الاتصالات
                except Exception as e:
                    print(f"⚠️ خطأ في إنشاء اتصال للحساب {account['id']}: {e}")
            if account_connections:
                self.connections.extend(account_connections)
                print(f"✅ تم إنشاء {len(account_connections)} اتصال للحساب {account['id']}")
        
        print(f"🔥 Turbo Pool created with {len(self.connections)} connections for {len(self.accounts)} accounts")
    
    def get_connection(self):
        """الحصول على اتصال من التجمع (round-robin)"""
        with self.pool_lock:
            if not self.connections:
                return None
            conn = self.connections[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.connections)
            return conn
    
    def get_all_connections(self):
        """الحصول على جميع الاتصالات"""
        return self.connections

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS
    chat_type = message.chat.type
    
    if chat_type != 'private':
        msg = (
            "<b>🎮 SPAM BOT - 200 ACCOUNTS</b>\n\n"
            "<b>📝 Commands:</b>\n"
            "• <code>/spam {id}</code> - Start spam (5 minutes)\n"
            "• <code>/room {id}</code> - Start room spam (5 minutes)\n"
            "• <code>/status {id}</code> - Check spam status\n"
            "• <code>/stop_spam {id}</code> - Stop normal spam\n"
            "• <code>/stop_room {id}</code> - Stop room spam\n"
            "• <code>/stats</code> - Show performance stats\n\n"
            "<b>⏰ Duration:</b> 5 minutes fixed\n"
            "<b>🔥 Mode:</b> TesT V1.5\n"
            "<b>👤 Player Info:</b> on spam start\n\n"
            "<b>📞 Support:</b> @noseyrobot"
        )
    else:
        if is_admin:
            msg = (
                "<b>👑 Admin Panel - 200 Accounts</b>\n\n"
                "<b>🔥 MODE ACTIVE:</b>\n"
                "• MOD TEST V1.5\n"
                "• 500 messages per burst\n"
                "• 5 WORKERS per target\n"
                "• 3 connections per account\n"
                "• Auto player info fetch\n"
                "• Fixed duration: 5 minutes\n\n"
                "<b>📝 Commands:</b>\n"
                "• <code>/spam {id}</code> - Start spam (5 minutes)\n"
                "• <code>/room {id}</code> - Start room spam (5 minutes)\n"
                "• <code>/status {id}</code> - Check spam status\n"
                "• <code>/stop_spam {id}</code> - Stop normal spam\n"
                "• <code>/stop_room {id}</code> - Stop room spam\n"
                "• <code>/stats</code> - Show performance stats\n"
                "• <code>/restart</code> - Restart accounts\n\n"
                "<b>📞 Support:</b> @noseyrobot"
            )
        else:
            msg = "🗿"
    
    bot.reply_to(message, msg)

@bot.message_handler(commands=['stats'])
def stats_command(message):
    """عرض إحصائيات الأداء"""
    with stats_lock:
        uptime = datetime.now() - performance_stats['start_time']
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        # حساب معدل الرسائل في الثانية
        elapsed_seconds = uptime.seconds
        if elapsed_seconds > 0:
            mps = performance_stats['total_messages_sent'] / elapsed_seconds
        else:
            mps = 0
        
        stats_msg = (
            "<b>📊 Performance Stats</b>\n\n"
            f"<b>⏱️ Uptime:</b> {hours}h {minutes}m\n"
            f"<b>👥 Active Accounts:</b> {len(connected_clients)}\n"
            f"<b>🔌 Total Connections:</b> {len(connected_clients) * CONNECTIONS_PER_ACCOUNT}\n"
            f"<b>📨 Messages Sent:</b> {performance_stats['total_messages_sent']:,}\n"
            f"<b>⚡ Msg/Sec:</b> {mps:.1f}\n"
            f"<b>🎯 Active Targets:</b> {len(active_spam_targets) + len(active_room_spam_targets)}\n"
            f"<b>📦 Queue Size:</b> {spam_queue.qsize() + room_spam_queue.qsize()}\n"
        )
        
        # إضافة إحصائيات لكل هدف نشط
        if active_spam_targets or active_room_spam_targets:
            stats_msg += "\n<b>🔥 Active Targets:</b>\n"
            
            with active_spam_lock:
                for target_id in active_spam_targets:
                    stats_msg += f"• <code>{target_id}</code>: {spam_stats[target_id]['sent']:,} msgs\n"
                
                for target_id in active_room_spam_targets:
                    room_key = f"room_{target_id}"
                    stats_msg += f"• <code>{target_id}</code> (Room): {spam_stats[room_key]['sent']:,} msgs\n"
        
        bot.reply_to(message, stats_msg)

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.from_user.id not in ADMIN_IDS and not message.text.startswith('/'))
def handle_private(message):
    bot.reply_to(message, "🗿")

@bot.message_handler(commands=['spam'])
def spam_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    try:
        if len(args) != 2:
            bot.reply_to(message, "<b>❌ Wrong Format</b>\nUse: <code>/spam {id}</code>\nDuration: 5 minutes fixed")
            return
        
        target_id = args[1]
        duration_minutes = SPAM_DURATION_MINUTES  # 5 دقائق ثابتة
        
        # التحقق من صحة الآيدي
        if not ChEck_Commande(target_id):
            bot.reply_to(message, "<b>❌ Error</b>\nInvalid user_id")
            return
        
        # إرسال رسالة "جاري الجلب..."
        fetching_msg = bot.reply_to(message, "<b>🔍 Fetching player info...</b>")
        
        # جلب معلومات اللاعب
        player_name, player_level, player_likes, player_region = get_player_info(target_id)
        
        # إذا فشل الجلب، استخدم قيماً افتراضية
        if player_name is None:
            player_name = "غير معروف"
            player_level = "?"
            player_likes = "?"
            player_region = "ME"
        
        with active_spam_lock:
            if target_id in active_spam_targets:
                bot.reply_to(message, f"<b>⚠️ Already spamming ID {target_id}</b>")
                return
            
            active_spam_targets[target_id] = {
                'active': True,
                'start_time': datetime.now(),
                'duration': duration_minutes,
                'type': 'normal',
                'initiator': user_id,
                'player_info': {
                    'name': player_name,
                    'level': player_level,
                    'likes': player_likes,
                    'region': player_region
                }
            }
            
            for i in range(TURBO_WORKERS_PER_TARGET):
                worker_id = f"{target_id}_worker_{i}"
                spam_workers_active[worker_id] = True
                threading.Thread(target=turbo_normal_spam_worker, args=(target_id, duration_minutes, worker_id), daemon=True).start()
            
            with spam_start_times_lock:
                spam_start_times[target_id] = datetime.now()
            
            with spam_initiators_lock:
                spam_initiators[target_id] = user_id
            
            # حذف رسالة "جاري الجلب"
            bot.delete_message(fetching_msg.chat.id, fetching_msg.message_id)
            
            # إرسال رسالة التأكيد مع معلومات اللاعب
            bot.reply_to(
                message, 
                f"<b>✅ TURBO MODE ACTIVATED</b>\n\n"
                f"<b>🎮 Player Information:</b>\n"
                f"• <b>ID:</b> <code>{target_id}</code>\n"
                f"• <b>Name:</b> {player_name}\n"
                f"• <b>Level:</b> {player_level}\n"
                f"• <b>Likes:</b> {player_likes}\n"
                f"• <b>Region:</b> {player_region}\n\n"
                f"<b>⏱️ Duration:</b> {duration_minutes} minutes\n"
                f"<b>🔥 Turbo Workers:</b> {TURBO_WORKERS_PER_TARGET}\n"
                f"<b>⚡ Status:</b> <b>SPAMMING</b>"
            )
            
    except ValueError:
        bot.reply_to(message, "<b>❌ Error</b>\nPlease enter a valid ID")
    except Exception as e:
        bot.reply_to(message, f"<b>❌ Error:</b> {str(e)}")

@bot.message_handler(commands=['room'])
def room_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    try:
        if len(args) != 2:
            bot.reply_to(message, "<b>❌ Wrong Format</b>\nUse: <code>/room {id}</code>\nDuration: 5 minutes fixed")
            return
        
        target_id = args[1]
        duration_minutes = SPAM_DURATION_MINUTES  # 5 دقائق ثابتة
        
        # التحقق من صحة الآيدي
        if not ChEck_Commande(target_id):
            bot.reply_to(message, "<b>❌ Error</b>\nInvalid user_id")
            return
        
        # إرسال رسالة "جاري الجلب..."
        fetching_msg = bot.reply_to(message, "<b>🔍 Fetching player info...</b>")
        
        # جلب معلومات اللاعب
        player_name, player_level, player_likes, player_region = get_player_info(target_id)
        
        # إذا فشل الجلب، استخدم قيماً افتراضية
        if player_name is None:
            player_name = "غير معروف"
            player_level = "?"
            player_likes = "?"
            player_region = "ME"
        
        with active_spam_lock:
            if target_id in active_room_spam_targets:
                bot.reply_to(message, f"<b>⚠️ Already room spamming ID {target_id}</b>")
                return
            
            active_room_spam_targets[target_id] = {
                'active': True,
                'start_time': datetime.now(),
                'duration': duration_minutes,
                'type': 'room',
                'initiator': user_id,
                'player_info': {
                    'name': player_name,
                    'level': player_level,
                    'likes': player_likes,
                    'region': player_region
                }
            }
            
            for i in range(TURBO_WORKERS_PER_TARGET):
                worker_id = f"room_{target_id}_worker_{i}"
                spam_workers_active[worker_id] = True
                threading.Thread(target=turbo_room_spam_worker, args=(target_id, duration_minutes, worker_id), daemon=True).start()
            
            with spam_start_times_lock:
                spam_start_times[f"room_{target_id}"] = datetime.now()
            
            with spam_initiators_lock:
                spam_initiators[f"room_{target_id}"] = user_id
            
            # حذف رسالة "جاري الجلب"
            bot.delete_message(fetching_msg.chat.id, fetching_msg.message_id)
            
            # إرسال رسالة التأكيد مع معلومات اللاعب
            bot.reply_to(
                message, 
                f"<b>✅ ROOM TURBO MODE ACTIVATED</b>\n\n"
                f"<b>🎮 Player Information:</b>\n"
                f"• <b>ID:</b> <code>{target_id}</code>\n"
                f"• <b>Name:</b> {player_name}\n"
                f"• <b>Level:</b> {player_level}\n"
                f"• <b>Likes:</b> {player_likes}\n"
                f"• <b>Region:</b> {player_region}\n\n"
                f"<b>⏱️ Duration:</b> {duration_minutes} minutes\n"
                f"<b>🔥 Turbo Workers:</b> {TURBO_WORKERS_PER_TARGET}\n"
                f"<b>⚡ Status:</b> <b>ROOM SPAMMING</b>"
            )
            
    except ValueError:
        bot.reply_to(message, "<b>❌ Error</b>\nPlease enter a valid ID")
    except Exception as e:
        bot.reply_to(message, f"<b>❌ Error:</b> {str(e)}")

@bot.message_handler(commands=['status'])
def status_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    try:
        if len(args) != 2:
            bot.reply_to(message, "<b>❌ Wrong Format</b>\nUse: <code>/status {id}</code>")
            return
        
        target_id = args[1]
        found = False
        
        # فحص السبام العادي
        with active_spam_lock:
            if target_id in active_spam_targets:
                with spam_start_times_lock:
                    if target_id in spam_start_times:
                        start_time = spam_start_times[target_id]
                        elapsed = datetime.now() - start_time
                        total_seconds = int(elapsed.total_seconds())
                        duration_seconds = SPAM_DURATION_SECONDS
                        remaining = duration_seconds - total_seconds
                        
                        if remaining > 0:
                            minutes = remaining // 60
                            seconds = remaining % 60
                            
                            # استرجاع معلومات اللاعب
                            player_info = active_spam_targets[target_id].get('player_info', {})
                            player_name = player_info.get('name', 'غير معروف')
                            player_level = player_info.get('level', '?')
                            player_likes = player_info.get('likes', '?')
                            player_region = player_info.get('region', 'ME')
                            
                            # حساب معدل الإرسال
                            sent_count = spam_stats[target_id]['sent']
                            if total_seconds > 0:
                                rate = sent_count / total_seconds
                            else:
                                rate = 0
                            
                            bot.reply_to(
                                message,
                                f"<b>📊 NORMAL SPAM STATUS</b>\n\n"
                                f"<b>🎮 Player:</b> {player_name}\n"
                                f"<b>🆔 ID:</b> <code>{target_id}</code>\n"
                                f"<b>📊 Level:</b> {player_level} | <b>❤️ Likes:</b> {player_likes}\n"
                                f"<b>🌍 Region:</b> {player_region}\n\n"
                                f"<b>📨 Messages Sent:</b> {sent_count:,}\n"
                                f"<b>⚡ Rate:</b> {rate:.1f} msg/sec\n"
                                f"<b>⏱️ Time Left:</b> {minutes}m {seconds}s\n"
                                f"<b>🔥 Turbo Workers:</b> {TURBO_WORKERS_PER_TARGET}\n"
                                f"<b>⚡ Status:</b> 🔥 <b>ACTIVE</b>"
                            )
                            found = True
                        else:
                            # انتهت المدة، إيقاف تلقائي
                            bot.reply_to(message, f"<b>⏰ Spam for ID <code>{target_id}</code> has completed (5 minutes)</b>")
                            # إيقاف السبام
                            for i in range(TURBO_WORKERS_PER_TARGET):
                                worker_id = f"{target_id}_worker_{i}"
                                spam_workers_active[worker_id] = False
                            if target_id in active_spam_targets:
                                del active_spam_targets[target_id]
                            found = True
        
        # فحص سبام الروم
        if not found:
            with active_spam_lock:
                if target_id in active_room_spam_targets:
                    with spam_start_times_lock:
                        room_key = f"room_{target_id}"
                        if room_key in spam_start_times:
                            start_time = spam_start_times[room_key]
                            elapsed = datetime.now() - start_time
                            total_seconds = int(elapsed.total_seconds())
                            duration_seconds = SPAM_DURATION_SECONDS
                            remaining = duration_seconds - total_seconds
                            
                            if remaining > 0:
                                minutes = remaining // 60
                                seconds = remaining % 60
                                
                                # استرجاع معلومات اللاعب
                                player_info = active_room_spam_targets[target_id].get('player_info', {})
                                player_name = player_info.get('name', 'غير معروف')
                                player_level = player_info.get('level', '?')
                                player_likes = player_info.get('likes', '?')
                                player_region = player_info.get('region', 'ME')
                                
                                # حساب معدل الإرسال
                                sent_count = spam_stats[room_key]['sent']
                                if total_seconds > 0:
                                    rate = sent_count / total_seconds
                                else:
                                    rate = 0
                                
                                bot.reply_to(
                                    message,
                                    f"<b>📊 ROOM SPAM STATUS</b>\n\n"
                                    f"<b>🎮 Player:</b> {player_name}\n"
                                    f"<b>🆔 ID:</b> <code>{target_id}</code>\n"
                                    f"<b>📊 Level:</b> {player_level} | <b>❤️ Likes:</b> {player_likes}\n"
                                    f"<b>🌍 Region:</b> {player_region}\n\n"
                                    f"<b>📨 Messages Sent:</b> {sent_count:,}\n"
                                    f"<b>⚡ Rate:</b> {rate:.1f} msg/sec\n"
                                    f"<b>⏱️ Time Left:</b> {minutes}m {seconds}s\n"
                                    f"<b>🔥 Turbo Workers:</b> {TURBO_WORKERS_PER_TARGET}\n"
                                    f"<b>⚡ Status:</b> 🔥 <b>ROOM ACTIVE</b>"
                                )
                                found = True
                            else:
                                # انتهت المدة، إيقاف تلقائي
                                bot.reply_to(message, f"<b>⏰ Room spam for ID <code>{target_id}</code> has completed (5 minutes)</b>")
                                # إيقاف السبام
                                for i in range(TURBO_WORKERS_PER_TARGET):
                                    worker_id = f"room_{target_id}_worker_{i}"
                                    spam_workers_active[worker_id] = False
                                if target_id in active_room_spam_targets:
                                    del active_room_spam_targets[target_id]
                                found = True
        
        if not found:
            bot.reply_to(message, f"<b>❌ No active spam found for ID <code>{target_id}</code></b>")
            
    except Exception as e:
        bot.reply_to(message, f"<b>❌ Error:</b> {str(e)}")

@bot.message_handler(commands=['stop_spam'])
def stop_spam_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    try:
        if len(args) != 2:
            bot.reply_to(message, "<b>❌ Wrong Format</b>\nUse: <code>/stop_spam {id}</code>")
            return
        
        target_id = args[1]
        
        with active_spam_lock:
            if target_id not in active_spam_targets:
                bot.reply_to(message, f"<b>❌ No active spam for ID {target_id}</b>")
                return
            
            with spam_initiators_lock:
                initiator = spam_initiators.get(target_id)
                if initiator != user_id and user_id not in ADMIN_IDS:
                    bot.reply_to(message, "<b>⛔ You cannot stop this spam</b>")
                    return
            
            # إيقاف جميع عمال التوربو
            for i in range(TURBO_WORKERS_PER_TARGET):
                worker_id = f"{target_id}_worker_{i}"
                spam_workers_active[worker_id] = False
            
            # استرجاع معلومات اللاعب للإحصائيات النهائية
            player_info = active_spam_targets[target_id].get('player_info', {})
            player_name = player_info.get('name', 'غير معروف')
            
            # حساب إجمالي الوقت
            start_time = spam_start_times.get(target_id, datetime.now())
            total_duration = datetime.now() - start_time
            total_minutes = total_duration.seconds // 60
            total_seconds = total_duration.seconds % 60
            
            sent_count = spam_stats[target_id]['sent']
            
            del active_spam_targets[target_id]
            
            bot.reply_to(
                message, 
                f"<b>✅ SPAM STOPPED</b>\n\n"
                f"<b>🎮 Player:</b> {player_name}\n"
                f"<b>🆔 ID:</b> <code>{target_id}</code>\n"
                f"<b>📨 Total Messages:</b> {sent_count:,}\n"
                f"<b>⏱️ Duration:</b> {total_minutes}m {total_seconds}s\n"
                f"<b>⚡ Avg Rate:</b> {sent_count // max(1, total_duration.seconds)} msg/sec"
            )
            
    except Exception as e:
        bot.reply_to(message, f"<b>❌ Error:</b> {str(e)}")

@bot.message_handler(commands=['stop_room'])
def stop_room_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    try:
        if len(args) != 2:
            bot.reply_to(message, "<b>❌ Wrong Format</b>\nUse: <code>/stop_room {id}</code>")
            return
        
        target_id = args[1]
        room_key = f"room_{target_id}"
        
        with active_spam_lock:
            if target_id not in active_room_spam_targets:
                bot.reply_to(message, f"<b>❌ No active room spam for ID {target_id}</b>")
                return
            
            with spam_initiators_lock:
                initiator = spam_initiators.get(room_key)
                if initiator != user_id and user_id not in ADMIN_IDS:
                    bot.reply_to(message, "<b>⛔ You cannot stop this spam</b>")
                    return
            
            # إيقاف جميع عمال التوربو
            for i in range(TURBO_WORKERS_PER_TARGET):
                worker_id = f"room_{target_id}_worker_{i}"
                spam_workers_active[worker_id] = False
            
            # استرجاع معلومات اللاعب للإحصائيات النهائية
            player_info = active_room_spam_targets[target_id].get('player_info', {})
            player_name = player_info.get('name', 'غير معروف')
            
            # حساب إجمالي الوقت
            start_time = spam_start_times.get(room_key, datetime.now())
            total_duration = datetime.now() - start_time
            total_minutes = total_duration.seconds // 60
            total_seconds = total_duration.seconds % 60
            
            sent_count = spam_stats[room_key]['sent']
            
            del active_room_spam_targets[target_id]
            
            bot.reply_to(
                message, 
                f"<b>✅ ROOM SPAM STOPPED</b>\n\n"
                f"<b>🎮 Player:</b> {player_name}\n"
                f"<b>🆔 ID:</b> <code>{target_id}</code>\n"
                f"<b>📨 Total Messages:</b> {sent_count:,}\n"
                f"<b>⏱️ Duration:</b> {total_minutes}m {total_seconds}s\n"
                f"<b>⚡ Avg Rate:</b> {sent_count // max(1, total_duration.seconds)} msg/sec"
            )
            
    except Exception as e:
        bot.reply_to(message, f"<b>❌ Error:</b> {str(e)}")

@bot.message_handler(commands=['restart'])
def restart_command(message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "<b>❌ Admin only</b>")
        return
    
    bot.reply_to(message, "<b>🔄 Restarting all accounts...</b>")
    threading.Thread(target=restart_accounts, daemon=True).start()

def restart_accounts():
    time.sleep(2)
    ResTarT_BoT()

def AuTo_ResTartinG():
    """إعادة تشغيل تلقائي كل 4 ساعات"""
    while True:
        time.sleep(4 * 60 * 60)  # 4 ساعات
        print("🔄 Auto restarting bot...")
        ResTarT_BoT()

def ResTarT_BoT():
    """إعادة تشغيل البوت"""
    print('🔄 Restarting bot...')
    p = psutil.Process(os.getpid())
    
    # إغلاق جميع الاتصالات
    for handler in p.open_files():
        try:
            os.close(handler.fd)
        except:
            pass
    
    for conn in p.net_connections():
        try:
            conn.close()
        except:
            pass
    
    # إعادة التشغيل
    python = sys.executable
    os.execl(python, python, *sys.argv)

def GeT_Time(timestamp):
    last_login = datetime.fromtimestamp(timestamp)
    now = datetime.now()
    diff = now - last_login   
    d = diff.days
    h, rem = divmod(diff.seconds, 3600)
    m, s = divmod(rem, 60)    
    return d, h, m, s

def Time_En_Ar(t): 
    return ' '.join(t.replace("Day","Day").replace("Hour","Hour").replace("Min","Min").replace("Sec","Sec").split(" - "))

# تشغيل الإعادة التلقائية
Thread(target=AuTo_ResTartinG, daemon=True).start()

# تحميل الحسابات
ACCOUNTS = []

def load_accounts_from_file(filename="accs.json"):
    accounts = []
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
            
            if isinstance(data, list):
                for account in data:
                    if isinstance(account, dict):
                        account_id = account.get('uid', '')
                        password = account.get('password', '')
                        
                        if account_id:
                            accounts.append({
                                'id': str(account_id),
                                'password': password
                            })
            
            print(f"✅ Loaded {len(accounts)} accounts from {filename}")
            
    except FileNotFoundError:
        print(f"❌ File {filename} not found!")
    except json.JSONDecodeError:
        print(f"❌ JSON format error in {filename}!")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
    
    return accounts

ACCOUNTS = load_accounts_from_file()

def get_active_connections():
    """الحصول على قائمة الاتصالات النشطة"""
    with connected_clients_lock:
        active = []
        for account_id, client in connected_clients.items():
            if (hasattr(client, 'CliEnts2') and client.CliEnts2 and 
                hasattr(client, 'key') and client.key and 
                hasattr(client, 'iv') and client.iv):
                active.append(client)
        return active

def turbo_normal_spam_worker(target_id, duration_minutes, worker_id):
    """عامل توربو للسبام العادي - مدة ثابتة 5 دقائق"""
    print(f"🔥 Turbo worker {worker_id} started for target {target_id} (Duration: {duration_minutes} minutes)")
    
    start_time = datetime.now()
    duration_seconds = duration_minutes * 60
    local_stats = spam_stats[target_id]
    
    while True:
        # التحقق من استمرار السبام
        with active_spam_lock:
            if target_id not in active_spam_targets:
                print(f"Worker {worker_id} stopping - target {target_id} removed")
                break
            if not spam_workers_active.get(worker_id, True):
                print(f"Worker {worker_id} stopping - deactivated")
                break
            
            # التحقق من انتهاء المدة (5 دقائق)
            elapsed = datetime.now() - start_time
            if elapsed.total_seconds() >= duration_seconds:
                print(f"Worker {worker_id} - 5 minutes completed for {target_id}, stopping...")
                # إيقاف العامل وإزالة الهدف
                spam_workers_active[worker_id] = False
                with active_spam_lock:
                    if target_id in active_spam_targets:
                        del active_spam_targets[target_id]
                break
        
        try:
            # إرسال سبام بسرعة قصوى
            connections = get_active_connections()
            if not connections:
                time.sleep(0.05)
                continue
            
            # إرسال دفعات ضخمة
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                # استخدام جميع الاتصالات المتاحة
                for conn in connections:
                    for _ in range(BURST_SIZE // len(connections) + 1):
                        future = executor.submit(send_turbo_normal_burst, conn, target_id, worker_id)
                        futures.append(future)
                
                # تحديث الإحصائيات
                with stats_lock:
                    performance_stats['total_messages_sent'] += len(futures) * 3
                    local_stats['sent'] += len(futures) * 3
                    
                    # حساب الرسائل في الثانية
                    elapsed = (datetime.now() - performance_stats['start_time']).seconds
                    if elapsed > 0:
                        performance_stats['messages_per_second'] = performance_stats['total_messages_sent'] // elapsed
                
        except Exception as e:
            local_stats['errors'] += 1
            time.sleep(0.01)  # تأخير بسيط جداً عند الخطأ

def turbo_room_spam_worker(target_id, duration_minutes, worker_id):
    """عامل توربو لسبام الروم - مدة ثابتة 5 دقائق"""
    print(f"🔥 Room turbo worker {worker_id} started for target {target_id} (Duration: {duration_minutes} minutes)")
    
    start_time = datetime.now()
    duration_seconds = duration_minutes * 60
    room_key = f"room_{target_id}"
    local_stats = spam_stats[room_key]
    
    while True:
        with active_spam_lock:
            if target_id not in active_room_spam_targets:
                print(f"Room worker {worker_id} stopping - target {target_id} removed")
                break
            if not spam_workers_active.get(worker_id, True):
                print(f"Room worker {worker_id} stopping - deactivated")
                break
            
            # التحقق من انتهاء المدة (5 دقائق)
            elapsed = datetime.now() - start_time
            if elapsed.total_seconds() >= duration_seconds:
                print(f"Room worker {worker_id} - 5 minutes completed for {target_id}, stopping...")
                # إيقاف العامل وإزالة الهدف
                spam_workers_active[worker_id] = False
                with active_spam_lock:
                    if target_id in active_room_spam_targets:
                        del active_room_spam_targets[target_id]
                break
        
        try:
            connections = get_active_connections()
            if not connections:
                time.sleep(0.05)
                continue
            
            # فتح الروم أولاً لجميع الاتصالات
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                open_futures = []
                for conn in connections:
                    future = executor.submit(open_room_for_connection, conn, target_id)
                    open_futures.append(future)
                
                # انتظار فتح الروم (بسرعة)
                for future in as_completed(open_futures, timeout=2):
                    pass
                
                # إرسال سبام الروم
                spam_futures = []
                for conn in connections:
                    for _ in range(BURST_SIZE // len(connections) + 1):
                        future = executor.submit(send_turbo_room_burst, conn, target_id, worker_id)
                        spam_futures.append(future)
                
                # تحديث الإحصائيات
                with stats_lock:
                    performance_stats['total_messages_sent'] += len(spam_futures)
                    local_stats['sent'] += len(spam_futures)
                    
                    elapsed = (datetime.now() - performance_stats['start_time']).seconds
                    if elapsed > 0:
                        performance_stats['messages_per_second'] = performance_stats['total_messages_sent'] // elapsed
                
        except Exception as e:
            local_stats['errors'] += 1
            time.sleep(0.01)

def send_turbo_normal_burst(client, target_id, worker_id):
    """إرسال دفعة سبام عادي - 3 رسائل في المرة"""
    try:
        if hasattr(client, 'CliEnts2') and client.CliEnts2:
            # إرسال 3 رسائل دفعة واحدة بسرعة قصوى
            client.CliEnts2.send(SEnd_InV(1, target_id, client.key, client.iv))
            client.CliEnts2.send(OpEnSq(client.key, client.iv))
            client.CliEnts2.send(SPamSq(target_id, client.key, client.iv))
            return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        # تجاهل أخطاء الاتصال
        pass
    except Exception:
        pass
    return False

def open_room_for_connection(client, target_id):
    """فتح روم لحساب واحد"""
    try:
        if hasattr(client, 'CliEnts2') and client.CliEnts2:
            client.CliEnts2.send(openroom(client.key, client.iv))
            return True
    except:
        pass
    return False

def send_turbo_room_burst(client, target_id, worker_id):
    """إرسال دفعة سبام روم"""
    try:
        if hasattr(client, 'CliEnts2') and client.CliEnts2:
            client.CliEnts2.send(spmroom(client.key, client.iv, target_id))
            return True
    except:
        pass
    return False

class FF_CLient():

    def __init__(self, id, password):
        self.id = id
        self.password = password
        self.key = None
        self.iv = None
        self.connection_active = True
        self.max_retries = 5
        self.retry_delay = 10
        self.Get_FiNal_ToKen_0115()     
            
    def Connect_SerVer_OnLine(self , Token , tok , host , port , key , iv , host2 , port2):
        try:
            self.AutH_ToKen_0115 = tok    
            self.CliEnts2 = socket.create_connection((host2 , int(port2)))
            self.CliEnts2.send(bytes.fromhex(self.AutH_ToKen_0115))                  
        except Exception as e:
            print(f"Error in Connect_SerVer_OnLine: {e}")
            return
        
        while self.connection_active:
            try:
                self.DaTa2 = self.CliEnts2.recv(99999)
                if '0500' in self.DaTa2.hex()[0:4] and len(self.DaTa2.hex()) > 30:	         	    	    
                    self.packet = json.loads(DeCode_PackEt(f'08{self.DaTa2.hex().split("08", 1)[1]}'))
                    self.AutH = self.packet['5']['data']['7']['data']
            except Exception as e:
                print(f"Error in Connect_SerVer_OnLine receive: {e}")
                time.sleep(1)
                                                            
    def Connect_SerVer(self , Token , tok , host , port , key , iv , host2 , port2):
        try:
            self.AutH_ToKen_0115 = tok    
            self.CliEnts = socket.create_connection((host , int(port)))
            self.CliEnts.send(bytes.fromhex(self.AutH_ToKen_0115))  
            self.DaTa = self.CliEnts.recv(1024)          	        
            threading.Thread(target=self.Connect_SerVer_OnLine, args=(Token , tok , host , port , key , iv , host2 , port2)).start()
            self.Exemple = xMsGFixinG('12345678')
            
            self.key = key
            self.iv = iv
            
            with connected_clients_lock:
                connected_clients[self.id] = self
                print(f"Account {self.id} registered, total accounts: {len(connected_clients)}")
            
            while True:      
                try:
                    self.DaTa = self.CliEnts.recv(1024)   
                    if len(self.DaTa) == 0 or (hasattr(self, 'DaTa2') and len(self.DaTa2) == 0):	            		
                        print(f"Connection lost for account {self.id}, reconnecting...")
                        try:            		    
                            self.CliEnts.close()
                            if hasattr(self, 'CliEnts2'):
                                self.CliEnts2.close()
                            
                            time.sleep(3)
                            self.Connect_SerVer(Token , tok , host , port , key , iv , host2 , port2)                    		                    
                        except:
                            print(f"Failed to reconnect account {self.id}")
                            with connected_clients_lock:
                                if self.id in connected_clients:
                                    del connected_clients[self.id]
                            break	            
                                      
                    if '/pp/' in self.input_msg[:4]:
                        self.target_id = self.input_msg[4:]	 
                        self.Zx = ChEck_Commande(self.target_id)
                        if True == self.Zx:	            		     
                            threading.Thread(target=send_normal_spam_max_speed, args=(self.target_id,)).start()
                            time.sleep(2.5)    			         
                            self.CliEnts.send(xSEndMsg(f'\n[b][c][{ArA_CoLor()}] SuccEss Spam To {xMsGFixinG(self.target_id)} From All Accounts\n', 2 , self.DeCode_CliEnt_Uid , self.DeCode_CliEnt_Uid , key , iv))
                            time.sleep(1.3)
                            self.CliEnts.close()
                            if hasattr(self, 'CliEnts2'):
                                self.CliEnts2.close()
                            self.Connect_SerVer(Token , tok , host , port , key , iv , host2 , port2)	            		      	
                        elif False == self.Zx: 
                            self.CliEnts.send(xSEndMsg(f'\n[b][c][{ArA_CoLor()}] - PLease Use /pp/<id>\n - Ex : /pp/{self.Exemple}\n', 2 , self.DeCode_CliEnt_Uid , self.DeCode_CliEnt_Uid , key , iv))	
                            time.sleep(1.1)
                            self.CliEnts.close()
                            if hasattr(self, 'CliEnts2'):
                                self.CliEnts2.close()
                            self.Connect_SerVer(Token , tok , host , port , key , iv , host2 , port2)	            		

                except Exception as e:
                    print(f"Error in Connect_SerVer loop for account {self.id}: {e}")
                    try:
                        if hasattr(self, 'CliEnts') and self.CliEnts:
                            self.CliEnts.close()
                        if hasattr(self, 'CliEnts2') and self.CliEnts2:
                            self.CliEnts2.close()
                    except:
                        pass
                    
                    time.sleep(self.retry_delay)
                    
                    # محاولة إعادة الاتصال بشكل محدود لتجنب Recursion Depth
                    try:
                        # بدلاً من استدعاء الدالة نفسها بشكل متكرر، نترك الحلقة الخارجية تتعامل مع الإعادة
                        # أو نقوم بإعادة تهيئة الاتصال هنا مرة واحدة
                        print(f"Attempting to reconnect account {self.id}...")
                        # نخرج من هذه المحاولة للسماح للحلقة أو المنطق الخارجي بإعادة المحاولة
                        break 
                    except Exception as re_e:
                        print(f"Reconnection attempt failed for account {self.id}: {re_e}")
                        break
        except Exception as e:
            print(f"Error in Connect_SerVer initial connection: {e}")
            time.sleep(self.retry_delay)
                                    
    def GeT_Key_Iv(self , serialized_data):
        my_message = xKEys.MyMessage()
        my_message.ParseFromString(serialized_data)
        timestamp , key , iv = my_message.field21 , my_message.field22 , my_message.field23
        timestamp_obj = Timestamp()
        timestamp_obj.FromNanoseconds(timestamp)
        timestamp_seconds = timestamp_obj.seconds
        timestamp_nanos = timestamp_obj.nanos
        combined_timestamp = timestamp_seconds * 1_000_000_000 + timestamp_nanos
        return combined_timestamp , key , iv    

    def Guest_GeneRaTe(self, uid, password):
        """
        محاولة الاتصال بسيرفر Garena للحصول على التوكن
        مع دعم روابط بديلة وتعطيل التحقق من SSL
        """
        # قائمة بالروابط البديلة لمحاولة الاتصال
        urls = [
            "https://100067.connect.garena.com/oauth/guest/token/grant",
            "https://100067.connect.garena.com/api/oauth/guest/token/grant",
            "https://account.garena.com/api/oauth/guest/token/grant",
            "https://accounts.garena.com/oauth/guest/token/grant",
            "https://connect.garena.com/oauth/guest/token/grant",
            "https://api.garena.com/oauth/guest/token/grant"
        ]
        
        self.headers = {
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        
        self.dataa = {
            "uid": f"{uid}",
            "password": f"{password}",
            "response_type": "token",
            "client_type": "2",
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_id": "100067",
        }
        
        # تجربة كل رابط في القائمة
        for url in urls:
            try:
                print(f"Trying URL: {url}")
                
                # محاولة الاتصال مع timeout وتعطيل التحقق من SSL
                response = requests.post(
                    url, 
                    headers=self.headers, 
                    data=self.dataa,
                    timeout=10,  # timeout 10 ثواني
                    verify=False  # تعطيل التحقق من SSL
                )
                
                # التحقق من نجاح الطلب
                if response.status_code == 200:
                    try:
                        response_json = response.json()
                        if 'access_token' in response_json and 'open_id' in response_json:
                            print(f"Success with URL: {url}")
                            self.Access_ToKen = response_json['access_token']
                            self.Access_Uid = response_json['open_id']
                            time.sleep(0.2)
                            return self.ToKen_GeneRaTe(self.Access_ToKen, self.Access_Uid)
                        else:
                            print(f"Response missing required fields from {url}")
                    except json.JSONDecodeError:
                        print(f"Invalid JSON response from {url}")
                else:
                    print(f"HTTP {response.status_code} from {url}")
                    
            except requests.exceptions.SSLError as e:
                print(f"SSL Error with {url}: {e}")
                continue
            except requests.exceptions.ConnectionError as e:
                print(f"Connection Error with {url}: {e}")
                continue
            except requests.exceptions.Timeout as e:
                print(f"Timeout with {url}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error with {url}: {e}")
                continue
        
        # إذا فشلت جميع المحاولات، انتظر وحاول مرة أخرى
        print(f"All URLs failed for account {uid}, retrying in {self.retry_delay} seconds...")
        time.sleep(self.retry_delay)
        # نرجع None بدلاً من Recursion للسماح للحلقة الخارجية بالتعامل مع الإعادة
        return None
                                        
    def GeT_LoGin_PorTs(self , JwT_ToKen , PayLoad):
        self.UrL = 'https://clientbp.ggwhitehawk.com/GetLoginData'
        self.HeadErs = {
            'Expect': '100-continue',
            'Authorization': f'Bearer {JwT_ToKen}',
            'X-Unity-Version': '2022.3.47f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB52',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Accept-Encoding': 'deflate, gzip',
        }        
        
        try:
            self.Res = requests.post(self.UrL , headers=self.HeadErs , data=PayLoad , verify=False , timeout=10)
            
            if self.Res.status_code == 200:
                try:
                    self.BesTo_data = json.loads(DeCode_PackEt(self.Res.content.hex()))  
                    address , address2 = self.BesTo_data['32']['data'] , self.BesTo_data['14']['data'] 
                    ip , ip2 = address[:len(address) - 6] , address2[:len(address2) - 6]
                    port , port2 = address[len(address) - 5:] , address2[len(address2) - 5:]             
                    return ip , port , ip2 , port2
                except Exception as e:
                    print(f"Error parsing GetLoginData response: {e}")
            else:
                print(f"GetLoginData returned status code: {self.Res.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"Request error in GeT_LoGin_PorTs: {e}")
        except Exception as e:
            print(f"Unexpected error in GeT_LoGin_PorTs: {e}")
            
        print(" - Failed To Get Ports!")
        return None, None, None, None
        
    def ToKen_GeneRaTe(self , Access_ToKen , Access_Uid):
        self.UrL = "https://loginbp.ggwhitehawk.com/MajorLogin"
        self.HeadErs = {
            'X-Unity-Version': '2022.3.47f1',
            'ReleaseVersion': 'OB52',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-GA': 'v1 1',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Accept-Encoding': 'deflate, gzip',
        }   
        
        self.dT = bytes.fromhex('1a13323032362d30312d31342031323a31393a3032220966726565206669726528013a07312e3132302e324232416e64726f6964204f532039202f204150492d3238202850492f72656c2e636a772e32303232303531382e313134313333294a0848616e6468656c64520c4d544e2f537061636574656c5a045749464960800a68d00572033234307a2d7838362d3634205353453320535345342e3120535345342e32204156582041565832207c2032343030207c20348001e61e8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e329a012b476f6f676c657c36323566373136662d393161372d343935622d396631362d303866653964336336353333a2010d3137362e32382e3134352e3239aa01026172b201203931333263366662373263616363666463383132306439656332636330366238ba010134c2010848616e6468656c64ca010d4f6e65506c7573204135303130d201025347ea014033646661396162396432353237306661663433326637623532383536346265396563343739306263373434613465626137303232353230373432376430633430f00101ca020c4d544e2f537061636574656cd2020457494649ca03203161633462383065636630343738613434323033626638666163363132306635e003b5ee02e803c28302f003af13f80384078004cf92028804b5ee029004cf92029804b5ee02b00404c80403d2043d2f646174612f6170702f636f6d2e6474732e667265656669726574682d49316855713474347641365f516f34432d58676165513d3d2f6c69622f61726de00401ea045f65363261623933353464386662356662303831646233333861636233333439317c2f646174612f6170702f636f6d2e6474732e667265656669726574682d49316855713474347641365f516f34432d58676165513d3d2f626173652e61706bf00406f804018a050233329a050a32303139313139363234b205094f70656e474c455332b805ff01c00504e005edb402ea05093372645f7061727479f2055c4b7173485438512b6c73302b4464496c2f4f617652726f7670795a596377676e51485151636d57776a476d587642514b4f4d63747870796f7054515754487653354a714d6967476b534c434c423651387839544161764d666c6a6f3d8806019006019a060134a2060134b206224006474f56540a011a5d0e115e00170d4b6e085709510a685a02586800096f000161')
        
        self.dT = self.dT.replace(b'2026-01-14 12:19:02' , str(datetime.now())[:-7].encode())        
        self.dT = self.dT.replace(b'3dfa9ab9d25270faf432f7b528564be9ec4790bc744a4eba70225207427d0c40' , Access_ToKen.encode())
        self.dT = self.dT.replace(b'9132c6fb72caccfdc8120d9ec2cc06b8' , Access_Uid.encode())
        
        try:
            hex_data = self.dT.hex()
            encoded_data = EnC_AEs(hex_data)
            
            if not all(c in '0123456789abcdefABCDEF' for c in encoded_data):
                print("Invalid hex output from EnC_AEs, using alternative encoding")
                encoded_data = hex_data
            
            self.PaYload = bytes.fromhex(encoded_data)
        except Exception as e:
            print(f"Error in encoding: {e}")
            self.PaYload = self.dT
        
        try:
            self.ResPonse = requests.post(self.UrL, headers=self.HeadErs, data=self.PaYload, verify=False, timeout=10)        
            
            if self.ResPonse.status_code == 200 and len(self.ResPonse.text) > 10:
                try:
                    self.BesTo_data = json.loads(DeCode_PackEt(self.ResPonse.content.hex()))
                    self.JwT_ToKen = self.BesTo_data['8']['data']           
                    self.combined_timestamp , self.key , self.iv = self.GeT_Key_Iv(self.ResPonse.content)
                    ip , port , ip2 , port2 = self.GeT_LoGin_PorTs(self.JwT_ToKen , self.PaYload)            
                    return self.JwT_ToKen , self.key , self.iv, self.combined_timestamp , ip , port , ip2 , port2
                except Exception as e:
                    print(f"Error parsing MajorLogin response: {e}")
            else:
                print(f"MajorLogin failed with status code: {self.ResPonse.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"Request error in ToKen_GeneRaTe: {e}")
        except Exception as e:
            print(f"Unexpected error in ToKen_GeneRaTe: {e}")
            
        print("Retrying ToKen_GeneRaTe...")
        time.sleep(self.retry_delay)
        return None
      
    def Get_FiNal_ToKen_0115(self):
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                result = self.Guest_GeneRaTe(self.id , self.password)
                
                if not result:
                    print(f"Failed to get tokens for account {self.id}, retrying... ({retry_count + 1}/{self.max_retries})")
                    retry_count += 1
                    time.sleep(self.retry_delay)
                    continue
                    
                token , key , iv , Timestamp , ip , port , ip2 , port2 = result
                
                if not all([ip, port, ip2, port2]):
                    print(f"Failed to get ports for account {self.id}, retrying... ({retry_count + 1}/{self.max_retries})")
                    retry_count += 1
                    time.sleep(self.retry_delay)
                    continue
                    
                self.JwT_ToKen = token        
                try:
                    self.AfTer_DeC_JwT = jwt.decode(token, options={"verify_signature": False})
                    self.AccounT_Uid = self.AfTer_DeC_JwT.get('account_id')
                    self.EncoDed_AccounT = hex(self.AccounT_Uid)[2:]
                    self.HeX_VaLue = DecodE_HeX(Timestamp)
                    self.TimE_HEx = self.HeX_VaLue
                    self.JwT_ToKen_ = token.encode().hex()
                    print(f'✅ Account connected: {self.AccounT_Uid}')
                except Exception as e:
                    print(f"Error decoding JWT: {e}")
                    retry_count += 1
                    time.sleep(self.retry_delay)
                    continue
                    
                try:
                    self.Header = hex(len(EnC_PacKeT(self.JwT_ToKen_, key, iv)) // 2)[2:]
                    length = len(self.EncoDed_AccounT)
                    self.__ = '00000000'
                    if length == 9: self.__ = '0000000'
                    elif length == 8: self.__ = '00000000'
                    elif length == 10: self.__ = '000000'
                    elif length == 7: self.__ = '000000000'
                    else:
                        print(f'Unexpected length: {length}')
                        self.__ = '00000000'            
                    
                    self.Header = f'0115{self.__}{self.EncoDed_AccounT}{self.TimE_HEx}00000{self.Header}'
                    self.FiNal_ToKen_0115 = self.Header + EnC_PacKeT(self.JwT_ToKen_ , key , iv)
                except Exception as e:
                    print(f"Error creating final token: {e}")
                    retry_count += 1
                    time.sleep(self.retry_delay)
                    continue
                    
                self.AutH_ToKen = self.FiNal_ToKen_0115
                self.Connect_SerVer(self.JwT_ToKen , self.AutH_ToKen , ip , port , key , iv , ip2 , port2)        
                return self.AutH_ToKen , key , iv
                
            except Exception as e:
                print(f"Error in Get_FiNal_ToKen_0115 for account {self.id}: {e}")
                retry_count += 1
                time.sleep(self.retry_delay)
        
        print(f"❌ Failed to connect account {self.id} after {self.max_retries} attempts")
        return None, None, None

def start_account(account):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Starting account: {account['id']} (Attempt {attempt + 1}/{max_retries})")
            client = FF_CLient(account['id'], account['password'])
            if client.key and client.iv:
                print(f"✅ Account {account['id']} connected successfully")
                return
            else:
                print(f"⚠️ Account {account['id']} connection incomplete")
        except Exception as e:
            print(f"Error starting account {account['id']}: {e}")
        time.sleep(10)
    print(f"❌ Failed to start account {account['id']} after {max_retries} attempts")

def run_bot():
    print("🤖 Bot started...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(10)

def StarT_SerVer():
    threads = []
    
    # تقسيم الحسابات إلى مجموعات للتشغيل المتدرج
    batch_size = 20
    for i in range(0, len(ACCOUNTS), batch_size):
        batch = ACCOUNTS[i:i+batch_size]
        for account in batch:
            thread = threading.Thread(target=start_account, args=(account,))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            time.sleep(0.5)  # تأخير بسيط بين الحسابات
        print(f"✅ Started batch {i//batch_size + 1}/{(len(ACCOUNTS)-1)//batch_size + 1}")
        time.sleep(2)  # تأخير بين المجموعات
    
    print(f"✅ All {len(ACCOUNTS)} accounts started")
    
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 TURBO SPAM BOT - ULTIMATE EDITION")
    print("=" * 60)
    print(f"📅 Time: {datetime.now()}")
    print(f"📊 Total accounts: {len(ACCOUNTS)}")
    print(f"🔥 Turbo Workers per target: {TURBO_WORKERS_PER_TARGET}")
    print(f"⚡ Max Workers: {MAX_WORKERS}")
    print(f"📨 Burst Size: {BURST_SIZE}")
    print(f"🔌 Connections per account: {CONNECTIONS_PER_ACCOUNT}")
    print(f"⏱️ Fixed duration: {SPAM_DURATION_MINUTES} minutes")
    print("=" * 60)
    print("📡 Player info API: https://fpi-sx-team.vercel.app/add")
    print("=" * 60)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    StarT_SerVer()