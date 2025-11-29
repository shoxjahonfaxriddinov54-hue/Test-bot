import logging
import datetime
import json
import os
import requests
import time
from collections import defaultdict

# Bot token va admin ID
BOT_TOKEN = "8415440653:AAFdD_TutJaj3D74DomDxXpBeT3X8NGjyXo"
ADMIN_ID = 6875823125

# Logging ni sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ma'lumotlarni saqlash uchun fayllar
DATA_FILE = "responses.json"
TESTS_FILE = "tests.json"
ANSWERS_FILE = "answers.json"
RESULTS_FILE = "results.json"

class TestBot:
    def __init__(self, token, admin_id):
        self.token = token
        self.admin_id = admin_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.responses = self.load_data(DATA_FILE)
        self.tests = self.load_data(TESTS_FILE)
        self.answers = self.load_data(ANSWERS_FILE)
        self.results = self.load_data(RESULTS_FILE)
        self.user_sessions = {}
        self.current_test_id = None
    
    def load_data(self, filename):
        """Ma'lumotlarni yuklash"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"{filename} yuklashda xatolik: {e}")
            return {}
    
    def save_data(self, data, filename):
        """Ma'lumotlarni saqlash"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"{filename} saqlashda xatolik: {e}")
            return False
    
    def send_message(self, chat_id, text, parse_mode='HTML', reply_markup=None):
        """Xabar yuborish"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik: {e}")
            return None
    
    def send_photo(self, chat_id, photo_file_id, caption=None):
        """Rasm yuborish"""
        url = f"{self.base_url}/sendPhoto"
        payload = {
            'chat_id': chat_id,
            'photo': photo_file_id
        }
        if caption:
            payload['caption'] = caption
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Rasm yuborishda xatolik: {e}")
            return None
    
    def get_updates(self, offset=None):
        """Yangiliklarni olish"""
        url = f"{self.base_url}/getUpdates"
        params = {'timeout': 10, 'offset': offset}
        try:
            response = requests.get(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"Updates olishda xatolik: {e}")
            return None
    
    def remove_keyboard(self):
        """Tugmalarni olib tashlash"""
        return {'remove_keyboard': True}
    
    def handle_message(self, message):
        """Xabarni qayta ishlash"""
        user_id = message['from']['id']
        text = message.get('text', '')
        first_name = message['from'].get('first_name', '')
        
        # Admin uchun maxsus start
        if user_id == self.admin_id and text == '/start':
            admin_menu = (
                "👨‍💻 <b>Admin Panel</b>\n\n"
                "Buyruqlar:\n"
                "/upload_test - Yangi test yuklash\n"
                "/set_answers - Javoblar yuklash\n" 
                "/set_timer - Test muddatini belgilash\n"
                "/current_test - Joriy testni ko'rish\n"
                "/stats - Statistika\n"
                "/results - Natijalarni ko'rish\n"
                "/leaderboard - Reyting jadvali"
            )
            self.send_message(user_id, admin_menu, reply_markup=self.remove_keyboard())
            return
        
        # /done kommandasini alohida tekshirish
        if text == '/done' and user_id == self.admin_id:
            session = self.user_sessions.get(user_id, {})
            if session.get('mode') == 'uploading_test':
                self.finish_test_upload(user_id)
                return
        
        # Command larni boshqarish
        if text.startswith('/'):
            self.handle_command(user_id, text, first_name, message)
            return
        
        # Rasm yuklash rejimi
        session = self.user_sessions.get(user_id, {})
        if session.get('mode') == 'uploading_test' and user_id == self.admin_id:
            self.process_test_upload(user_id, message)
            return
        elif session.get('mode') == 'setting_answers' and user_id == self.admin_id:
            self.process_answers(user_id, text)
            return
        elif session.get('mode') == 'setting_timer' and user_id == self.admin_id:
            self.process_timer(user_id, text)
            return
        elif session.get('mode') == 'setting_question_count' and user_id == self.admin_id:
            self.process_question_count(user_id, text)
            return
        
        # Oddiy xabar (javob) - faqat o'quvchilar uchun
        if text.strip() and user_id != self.admin_id:
            self.process_response(user_id, first_name, text)
    
    def handle_command(self, user_id, text, first_name, message):
        """Command larni boshqarish"""
        command = text.split()[0].lower()
        
        if command == '/start':
            if user_id == self.admin_id:
                return
            else:
                self.send_current_test(user_id, first_name)
        
        # Admin command lari
        elif user_id == self.admin_id:
            if command == '/upload_test':
                self.start_test_upload(user_id)
            elif command == '/set_answers':
                self.start_answers_upload(user_id)
            elif command == '/set_timer':
                self.start_timer_setting(user_id)
            elif command == '/current_test':
                self.show_current_test(user_id)
            elif command == '/stats':
                self.show_stats(user_id)
            elif command == '/results':
                self.show_results(user_id)
            elif command == '/leaderboard':
                self.show_leaderboard(user_id)
        
        else:
            if command == '/mystats':
                self.show_user_stats(user_id)
    
    def start_test_upload(self, user_id):
        """Test yuklashni boshlash"""
        self.user_sessions[user_id] = {
            'mode': 'uploading_test',
            'test_photos': [],
            'test_name': f"Test {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        }
        self.send_message(user_id, 
            "📸 <b>Test yuklash</b>\n\n"
            "Test savollarini rasm shaklida yuboring.\n"
            "Har bir rasm alohida yuboriladi.\n\n"
            "🔚 <b>Yakunlash uchun /done deb yozing</b>",
            reply_markup=self.remove_keyboard()
        )
    
    def process_test_upload(self, user_id, message):
        """Test rasmlarini qayta ishlash"""
        session = self.user_sessions.get(user_id, {})
        
        if message.get('photo'):
            photo = message['photo'][-1]
            file_id = photo['file_id']
            
            session['test_photos'].append(file_id)
            self.user_sessions[user_id] = session
            
            count = len(session['test_photos'])
            self.send_message(user_id, 
                f"✅ Rasm qabul qilindi! Jami: {count} ta\n\n"
                f"🔚 <b>Yakunlash uchun /done deb yozing</b>",
                reply_markup=self.remove_keyboard()
            )
    
    def finish_test_upload(self, user_id):
        """Test yuklashni yakunlash va savollar sonini so'rash"""
        session = self.user_sessions.get(user_id, {})
        
        if not session or session.get('mode') != 'uploading_test':
            self.send_message(user_id, "❌ Test yuklash rejimida emassiz!")
            return
        
        if len(session['test_photos']) == 0:
            self.send_message(user_id, "❌ Hech qanday rasm yuklanmadi!")
            self.user_sessions[user_id] = {}
            return
        
        # Savollar sonini so'rash
        self.user_sessions[user_id] = {
            'mode': 'setting_question_count',
            'test_photos': session['test_photos'],
            'test_name': session['test_name']
        }
        
        self.send_message(user_id,
            f"📸 Rasmlar yuklandi! Jami: {len(session['test_photos'])} ta\n\n"
            f"❓ <b>Testda jami nechta savol bor?</b>\n"
            f"Raqam kiriting (masalan: 10):",
            reply_markup=self.remove_keyboard()
        )
    
    def process_question_count(self, user_id, text):
        """Savollar sonini qayta ishlash"""
        session = self.user_sessions.get(user_id, {})
        
        if not session or session.get('mode') != 'setting_question_count':
            self.send_message(user_id, "❌ Xatolik! Qaytadan boshlang.")
            self.user_sessions[user_id] = {}
            return
        
        try:
            question_count = int(text)
            if question_count <= 0:
                self.send_message(user_id, "❌ Iltimos, musbat son kiriting!")
                return
            
            # Testni saqlash
            test_id = f"test_{int(time.time())}"
            self.tests[test_id] = {
                'name': session['test_name'],
                'photos': session['test_photos'],
                'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'question_count': question_count,
                'timer_minutes': 0,
                'active': True
            }
            self.current_test_id = test_id
            self.save_data(self.tests, TESTS_FILE)
            
            self.send_message(user_id,
                f"✅ <b>Test muvaffaqiyatli yuklandi!</b>\n\n"
                f"📝 Nomi: {session['test_name']}\n"
                f"📸 Rasmlar: {len(session['test_photos'])} ta\n"
                f"❓ Savollar: {question_count} ta\n"
                f"🆔 Test ID: {test_id}\n\n"
                "Endi javoblarni /set_answers buyrug'i bilan yuklang.",
                reply_markup=self.remove_keyboard()
            )
            self.user_sessions[user_id] = {}
            
        except ValueError:
            self.send_message(user_id, "❌ Iltimos, raqam kiriting!")
    
    def start_answers_upload(self, user_id):
        """Javoblar yuklashni boshlash"""
        if not self.current_test_id:
            self.send_message(user_id, "❌ Avval test yuklashingiz kerak!")
            return
        
        test = self.tests.get(self.current_test_id, {})
        question_count = test.get('question_count', 0)
        
        if question_count == 0:
            self.send_message(user_id, "❌ Testda savollar mavjud emas!")
            return
        
        self.user_sessions[user_id] = {
            'mode': 'setting_answers',
            'test_id': self.current_test_id
        }
        
        self.send_message(user_id,
            f"📝 <b>Javoblar yuklash</b>\n\n"
            f"Test: {test.get('name', 'Noma\'lum')}\n"
            f"Savollar soni: {question_count} ta\n\n"
            "Javoblarni quyidagi formatda yuboring:\n"
            "<code>1A 2B 3C 4D 5A 6B 7C 8D 9A 10B</code>\n\n"
            "Har bir javob raqam va variantdan iborat bo'lsin.",
            reply_markup=self.remove_keyboard()
        )
    
    def process_answers(self, user_id, text):
        """Javoblarni qayta ishlash"""
        session = self.user_sessions.get(user_id, {})
        test_id = session.get('test_id')
        
        if not test_id:
            self.send_message(user_id, "❌ Xatolik! Qaytadan boshlang.")
            self.user_sessions[user_id] = {}
            return
        
        # Javoblarni ajratish
        answers = text.strip().split()
        test = self.tests.get(test_id, {})
        question_count = test.get('question_count', 0)
        
        if len(answers) != question_count:
            self.send_message(user_id,
                f"❌ Noto'g'ri javoblar soni!\n"
                f"Kutilgan: {question_count} ta\n"
                f"Yuborilgan: {len(answers)} ta\n\n"
                "Qaytadan yuboring:"
            )
            return
        
        # Javoblarni saqlash
        self.answers[test_id] = answers
        self.save_data(self.answers, ANSWERS_FILE)
        
        self.send_message(user_id,
            f"✅ <b>Javoblar muvaffaqiyatli yuklandi!</b>\n\n"
            f"📝 Test: {test.get('name', 'Noma\'lum')}\n"
            f"✅ Javoblar soni: {len(answers)} ta\n\n"
            "O'quvchilar endi testni ishlashni boshlashlari mumkin!",
            reply_markup=self.remove_keyboard()
        )
        self.user_sessions[user_id] = {}
    
    def start_timer_setting(self, user_id):
        """Test muddatini belgilash"""
        if not self.current_test_id:
            self.send_message(user_id, "❌ Avval test yuklashingiz kerak!")
            return
        
        self.user_sessions[user_id] = {'mode': 'setting_timer'}
        
        self.send_message(user_id,
            "⏰ <b>Test muddatini belgilash</b>\n\n"
            "Test necha daqiqa davom etsin?\n"
            "Raqam kiriting (masalan: 60):",
            reply_markup=self.remove_keyboard()
        )
    
    def process_timer(self, user_id, text):
        """Test muddatini qayta ishlash"""
        try:
            minutes = int(text)
            if minutes > 0:
                test = self.tests.get(self.current_test_id, {})
                test['timer_minutes'] = minutes
                test['end_time'] = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
                self.tests[self.current_test_id] = test
                self.save_data(self.tests, TESTS_FILE)
                
                self.send_message(user_id, f"✅ Test muddati {minutes} daqiqaga sozlandi!")
                self.user_sessions[user_id] = {}
            else:
                self.send_message(user_id, "❌ Iltimos, musbat son kiriting!")
        except ValueError:
            self.send_message(user_id, "❌ Iltimos, raqam kiriting!")
    
    def send_current_test(self, user_id, first_name):
        """O'quvchiga joriy testni yuborish"""
        if not self.current_test_id:
            self.send_message(user_id,
                "📭 Hozircha test mavjud emas.\n"
                "Admin yangi test yuklagach, bu yerda paydo bo'ladi.",
                reply_markup=self.remove_keyboard()
            )
            return
        
        test = self.tests.get(self.current_test_id, {})
        answers = self.answers.get(self.current_test_id, [])
        
        if not test or not answers:
            self.send_message(user_id, "❌ Test hali to'liq tayyor emas.")
            return
        
        welcome_text = (
            f"👋 Salom {first_name}!\n\n"
            f"📝 <b>{test.get('name', 'Test')}</b>\n"
            f"📊 Savollar soni: {len(answers)} ta\n\n"
            "Quyidagi savollarni ko'rib chiqing va javobingizni yuboring:"
        )
        self.send_message(user_id, welcome_text, reply_markup=self.remove_keyboard())
        
        # Savollarni (rasmlarni) yuborish
        photos = test.get('photos', [])
        for i, photo_id in enumerate(photos, 1):
            self.send_photo(user_id, photo_id, f"Savol #{i}")
            time.sleep(1)
        
        instruction_text = (
            "📝 <b>Javob yuborish</b>\n\n"
            "Javobingizni quyidagi formatda yuboring:\n"
            "<code>Ism Familiya\n"
            "1A 2B 3C 4D 5A 6B 7C 8D 9A 10B</code>\n\n"
            "Ism va javoblar alohida qatorda bo'lishi kerak."
        )
        self.send_message(user_id, instruction_text, reply_markup=self.remove_keyboard())
    
    def show_current_test(self, user_id):
        """Joriy testni ko'rsatish"""
        if not self.current_test_id:
            self.send_message(user_id, "❌ Hozircha faol test mavjud emas.")
            return
        
        test = self.tests.get(self.current_test_id, {})
        answers = self.answers.get(self.current_test_id, [])
        
        test_info = (
            f"📊 <b>JORIY TEST</b>\n\n"
            f"📝 Nomi: {test.get('name', 'Noma\'lum')}\n"
            f"📅 Sana: {test.get('date', 'Noma\'lum')}\n"
            f"❓ Savollar: {test.get('question_count', 0)} ta\n"
            f"✅ Javoblar: {'Yuklangan' if answers else 'Yuklanmagan'}\n"
            f"⏰ Muddati: {test.get('timer_minutes', 0)} daqiqa\n"
            f"🆔 ID: {self.current_test_id}"
        )
        self.send_message(user_id, test_info)
    
    def process_response(self, user_id, user_name, text):
        """O'quvchi javobini qayta ishlash"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if self.validate_response(text):
            # Admin ga xabar
            admin_message = (
                f"📥 <b>YANGI JAVOB</b>\n"
                f"👤 <b>Foydalanuvchi:</b> {user_name}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"⏰ <b>Vaqt:</b> {timestamp}\n"
                f"📝 <b>Javob:</b>\n<code>{text}</code>"
            )
            
            admin_result = self.send_message(self.admin_id, admin_message)
            
            if admin_result and admin_result.get('ok'):
                # Saqlash
                user_key = f"{user_id}_{timestamp}"
                self.responses[user_key] = {
                    'name': user_name,
                    'response': text,
                    'timestamp': timestamp,
                    'user_id': user_id,
                    'date': datetime.datetime.now().strftime("%Y-%m-%d"),
                    'test_id': self.current_test_id
                }
                self.save_data(self.responses, DATA_FILE)
                
                # Javoblarni tekshirish
                result_text = self.check_answers(user_id, user_name, text, timestamp)
                self.send_message(user_id, result_text, reply_markup=self.remove_keyboard())
                
                logger.info(f"Yangi javob: {user_id} - {user_name}")
            else:
                self.send_message(user_id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        else:
            error_text = (
                "❌ <b>Noto'g'ri format!</b>\n\n"
                "Iltimos, quyidagi formatda yuboring:\n\n"
                "<code>Ism Familiya\n"
                "1A 2B 3C 4D 5A ...</code>\n\n"
                "Ism va javoblar alohida qatorda bo'lishi kerak."
            )
            self.send_message(user_id, error_text, reply_markup=self.remove_keyboard())
    
    def check_answers(self, user_id, user_name, text, timestamp):
        """Javoblarni tekshirish"""
        if not self.current_test_id:
            return "✅ Javobingiz qabul qilindi! Lekin test aktiv emas."
        
        correct_answers = self.answers.get(self.current_test_id, [])
        if not correct_answers:
            return "✅ Javobingiz qabul qilindi! Lekin javoblar mavjud emas."
        
        # Foydalanuvchi javoblarini ajratish
        lines = text.strip().split('\n')
        if len(lines) < 2:
            return "❌ Noto'g'ri format!"
        
        user_answers = lines[1].strip().split()
        
        if len(user_answers) != len(correct_answers):
            return f"❌ Javoblar soni noto'g'ri! Kutilgan: {len(correct_answers)} ta"
        
        # Tekshirish
        correct_count = 0
        details = []
        
        for i, (user_ans, correct_ans) in enumerate(zip(user_answers, correct_answers), 1):
            if user_ans.upper() == correct_ans.upper():
                correct_count += 1
                details.append(f"{i}. {user_ans} ✅")
            else:
                details.append(f"{i}. {user_ans} ❌ (To'g'ri: {correct_ans})")
        
        score = int((correct_count / len(correct_answers)) * 100)
        
        # Natijani saqlash
        if self.current_test_id not in self.results:
            self.results[self.current_test_id] = {}
        
        self.results[self.current_test_id][user_id] = {
            'name': user_name,
            'score': score,
            'correct': correct_count,
            'total': len(correct_answers),
            'details': details,
            'timestamp': timestamp
        }
        self.save_data(self.results, RESULTS_FILE)
        
        # Natijani tayyorlash
        result_text = (
            f"📊 <b>TEST NATIJASI</b>\n\n"
            f"👤 <b>{user_name}</b>\n"
            f"✅ To'g'ri: {correct_count}/{len(correct_answers)}\n"
            f"📈 Ball: {score}%\n\n"
            f"<b>Javoblar:</b>\n" + "\n".join(details[:10])
        )
        
        if len(details) > 10:
            result_text += f"\n\n... va yana {len(details) - 10} ta savol"
        
        return result_text
    
    def show_stats(self, user_id):
        """Statistika ko'rsatish"""
        total = len(self.responses)
        if total == 0:
            self.send_message(user_id, "📊 <b>STATISTIKA</b>\n\n📭 Hali javoblar mavjud emas.")
            return
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for r in self.responses.values() if r.get('date') == today)
        unique_users = len(set(r['user_id'] for r in self.responses.values()))
        
        stats_text = (
            f"📊 <b>STATISTIKA</b>\n\n"
            f"📈 Jami javoblar: <b>{total}</b>\n"
            f"👥 Foydalanuvchilar: <b>{unique_users}</b>\n"
            f"📅 Bugungi javoblar: <b>{today_count}</b>"
        )
        
        self.send_message(user_id, stats_text)
    
    def show_results(self, user_id):
        """Natijalarni ko'rsatish"""
        if not self.current_test_id:
            self.send_message(user_id, "❌ Hozircha test natijalari mavjud emas.")
            return
        
        test_results = self.results.get(self.current_test_id, {})
        if not test_results:
            self.send_message(user_id, "❌ Bu test uchun hali natijalar mavjud emas.")
            return
        
        test_name = self.tests.get(self.current_test_id, {}).get('name', 'Noma\'lum test')
        
        results_text = f"📊 <b>NATIJALAR: {test_name}</b>\n\n"
        
        for i, (uid, data) in enumerate(sorted(test_results.items(), 
                                              key=lambda x: x[1]['score'], 
                                              reverse=True), 1):
            results_text += (
                f"{i}. 👤 {data['name']}\n"
                f"   ✅ {data['correct']}/{data['total']} - {data['score']}%\n\n"
            )
        
        self.send_message(user_id, results_text)
    
    def show_leaderboard(self, user_id):
        """Reyting jadvali"""
        if not self.current_test_id:
            self.send_message(user_id, "❌ Hozircha reyting mavjud emas.")
            return
        
        test_results = self.results.get(self.current_test_id, {})
        if not test_results:
            self.send_message(user_id, "❌ Hali hech kim test ishlamagan.")
            return
        
        test_name = self.tests.get(self.current_test_id, {}).get('name', 'Noma\'lum test')
        
        leaderboard_text = f"🏆 <b>REYTING: {test_name}</b>\n\n"
        
        top_results = sorted(test_results.items(), 
                           key=lambda x: x[1]['score'], 
                           reverse=True)[:10]
        
        for i, (uid, data) in enumerate(top_results, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            leaderboard_text += (
                f"{medal} {data['name']}\n"
                f"   ⭐ {data['score']}% ({data['correct']}/{data['total']})\n\n"
            )
        
        self.send_message(user_id, leaderboard_text)
    
    def show_user_stats(self, user_id):
        """Foydalanuvchi statistikasi"""
        user_responses = {k: v for k, v in self.responses.items() if v['user_id'] == user_id}
        
        if not user_responses:
            self.send_message(user_id, "📊 Siz hali javob yubormagansiz.")
            return
        
        total = len(user_responses)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for r in user_responses.values() if r.get('date') == today)
        
        stats_text = (
            f"📊 <b>SIZNING STATISTIKANGIZ</b>\n\n"
            f"📈 Jami javoblar: <b>{total}</b>\n"
            f"📅 Bugungi javoblar: <b>{today_count}</b>\n\n"
            f"<b>Oxirgi javobingiz:</b>\n"
            f"⏰ {list(user_responses.values())[-1]['timestamp']}\n"
            f"📝 {list(user_responses.values())[-1]['response'][:50]}..."
        )
        
        self.send_message(user_id, stats_text)
    
    def validate_response(self, text):
        """Javob formatini tekshirish"""
        lines = text.strip().split('\n')
        return len(lines) >= 2 and any(char.isdigit() for char in lines[1])
    
    def run(self):
        """Botni ishga tushirish"""
        print("🤖 Test Bot ishga tushdi...")
        print(f"👨‍💻 Admin ID: {self.admin_id}")
        print("🔄 Yangiliklarni kuzatish...")
        
        # Oxirgi testni topish
        if self.tests:
            self.current_test_id = list(self.tests.keys())[-1]
            print(f"📝 Joriy test: {self.current_test_id}")
        
        offset = 0
        try:
            while True:
                updates = self.get_updates(offset)
                if updates and updates.get('ok'):
                    for update in updates['result']:
                        offset = update['update_id'] + 1
                        if 'message' in update:
                            self.handle_message(update['message'])
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Bot to'xtatildi.")
        except Exception as e:
            print(f"❌ Xatolik: {e}")

if __name__ == '__main__':
    bot = TestBot(BOT_TOKEN, ADMIN_ID)
    bot.run()
