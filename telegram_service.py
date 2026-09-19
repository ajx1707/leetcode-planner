import os
import time
import json
import html
import threading
import requests
from dotenv import load_dotenv

load_dotenv()

class TelegramService:
    def __init__(self, excel_manager, bot_token=None, chat_id=None):
        self.excel_manager = excel_manager
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID', '').strip()
        self.is_running = False
        self.poll_thread = None
        self.last_update_id = 0

    def update_credentials(self, bot_token=None, chat_id=None):
        if bot_token:
            self.bot_token = bot_token.strip()
        if chat_id:
            self.chat_id = chat_id.strip()

    def is_configured(self):
        return bool(self.bot_token and self.chat_id)

    def _api_url(self, method):
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def send_message(self, text, reply_markup=None, parse_mode="HTML"):
        if not self.is_configured():
            return {"success": False, "error": "Telegram Bot Token or Chat ID not configured."}
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)

            resp = requests.post(self._api_url("sendMessage"), json=payload, timeout=12)
            data = resp.json()
            if data.get("ok"):
                return {"success": True, "result": data.get("result")}
            else:
                return {"success": False, "error": data.get("description", "Unknown Telegram API error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_ping(self):
        msg = (
            "🤖 <b>LeetCode Scheduler & Planner</b>\n\n"
            "✅ Connection test successful! Your bot is correctly linked to this chat.\n\n"
            "• Morning Dispatch: <b>09:00 AM IST</b>\n"
            "• Evening Reminder: <b>07:00 PM IST</b>\n\n"
            "Type /today anytime to view your assigned practice."
        )
        return self.send_message(msg)

    def dispatch_daily_practice(self, problems=None):
        """Sends today's scheduled practice problems with inline action buttons."""
        if not problems:
            problems = self.excel_manager.get_daily_batch()

        if not problems:
            return {"success": False, "error": "No problems scheduled for today."}

        active_topic = html.escape(str(problems[0].get('topic', 'General'))) if problems else 'General'
        header = f"🎯 <b>LEETCODE DAILY PRACTICE</b>\n<i>Topic: {active_topic}</i>\n"
        
        body_lines = []
        inline_keyboard = []

        for idx, p in enumerate(problems, 1):
            qid = html.escape(str(p['question_id']))
            title = html.escape(str(p['title']))
            diff = html.escape(str(p['difficulty']))
            url = p['url']
            is_done = p.get('is_completed_today', False)
            status_symbol = "✅" if is_done else "⏳"
            status_text = html.escape(str(p.get('status', 'Unsolved')))

            body_lines.append(
                f"\n<b>{idx}. #{qid} — {title}</b>\n"
                f"   • Difficulty: <b>{diff}</b>\n"
                f"   • Status: {status_symbol} <i>{status_text}</i>\n"
                f"   • Solve: <a href=\"{url}\">Open on LeetCode ↗</a>"
            )

            # Row of buttons for this problem
            btn_row = []
            if is_done:
                btn_row.append({"text": f"✓ #{qid} Completed", "callback_data": f"noop:{qid}"})
            else:
                btn_row.append({"text": f"✅ Mark #{qid} Complete", "callback_data": f"done:{qid}"})

            btn_row.append({"text": f"🔗 Problem #{qid}", "url": url})
            inline_keyboard.append(btn_row)

        footer = "\n\n💡 <i>Mark complete directly using the buttons above or via the Web UI!</i>"
        full_text = header + "".join(body_lines) + footer

        reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
        res = self.send_message(full_text, reply_markup=reply_markup)
        print(f"[TelegramService] dispatch_daily_practice result: {res}")
        return res

    def dispatch_evening_reminder(self):
        """Sends an evening reminder if problems remain unfinished."""
        problems = self.excel_manager.get_daily_batch()
        pending = [p for p in problems if not p.get('is_completed_today', False)]

        if not pending:
            print("[TelegramService] Evening check: All daily problems are already solved!")
            return {"success": True, "message": "All solved, no reminder needed.", "pending_count": 0}

        header = f"⏰ <b>LEETCODE EVENING REMINDER (7:00 PM IST)</b>\n"
        header += f"You have <b>{len(pending)} problem(s)</b> remaining from today's assignment:\n"

        body_lines = []
        inline_keyboard = []

        for p in pending:
            qid = html.escape(str(p['question_id']))
            title = html.escape(str(p['title']))
            diff = html.escape(str(p['difficulty']))
            url = p['url']

            body_lines.append(
                f"\n• <b>#{qid}: {title}</b> ({diff})\n"
                f"  Link: <a href=\"{url}\">Open LeetCode</a>"
            )

            inline_keyboard.append([
                {"text": f"✅ Mark #{qid} Complete", "callback_data": f"done:{qid}"},
                {"text": f"🔗 Problem #{qid}", "url": url}
            ])

        footer = "\n\n💪 <i>Set aside 30 minutes tonight to keep your consistency streak alive!</i>"
        full_text = header + "".join(body_lines) + footer

        reply_markup = {"inline_keyboard": inline_keyboard}
        res = self.send_message(full_text, reply_markup=reply_markup)
        print(f"[TelegramService] dispatch_evening_reminder result: {res}")
        res["pending_count"] = len(pending)
        return res

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        try:
            payload = {"callback_query_id": callback_query_id}
            if text:
                payload["text"] = text
                payload["show_alert"] = show_alert
            requests.post(self._api_url("answerCallbackQuery"), json=payload, timeout=8)
        except Exception as e:
            print(f"[TelegramService] Error answering callback query: {e}")

    def edit_message_reply_markup(self, chat_id, message_id, reply_markup):
        try:
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": json.dumps(reply_markup)
            }
            requests.post(self._api_url("editMessageReplyMarkup"), json=payload, timeout=8)
        except Exception as e:
            print(f"[TelegramService] Error editing reply markup: {e}")

    def start_polling(self):
        """Starts background daemon polling thread for receiving Telegram callback buttons & commands."""
        if self.is_running:
            return
        if not self.bot_token:
            print("[TelegramService] Bot token not provided; polling not started.")
            return

        self.is_running = True
        self.poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.poll_thread.start()
        print("[TelegramService] Background Telegram polling thread started.")

    def stop_polling(self):
        self.is_running = False

    def _polling_loop(self):
        while self.is_running:
            try:
                if not self.bot_token:
                    time.sleep(3)
                    continue

                url = self._api_url("getUpdates")
                params = {"offset": self.last_update_id + 1, "timeout": 20}
                resp = requests.get(url, params=params, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        for update in updates:
                            self.last_update_id = update.get("update_id", self.last_update_id)
                            self._handle_update(update)
                else:
                    time.sleep(5)
            except Exception as e:
                # Network hiccups or timeouts
                time.sleep(3)

    def _handle_update(self, update):
        # 1. Handle Inline Button Callback Queries
        if "callback_query" in update:
            cq = update["callback_query"]
            cq_id = cq.get("id")
            data = cq.get("data", "")
            message = cq.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            msg_id = message.get("message_id")

            if data.startswith("done:"):
                qid = data.split(":", 1)[1]
                # Update tracker Excel
                self.excel_manager.update_progress(
                    question_id=qid,
                    status="Solved Independently",
                    solved_via="telegram"
                )
                self.answer_callback_query(cq_id, text=f"🎉 Problem #{qid} marked as solved!", show_alert=False)

                # Update the button markup in the message to show completed
                if "reply_markup" in message and "inline_keyboard" in message["reply_markup"]:
                    keyboard = message["reply_markup"]["inline_keyboard"]
                    for row in keyboard:
                        for btn in row:
                            if btn.get("callback_data") == f"done:{qid}":
                                btn["text"] = f"✓ #{qid} Completed"
                                btn["callback_data"] = f"noop:{qid}"
                    self.edit_message_reply_markup(chat_id, msg_id, {"inline_keyboard": keyboard})

            elif data.startswith("noop:"):
                qid = data.split(":", 1)[1]
                self.answer_callback_query(cq_id, text=f"Problem #{qid} is already completed! 🎯", show_alert=False)

        # 2. Handle Text Commands
        elif "message" in update and "text" in update["message"]:
            msg = update["message"]
            chat_id = str(msg.get("chat", {}).get("id"))
            text = msg.get("text", "").strip()

            # If user hasn't set chat_id, remember this chat_id
            if not self.chat_id:
                self.chat_id = chat_id
                print(f"[TelegramService] Automatically detected Telegram chat_id: {chat_id}")

            if text.startswith("/start"):
                welcome = (
                    "👋 <b>Welcome to your LeetCode Daily Planner!</b>\n\n"
                    "I will dispatch your calibrated practice problems daily at <b>09:00 AM IST</b> "
                    "and check in with you at <b>07:00 PM IST</b>.\n\n"
                    "Commands:\n"
                    "• /today — View today's practice problems\n"
                    "• /status — View overall completion metrics\n"
                    "• /help — Show command guide"
                )
                self.send_message(welcome)

            elif text.startswith("/today"):
                self.dispatch_daily_practice()

            elif text.startswith("/status"):
                stats = self.excel_manager.get_stats()
                stat_msg = (
                    "📊 <b>LeetCode Practice Stats</b>\n\n"
                    f"• Total Solved: <b>{stats['total_solved']}</b> / {stats['total_master']} ({stats['completion_rate']}%)\n"
                    f"• Easy: {stats['difficulty_breakdown']['Easy']['solved']}/{stats['difficulty_breakdown']['Easy']['total']}\n"
                    f"• Medium: {stats['difficulty_breakdown']['Medium']['solved']}/{stats['difficulty_breakdown']['Medium']['total']}\n"
                    f"• Hard: {stats['difficulty_breakdown']['Hard']['solved']}/{stats['difficulty_breakdown']['Hard']['total']}\n\n"
                    "Keep up the great momentum! 🚀"
                )
                self.send_message(stat_msg)

            elif text.startswith("/help"):
                help_msg = (
                    "📖 <b>LeetCode Bot Commands</b>\n\n"
                    "/today - View today's assigned problems with solve buttons\n"
                    "/status - View your total solved metrics and completion rate\n"
                    "/help - Show this guide"
                )
                self.send_message(help_msg)
