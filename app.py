import os
from datetime import timedelta
import pytz
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from excel_manager import ExcelManager
from telegram_service import TelegramService

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'leetcode-planner-secret-key-2026-safe')
app.permanent_session_lifetime = timedelta(days=30)
APP_PASSWORD = os.getenv('APP_PASSWORD', 'ajith2026').strip()

@app.before_request
def require_login():
    # If no password configured, allow access
    if not APP_PASSWORD:
        return None

    # Allow static assets
    if request.path.startswith('/static/'):
        return None

    # Allow login and logout routes
    if request.path in ('/login', '/logout'):
        return None

    # Allow automated external webhook triggers and keep-alive pings (e.g. Cron-job.org)
    if request.path in ('/api/ping', '/api/status') or request.path.startswith('/api/scheduler/'):
        return None

    # Check session
    if not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not APP_PASSWORD or session.get('logged_in'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        entered_pw = request.form.get('password', '').strip()
        if entered_pw == APP_PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('index'))
        else:
            error = "Invalid passcode. Please try again."

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Initialize Managers
excel_manager = ExcelManager(
    master_path=os.getenv('MASTER_EXCEL_PATH', 'leetcode.xlsx'),
    tracker_path=os.getenv('TRACKER_EXCEL_PATH', 'leetcode_tracker.xlsx')
)

telegram_service = TelegramService(
    excel_manager=excel_manager,
    bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
    chat_id=os.getenv('TELEGRAM_CHAT_ID', '')
)

# Start Telegram background polling for inline buttons & commands
telegram_service.start_polling()

# Timezone setup (IST)
IST = pytz.timezone(os.getenv('TIMEZONE', 'Asia/Kolkata'))
scheduler = BackgroundScheduler(timezone=IST)

def scheduled_morning_dispatch():
    print("[Scheduler] Running 9:00 AM IST Morning Practice Dispatch...")
    problems = excel_manager.get_daily_batch()
    if telegram_service.is_configured():
        res = telegram_service.dispatch_daily_practice(problems, force=False)
        print(f"[Scheduler] Dispatched morning practice: {res}")
    else:
        print("[Scheduler] Telegram not configured; practice batch prepared in tracker.")

def scheduled_evening_reminder():
    print("[Scheduler] Running 7:00 PM IST Evening Reminder Check...")
    if telegram_service.is_configured():
        res = telegram_service.dispatch_evening_reminder(force=False)
        print(f"[Scheduler] Evening reminder result: {res}")

m_hour = int(os.getenv('MORNING_DISPATCH_HOUR', 9))
m_minute = int(os.getenv('MORNING_DISPATCH_MINUTE', 0))
e_hour = int(os.getenv('EVENING_REMINDER_HOUR', 19))
e_minute = int(os.getenv('EVENING_REMINDER_MINUTE', 0))

scheduler.add_job(
    scheduled_morning_dispatch,
    CronTrigger(hour=m_hour, minute=m_minute, timezone=IST),
    id='morning_dispatch',
    replace_existing=True
)

scheduler.add_job(
    scheduled_evening_reminder,
    CronTrigger(hour=e_hour, minute=e_minute, timezone=IST),
    id='evening_reminder',
    replace_existing=True
)

scheduler.start()
print(f"[Scheduler] APScheduler active. Morning job at {m_hour:02d}:{m_minute:02d} IST, Evening job at {e_hour:02d}:{e_minute:02d} IST.")

# ============================================================================
# Routes & Endpoints
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        'success': True,
        'ai_ready': False,
        'telegram_ready': telegram_service.is_configured(),
        'scheduler_ready': scheduler.running,
        'total_catalog': len(excel_manager.problems),
        'morning_time': f"{m_hour:02d}:{m_minute:02d} AM IST",
        'evening_time': f"{(e_hour - 12) if e_hour > 12 else e_hour:02d}:{e_minute:02d} PM IST"
    })

@app.route('/api/stats', methods=['GET'])
def api_stats():
    try:
        stats = excel_manager.get_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/daily', methods=['GET'])
def api_daily():
    try:
        company = request.args.get('company', '').strip()
        regenerate = request.args.get('regenerate', 'false').lower() == 'true'
        
        batch = excel_manager.get_daily_batch(force_regenerate=regenerate)
        if company:
            batch = [p for p in batch if company.lower() in p.get('companies', '').lower()]
        return jsonify({'success': True, 'data': batch})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/daily/mark-complete', methods=['POST'])
def api_daily_mark_complete():
    try:
        data = request.get_json() or {}
        qid = str(data.get('question_id', '')).strip()
        if not qid:
            return jsonify({'success': False, 'error': 'Missing question_id'}), 400
        
        excel_manager.update_progress(
            question_id=qid,
            status='Solved Independently',
            solved_via='web'
        )
        return jsonify({'success': True, 'question_id': qid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/problems', methods=['GET'])
def api_problems():
    try:
        search = request.args.get('search', '')
        topic = request.args.get('topic', 'all')
        difficulty = request.args.get('difficulty', 'all')
        company = request.args.get('company', 'all')
        status = request.args.get('status', 'all')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 30))

        data = excel_manager.search_problems(
            search=search,
            topic=topic,
            difficulty=difficulty,
            company=company,
            status=status,
            page=page,
            per_page=per_page
        )
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/problem/<qid_or_title>', methods=['GET'])
def api_problem_single(qid_or_title):
    query = str(qid_or_title).strip()
    clean_qid = query.lstrip('#').strip()
    if clean_qid in excel_manager.problems_by_id:
        return jsonify({'success': True, 'data': excel_manager.problems_by_id[clean_qid]})

    for p in excel_manager.problems:
        if p['title'].lower() == query.lower() or query.lower() in p['title'].lower():
            return jsonify({'success': True, 'data': p})

    return jsonify({'success': False, 'error': 'Problem not found in master catalog'}), 404

@app.route('/api/progress/update', methods=['POST'])
def api_progress_update():
    try:
        data = request.get_json() or {}
        qid = str(data.get('question_id', '')).strip()
        if not qid:
            return jsonify({'success': False, 'error': 'Missing question_id'}), 400

        status = data.get('status', 'Solved Independently')
        attempt_date = data.get('attempt_date')
        time_taken = data.get('time_taken')
        hints_used = int(data.get('hints_used', 0) or 0)
        feedback = data.get('feedback', '').strip()

        excel_manager.update_progress(
            question_id=qid,
            status=status,
            completed_date=attempt_date,
            time_taken=time_taken,
            hints_used=hints_used,
            notes=feedback,
            solved_via='web'
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/companies', methods=['GET'])
def api_companies():
    return jsonify({'success': True, 'data': excel_manager.companies})

@app.route('/api/topics', methods=['GET'])
def api_topics():
    return jsonify({'success': True, 'data': excel_manager.topics})

@app.route('/api/telegram/test', methods=['GET', 'POST'])
def api_telegram_test():
    res = telegram_service.test_ping()
    return jsonify(res)

@app.route('/api/telegram/send-daily', methods=['GET', 'POST'])
def api_telegram_send_daily():
    res = telegram_service.dispatch_daily_practice(force=True)
    return jsonify(res)

@app.route('/api/telegram/config', methods=['POST'])
def api_telegram_config():
    try:
        data = request.get_json() or {}
        token = data.get('token', '').strip()
        chat_id = data.get('chat_id', '').strip()

        if token:
            telegram_service.bot_token = token
        if chat_id:
            telegram_service.chat_id = chat_id

        # Update .env file
        env_lines = []
        if os.path.exists('.env'):
            with open('.env', 'r', encoding='utf-8') as f:
                env_lines = f.readlines()

        new_lines = []
        token_found = False
        chat_found = False
        for line in env_lines:
            if line.startswith('TELEGRAM_BOT_TOKEN='):
                new_lines.append(f"TELEGRAM_BOT_TOKEN={telegram_service.bot_token}\n")
                token_found = True
            elif line.startswith('TELEGRAM_CHAT_ID='):
                new_lines.append(f"TELEGRAM_CHAT_ID={telegram_service.chat_id}\n")
                chat_found = True
            else:
                new_lines.append(line)

        if not token_found:
            new_lines.append(f"TELEGRAM_BOT_TOKEN={telegram_service.bot_token}\n")
        if not chat_found:
            new_lines.append(f"TELEGRAM_CHAT_ID={telegram_service.chat_id}\n")

        with open('.env', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # Restart polling thread if needed
        telegram_service.start_polling()

        return jsonify({'success': True, 'configured': telegram_service.is_configured()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ping', methods=['GET'])
def api_ping():
    return jsonify({'status': 'ok'}), 200

@app.route('/api/scheduler/trigger-morning', methods=['GET', 'POST'])
def api_trigger_morning():
    try:
        problems = excel_manager.get_daily_batch()
        tg_res = telegram_service.dispatch_daily_practice(problems, force=False)
        return jsonify({
            'success': tg_res.get('success', False),
            'count': len(problems),
            'message': 'Morning practice dispatched' if tg_res.get('success') else tg_res.get('error', 'Failed')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scheduler/trigger-evening', methods=['GET', 'POST'])
def api_trigger_evening():
    try:
        res = telegram_service.dispatch_evening_reminder(force=False)
        return jsonify({
            'success': res.get('success', False),
            'pending_count': res.get('pending_count', 0),
            'message': res.get('message', 'Evening reminder check finished')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tracker/download', methods=['GET'])
def api_tracker_download():
    if os.path.exists(excel_manager.tracker_path):
        from flask import send_file
        return send_file(excel_manager.tracker_path, as_attachment=True, download_name='leetcode_tracker.xlsx')
    return jsonify({'success': False, 'error': 'Tracker file not found'}), 404

@app.route('/api/progress/reset', methods=['POST'])
def api_progress_reset():
    try:
        excel_manager.reset_progress()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/urls/status', methods=['GET'])
def api_urls_status():
    total = len(excel_manager.problems)
    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'valid': total,
            'invalid': 0,
            'unknown': 0,
            'coverage_pct': 100.0
        }
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '127.0.0.1')
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    print(f"\n[SERVER] LeetCode Scheduler & Planner running at http://{host}:{port}/\n")
    app.run(host=host, port=port, debug=debug)
