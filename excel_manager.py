import os
import re
import unicodedata
import threading
from datetime import datetime
import pytz
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST)

def get_ist_today_str():
    return get_ist_now().strftime('%Y-%m-%d')

def make_leetcode_slug(title):
    if not title:
        return ''
    s = unicodedata.normalize('NFKD', str(title))
    s = s.encode('ascii', 'ignore').decode('utf-8')
    s = s.lower().replace("'", "").replace("’", "")
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')

def make_leetcode_url(title, slug=None):
    clean_slug = slug if slug else make_leetcode_slug(title)
    return f"https://leetcode.com/problems/{clean_slug}/"

def is_solved_status(status):
    if not status:
        return False
    s = str(status).strip().lower()
    if 'unsolved' in s:
        return False
    return any(k in s for k in ['solved', 'complete', 'done'])

class ExcelManager:
    def __init__(self, master_path='leetcode.xlsx', tracker_path='leetcode_tracker.xlsx'):
        self.master_path = master_path
        self.tracker_path = tracker_path
        self.lock = threading.Lock()
        self.problems = []
        self.problems_by_id = {}
        self.topics = []
        self.companies = []
        
        self.load_master()
        self.init_tracker()

    def load_master(self):
        """Loads problems catalog from master leetcode.xlsx"""
        if not os.path.exists(self.master_path):
            print(f"[ExcelManager] Warning: {self.master_path} not found.")
            return

        try:
            wb = openpyxl.load_workbook(self.master_path, data_only=True)
            sheet = None
            for sname in wb.sheetnames:
                s = wb[sname]
                if s.max_row and s.max_row > 1:
                    sheet = s
                    break

            if not sheet:
                sheet = wb.active

            header_map = {}
            for col_idx in range(1, sheet.max_column + 1):
                val = sheet.cell(row=1, column=col_idx).value
                if val:
                    header_str = str(val).strip().lower().replace(' ', '_')
                    header_map[col_idx] = header_str

            def find_col(candidates):
                # 1. Check exact matches first
                for cand in candidates:
                    for col_idx, col_name in header_map.items():
                        if cand == col_name:
                            return col_idx
                # 2. Substring match fallback
                for cand in candidates:
                    for col_idx, col_name in header_map.items():
                        if cand in col_name:
                            return col_idx
                return None

            col_id = find_col(['question_id', 'id', 'qid', 'frontend_id', 'number', '#', 'no'])
            col_title = find_col(['title', 'problem_title', 'problem_name', 'problem', 'name'])
            col_diff = find_col(['difficulty', 'diff', 'level'])
            col_topic = find_col(['topic', 'topics', 'pattern', 'category', 'tag', 'tags'])
            col_comp = find_col(['companies', 'company', 'company_tags', 'asked_by'])
            col_url = find_col(['url', 'link', 'leetcode_url'])
            col_slug = find_col(['slug', 'title_slug'])

            problems = []
            seen_topics = set()
            topic_order = []
            company_counter = {}

            def clean_company_tag(raw_comp):
                # Turn 'adobe_1year', 'facebook_6months' into 'Adobe', 'Meta', etc.
                comp = raw_comp.split('_')[0].strip()
                if comp.lower() in ('facebook', 'fb'):
                    return 'Meta'
                return comp.title()

            for row_idx in range(2, sheet.max_row + 1):
                title_val = sheet.cell(row=row_idx, column=col_title).value if col_title else None
                if not title_val:
                    continue
                title = str(title_val).strip()

                id_val = sheet.cell(row=row_idx, column=col_id).value if col_id else None
                if id_val is not None and str(id_val).strip() != '':
                    try:
                        qid = str(int(float(str(id_val).strip())))
                    except (ValueError, TypeError):
                        qid = str(id_val).strip()
                else:
                    qid = str(row_idx - 1)

                diff_val = sheet.cell(row=row_idx, column=col_diff).value if col_diff else None
                diff_str = str(diff_val).strip().capitalize() if diff_val else 'Medium'
                if 'easy' in diff_str.lower():
                    difficulty = 'Easy'
                elif 'hard' in diff_str.lower():
                    difficulty = 'Hard'
                else:
                    difficulty = 'Medium'

                topic_val = sheet.cell(row=row_idx, column=col_topic).value if col_topic else None
                topic_str = str(topic_val).strip() if topic_val else 'General'
                if topic_str and topic_str not in seen_topics:
                    seen_topics.add(topic_str)
                    topic_order.append(topic_str)

                comp_val = sheet.cell(row=row_idx, column=col_comp).value if col_comp else None
                comp_str = str(comp_val).strip() if comp_val else ''
                cleaned_companies = []
                if comp_str:
                    seen_row_comps = set()
                    for c in comp_str.split(','):
                        raw_c = c.strip()
                        if raw_c:
                            clean_c = clean_company_tag(raw_c)
                            if clean_c and clean_c not in seen_row_comps:
                                seen_row_comps.add(clean_c)
                                cleaned_companies.append(clean_c)
                                company_counter[clean_c] = company_counter.get(clean_c, 0) + 1

                cleaned_comp_str = ', '.join(cleaned_companies)

                slug_val = sheet.cell(row=row_idx, column=col_slug).value if col_slug else None
                slug = str(slug_val).strip() if slug_val else make_leetcode_slug(title)

                url_val = sheet.cell(row=row_idx, column=col_url).value if col_url else None
                url = str(url_val).strip() if url_val else make_leetcode_url(title, slug)

                prob_dict = {
                    'question_id': qid,
                    'title': title,
                    'difficulty': difficulty,
                    'topic': topic_str,
                    'companies': cleaned_comp_str,
                    'slug': slug,
                    'url': url,
                    'url_valid': True
                }
                problems.append(prob_dict)

            self.problems = problems
            self.problems_by_id = {p['question_id']: p for p in problems}
            self.topics = topic_order
            self.companies = sorted(
                [{'company': k, 'count': v} for k, v in company_counter.items()],
                key=lambda x: x['count'],
                reverse=True
            )
            print(f"[ExcelManager] Loaded {len(self.problems)} problems across {len(self.topics)} topics from {self.master_path}.")

        except Exception as e:
            print(f"[ExcelManager] Error loading {self.master_path}: {e}")

    def init_tracker(self):
        """Initializes leetcode_tracker.xlsx if not present, ensuring sheets exist."""
        with self.lock:
            if not os.path.exists(self.tracker_path):
                wb = openpyxl.Workbook()
                # Sheet 1: Progress
                ws_prog = wb.active
                ws_prog.title = "Progress"
                prog_headers = [
                    'question_id', 'title', 'difficulty', 'topic', 'status',
                    'completed_date', 'time_taken', 'hints_used', 'notes', 'solved_via'
                ]
                ws_prog.append(prog_headers)
                self._format_header(ws_prog)

                # Sheet 2: DailyDispatch
                ws_daily = wb.create_sheet(title="DailyDispatch")
                daily_headers = [
                    'dispatch_date', 'question_id', 'title', 'difficulty',
                    'topic', 'status', 'dispatched_at', 'completed_at'
                ]
                ws_daily.append(daily_headers)
                self._format_header(ws_daily)

                wb.save(self.tracker_path)
                print(f"[ExcelManager] Initialized tracker file: {self.tracker_path}")

    def _format_header(self, ws):
        header_font = Font(name='Segoe UI', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='1E293B', end_color='1E293B', fill_type='solid')
        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')

    def get_progress_dict(self):
        """Returns dict mapping question_id -> dict of progress attributes."""
        progress = {}
        with self.lock:
            if not os.path.exists(self.tracker_path):
                return progress
            try:
                wb = openpyxl.load_workbook(self.tracker_path, data_only=True)
                if "Progress" not in wb.sheetnames:
                    return progress
                ws = wb["Progress"]
                headers = [str(cell.value).strip().lower() for cell in ws[1] if cell.value is not None]
                
                col_map = {h: idx + 1 for idx, h in enumerate(headers)}
                qid_col = col_map.get('question_id', 1)
                status_col = col_map.get('status')
                date_col = col_map.get('completed_date')
                time_col = col_map.get('time_taken')
                hints_col = col_map.get('hints_used')
                notes_col = col_map.get('notes')
                via_col = col_map.get('solved_via')

                for row_idx in range(2, ws.max_row + 1):
                    qid_val = ws.cell(row=row_idx, column=qid_col).value
                    if qid_val is None:
                        continue
                    qid = str(qid_val).strip()
                    status = str(ws.cell(row=row_idx, column=status_col).value or 'Unsolved').strip() if status_col else 'Unsolved'
                    comp_date = str(ws.cell(row=row_idx, column=date_col).value or '').strip() if date_col else ''
                    time_taken = ws.cell(row=row_idx, column=time_col).value if time_col else None
                    hints_used = ws.cell(row=row_idx, column=hints_col).value if hints_col else 0
                    notes = str(ws.cell(row=row_idx, column=notes_col).value or '').strip() if notes_col else ''
                    solved_via = str(ws.cell(row=row_idx, column=via_col).value or '').strip() if via_col else ''

                    progress[qid] = {
                        'question_id': qid,
                        'status': status,
                        'completed_date': comp_date,
                        'time_taken': time_taken,
                        'hints_used': hints_used,
                        'notes': notes,
                        'solved_via': solved_via
                    }
            except Exception as e:
                print(f"[ExcelManager] Error reading progress: {e}")
        return progress

    def update_progress(self, question_id, status='Solved Independently', completed_date=None,
                        time_taken=None, hints_used=0, notes='', solved_via='web'):
        """Upserts a problem progress record in leetcode_tracker.xlsx and updates daily dispatch."""
        qid = str(question_id).strip()
        problem = self.problems_by_id.get(qid, {})
        title = problem.get('title', f"Problem #{qid}")
        difficulty = problem.get('difficulty', 'Medium')
        topic = problem.get('topic', 'General')

        now_str = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')
        if not completed_date:
            completed_date = now_str if is_solved_status(status) else ''

        with self.lock:
            wb = openpyxl.load_workbook(self.tracker_path)
            if "Progress" not in wb.sheetnames:
                ws_prog = wb.create_sheet(title="Progress")
                ws_prog.append(['question_id', 'title', 'difficulty', 'topic', 'status',
                                'completed_date', 'time_taken', 'hints_used', 'notes', 'solved_via'])
                self._format_header(ws_prog)
            else:
                ws_prog = wb["Progress"]

            # Locate existing row or append
            found_row = None
            for r in range(2, ws_prog.max_row + 1):
                if str(ws_prog.cell(row=r, column=1).value).strip() == qid:
                    found_row = r
                    break

            if found_row:
                ws_prog.cell(row=found_row, column=2, value=title)
                ws_prog.cell(row=found_row, column=3, value=difficulty)
                ws_prog.cell(row=found_row, column=4, value=topic)
                ws_prog.cell(row=found_row, column=5, value=status)
                ws_prog.cell(row=found_row, column=6, value=completed_date)
                ws_prog.cell(row=found_row, column=7, value=time_taken)
                ws_prog.cell(row=found_row, column=8, value=hints_used)
                ws_prog.cell(row=found_row, column=9, value=notes)
                ws_prog.cell(row=found_row, column=10, value=solved_via)
            else:
                ws_prog.append([qid, title, difficulty, topic, status,
                                completed_date, time_taken, hints_used, notes, solved_via])

            # Also update DailyDispatch if this problem was dispatched
            if "DailyDispatch" in wb.sheetnames:
                ws_daily = wb["DailyDispatch"]
                today_str = get_ist_today_str()
                for r in range(2, ws_daily.max_row + 1):
                    d_date = str(ws_daily.cell(row=r, column=1).value or '').strip()
                    d_qid = str(ws_daily.cell(row=r, column=2).value or '').strip()
                    if d_date == today_str and d_qid == qid:
                        ws_daily.cell(row=r, column=6, value=status)
                        if is_solved_status(status):
                            ws_daily.cell(row=r, column=8, value=now_str)

            wb.save(self.tracker_path)
            print(f"[ExcelManager] Updated #{qid} -> {status} (via {solved_via}) in {self.tracker_path}")
            return True

    def get_daily_batch(self, target_date=None, force_regenerate=False):
        """Retrieves or generates today's dispatched problems according to sizing rules."""
        if not target_date:
            target_date = get_ist_today_str()

        progress = self.get_progress_dict()

        with self.lock:
            wb = openpyxl.load_workbook(self.tracker_path)
            if "DailyDispatch" not in wb.sheetnames:
                ws_daily = wb.create_sheet(title="DailyDispatch")
                ws_daily.append(['dispatch_date', 'question_id', 'title', 'difficulty',
                                'topic', 'status', 'dispatched_at', 'completed_at'])
                self._format_header(ws_daily)
                wb.save(self.tracker_path)
            else:
                ws_daily = wb["DailyDispatch"]

            existing_for_date = []
            for r in range(2, ws_daily.max_row + 1):
                d_date = str(ws_daily.cell(row=r, column=1).value or '').strip()
                if d_date == target_date:
                    qid = str(ws_daily.cell(row=r, column=2).value or '').strip()
                    existing_for_date.append((r, qid))

            if existing_for_date and not force_regenerate:
                # Return existing assigned batch
                results = []
                for row_idx, qid in existing_for_date:
                    prob = self.problems_by_id.get(qid, {})
                    prog = progress.get(qid, {})
                    status = prog.get('status', 'Unsolved')
                    is_done = is_solved_status(status)
                    results.append({
                        'question_id': qid,
                        'title': prob.get('title', f"Problem #{qid}"),
                        'difficulty': prob.get('difficulty', 'Medium'),
                        'topic': prob.get('topic', 'General'),
                        'companies': prob.get('companies', ''),
                        'url': prob.get('url', make_leetcode_url(prob.get('title', ''))),
                        'slug': prob.get('slug', make_leetcode_slug(prob.get('title', ''))),
                        'status': status,
                        'is_completed_today': is_done,
                        'type': 'REVIEW' if 'review' in status.lower() else 'NEW'
                    })
                return results

            # If force_regenerate, clear old rows for this date
            if force_regenerate and existing_for_date:
                # Delete rows in reverse order
                for row_idx, _ in sorted(existing_for_date, key=lambda x: x[0], reverse=True):
                    ws_daily.delete_rows(row_idx)

            # Generate new batch according to rules:
            # 1. Determine active topic with unsolved problems
            # 2. Pick next unsolved problem
            #    If Easy: pick 2 Easy problems (from topic or general)
            #    If Medium: pick 1 Medium problem
            #    If Hard: pick 1 Hard problem
            chosen_problems = self._select_next_problems(progress)

            now_str = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')
            for p in chosen_problems:
                qid = p['question_id']
                prog = progress.get(qid, {})
                status = prog.get('status', 'Unsolved')
                ws_daily.append([
                    target_date, qid, p['title'], p['difficulty'], p['topic'],
                    status, now_str, ''
                ])

            wb.save(self.tracker_path)

            results = []
            for p in chosen_problems:
                qid = p['question_id']
                prog = progress.get(qid, {})
                status = prog.get('status', 'Unsolved')
                results.append({
                    'question_id': qid,
                    'title': p['title'],
                    'difficulty': p['difficulty'],
                    'topic': p['topic'],
                    'companies': p.get('companies', ''),
                    'url': p.get('url', make_leetcode_url(p['title'])),
                    'slug': p.get('slug', make_leetcode_slug(p['title'])),
                    'status': status,
                    'is_completed_today': is_solved_status(status),
                    'type': 'NEW'
                })
            return results

    def _select_next_problems(self, progress):
        """Algorithm: Topic-wise progression + Easy=2, Medium=1, Hard=1."""
        unsolved = [p for p in self.problems if not is_solved_status(progress.get(p['question_id'], {}).get('status'))]

        if not unsolved:
            # All problems completed! Pick 1-2 for review
            return self.problems[:1] if self.problems else []

        # Find active topic (first topic in order with unsolved problems)
        active_topic = None
        for t in self.topics:
            if any(p['topic'] == t for p in unsolved):
                active_topic = t
                break

        topic_unsolved = [p for p in unsolved if p['topic'] == active_topic] if active_topic else unsolved
        if not topic_unsolved:
            topic_unsolved = unsolved

        # First unsolved problem
        first_prob = topic_unsolved[0]
        diff = first_prob['difficulty']

        if diff == 'Easy':
            # Need 2 problems: first_prob + another Easy problem
            other_easies = [p for p in topic_unsolved[1:] if p['difficulty'] == 'Easy']
            if not other_easies:
                # Search all unsolved for another Easy
                other_easies = [p for p in unsolved if p['question_id'] != first_prob['question_id'] and p['difficulty'] == 'Easy']
            if other_easies:
                return [first_prob, other_easies[0]]
            elif len(topic_unsolved) > 1:
                return [first_prob, topic_unsolved[1]]
            else:
                return [first_prob]
        else:
            # Medium -> 1 problem; Hard -> 1 problem
            return [first_prob]

    def get_stats(self):
        """Calculates comprehensive statistics for the dashboard analytics tab."""
        progress = self.get_progress_dict()
        total_master = len(self.problems)

        solved_count = 0
        indep_count = 0
        hint_count = 0
        review_count = 0
        reviews_due_count = 0

        diff_stats = {
            'Easy': {'total': 0, 'solved': 0},
            'Medium': {'total': 0, 'solved': 0},
            'Hard': {'total': 0, 'solved': 0}
        }

        topic_stats = {t: {'total': 0, 'solved': 0} for t in self.topics}

        weak_concepts = []

        for p in self.problems:
            qid = p['question_id']
            diff = p['difficulty']
            topic = p['topic']

            if diff in diff_stats:
                diff_stats[diff]['total'] += 1

            if topic in topic_stats:
                topic_stats[topic]['total'] += 1

            prog = progress.get(qid)
            if prog and is_solved_status(prog.get('status')):
                solved_count += 1
                if diff in diff_stats:
                    diff_stats[diff]['solved'] += 1
                if topic in topic_stats:
                    topic_stats[topic]['solved'] += 1

                st = prog.get('status', '').lower()
                if 'independently' in st:
                    indep_count += 1
                elif 'hint' in st or 'solution' in st:
                    hint_count += 1
                elif 'review' in st:
                    review_count += 1

                # Collect feedback concepts if any
                notes = prog.get('notes', '')
                if notes and 'weak concept:' in notes.lower():
                    for line in notes.split('\n'):
                        if 'weak concept:' in line.lower():
                            concept = line.replace('Weak concept:', '').strip()
                            if concept and concept not in weak_concepts:
                                weak_concepts.append(concept)
            elif prog and 'attempted' in prog.get('status', '').lower():
                reviews_due_count += 1

        comp_rate = round((solved_count / total_master * 100), 1) if total_master > 0 else 0.0

        topic_list = []
        for t in self.topics:
            tot = topic_stats[t]['total']
            sol = topic_stats[t]['solved']
            pct = round((sol / tot * 100), 1) if tot > 0 else 0.0
            topic_list.append({
                'topic': t,
                'total': tot,
                'solved': sol,
                'percentage': pct
            })

        return {
            'total_solved': solved_count,
            'total_master': total_master,
            'completion_rate': comp_rate,
            'solved_breakdown': {
                'independent': indep_count,
                'with_hint': hint_count,
                'review_solved': review_count
            },
            'reviews_due_count': reviews_due_count,
            'difficulty_breakdown': diff_stats,
            'topics': topic_list,
            'weak_concepts': weak_concepts[:12]
        }

    def search_problems(self, search='', topic='all', difficulty='all', company='all',
                        status='all', page=1, per_page=30):
        """Searches and filters problems for the Problem Explorer tab."""
        progress = self.get_progress_dict()
        search_lower = search.strip().lower()

        filtered = []
        for p in self.problems:
            qid = p['question_id']
            prog = progress.get(qid, {})
            p_status = prog.get('status', 'Unsolved')
            is_done = is_solved_status(p_status)

            # Query filter (title or #ID)
            if search_lower:
                clean_q = search_lower.lstrip('#').strip()
                match_id = clean_q == qid
                match_title = search_lower in p['title'].lower()
                if not (match_id or match_title):
                    continue

            # Topic filter
            if topic != 'all' and p['topic'].lower() != topic.lower():
                continue

            # Difficulty filter
            if difficulty != 'all' and p['difficulty'].lower() != difficulty.lower():
                continue

            # Company filter
            if company != 'all' and company.lower() not in p.get('companies', '').lower():
                continue

            # Status filter
            if status != 'all':
                st_filter = status.lower()
                if st_filter == 'solved' and not is_done:
                    continue
                elif st_filter == 'unsolved' and is_done:
                    continue
                elif st_filter == 'attempted' and 'attempt' not in p_status.lower():
                    continue
                elif st_filter == 'review' and 'review' not in p_status.lower():
                    continue

            filtered.append({
                'question_id': qid,
                'title': p['title'],
                'difficulty': p['difficulty'],
                'topic': p['topic'],
                'companies': p.get('companies', ''),
                'url': p['url'],
                'slug': p['slug'],
                'status': p_status,
                'url_valid': True
            })

        total = len(filtered)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        items = filtered[start_idx:end_idx]

        return {
            'total': total,
            'page': page,
            'total_pages': total_pages,
            'per_page': per_page,
            'items': items
        }

    def reset_progress(self):
        """Resets all tracker progress to 0."""
        with self.lock:
            wb = openpyxl.Workbook()
            ws_prog = wb.active
            ws_prog.title = "Progress"
            ws_prog.append(['question_id', 'title', 'difficulty', 'topic', 'status',
                            'completed_date', 'time_taken', 'hints_used', 'notes', 'solved_via'])
            self._format_header(ws_prog)

            ws_daily = wb.create_sheet(title="DailyDispatch")
            ws_daily.append(['dispatch_date', 'question_id', 'title', 'difficulty',
                            'topic', 'status', 'dispatched_at', 'completed_at'])
            self._format_header(ws_daily)

            wb.save(self.tracker_path)
            print(f"[ExcelManager] Reset tracker: {self.tracker_path}")
            return True
