from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, session
import csv
import os
import json
from datetime import date, datetime
from collections import Counter
import re
from io import StringIO 
import hashlib 
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

ROLES = ['مدرب', 'رئيس قسم', 'وكيل شؤون متدربين', 'وكيل جودة', 'عميد', 'مدير نظام']
ADMIN_PASSWORD = os.environ.get('ADMIN_PASS', 'admin')

CSV_FILE = 'violations.csv'
TRAINERS_FILE = 'trainers.json'
DEPARTMENTS_FILE = 'departments.csv'
VIOLATION_LEVELS_FILE = 'violation_levels.csv'
BUILDINGS_FILE = 'buildings.csv'
ROOMS_FILE = 'rooms.csv'
ACTIONS_FILE = 'violation_actions.csv'
VIOLATION_LOGS_FILE = 'violation_logs.csv'

BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}النظام الإداري للمخالفات{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/toastr.js/latest/toastr.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.11.5/css/dataTables.bootstrap5.min.css">
    <style>
        body { font-family: Arial, sans-serif; 
		 justify-content: center;  /* توسيط أفقي */
      align-items: center;      /* توسيط عمودي */
		
	}
        .table-action-cell { min-width: 150px; }
		
	    img.logo {
      width: 340px;   /* حجم مناسب للشعار */
      height: auto;   /* للحفاظ على النسبة */
      border-radius: 10px; /* حواف ناعمة اختيارية */
	  align-items-center;
	  
	      h5 {
      margin-top: 20px;
      color: #333;
      font-family: "Tahoma", sans-serif;
    }
    </style>
</head>
<body class="bg-light d-flex flex-column  align-items-center vh-50">
  <img src="{{ url_for('static', filename='img/tvtc.png') }}" alt="شعار الموقع" class="logo">




    <div class="container mt-4">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-{{ 'success' if 'نجاح' in message else 'warning' if 'تحديث' in message or 'تنبيه' in message else 'danger' if 'خطأ' in message else 'info' }}" role="alert">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {{ content|safe }}
    </div>
    
    <div class="modal fade" id="inactivityModal" tabindex="-1" aria-labelledby="inactivityModalLabel" aria-hidden="true" data-bs-backdrop="static" data-bs-keyboard="false">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header bg-warning text-dark">
                    <h5 class="modal-title" id="inactivityModalLabel">تنبيه تسجيل الخروج التلقائي!</h5>
                </div>
                <div class="modal-body">
                    <p>سيتم تسجيل الخروج التلقائي من النظام بسبب الخمول.</p>
                    <p class="fw-bold">سيتم تسجيل الخروج خلال: <span id="countdownDisplay" class="text-danger">15</span> ثواني.</p>
                    <small class="text-muted">الرجاء النقر على أي مكان أو الضغط على أي مفتاح لإلغاء التسجيل.</small>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="historyModal" tabindex="-1" aria-labelledby="historyModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="historyModalLabel">تتبع الإجراءات</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <ul id="historyList" class="list-group"></ul>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/toastr.js/latest/toastr.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/dataTables.bootstrap5.min.js"></script>

    <script>
        const INACTIVITY_TIMEOUT_MS = 30000; // 30 ثانية
        const WARNING_TIMEOUT_MS = 15000;  // 15 ثواني للعد التنازلي

        let inactivityTimer;
        let countdownTimer;
        let countdownValue;
        
        const modalElement = document.getElementById('inactivityModal');
        let inactivityModal = null;
        const isProtectedPage = window.location.pathname.startsWith('/submit_violation');

        if(modalElement && isProtectedPage) {
             inactivityModal = new bootstrap.Modal(modalElement);
             
            function resetInactivityTimer() {
                clearTimeout(inactivityTimer);
                
                if (inactivityModal && document.getElementById('inactivityModal').classList.contains('show')) {
                    inactivityModal.hide();
                    clearInterval(countdownTimer);
                }

                inactivityTimer = setTimeout(showInactivityWarning, INACTIVITY_TIMEOUT_MS);
            }

            function showInactivityWarning() {
                countdownValue = WARNING_TIMEOUT_MS / 1000;
                document.getElementById('countdownDisplay').textContent = countdownValue;
                
                inactivityModal.show();
                
                countdownTimer = setInterval(() => {
                    countdownValue--;
                    document.getElementById('countdownDisplay').textContent = countdownValue;
                    
                    if (countdownValue <= 0) {
                        clearInterval(countdownTimer);
                        autoLogout();
                    }
                }, 1000);
            }

            function autoLogout() {
                window.location.href = '/logout'; 
            }

            ['mousemove', 'mousedown', 'keypress', 'scroll', 'touchstart'].forEach(eventType => {
                document.addEventListener(eventType, resetInactivityTimer, true);
            });
            window.onload = resetInactivityTimer;
        }

        $(document).ready(function() {
            $('#violationsTable').DataTable({
                language: {
                    url: '//cdn.datatables.net/plug-ins/1.11.5/i18n/ar.json'
                },
                columnDefs: [
                    { orderable: false, targets: -1 } // تعطيل الترتيب لعامود الإجراءات
                ]
            });
        });
    </script>
    {{ scripts|safe }}
		<table> <td><tr>----------------------</tr></td></table><table><td><tr>	اعداد/م.مرتضى علي الناصر m.alnasser@tvtc.gov.sa</tr></td></table>
</body>
</html>
'''

LOGIN_BODY = '''
    <h1 class="text-center">دخول المدربين</h1>
    <div class="d-flex justify-content-center gap-2 mb-4">
        <a href="/trainer_register" class="btn btn-warning">تسجيل بياناتي كمدرب جديد</a>
        <a href="/view" class="btn btn-primary">عرض المخالفات</a>
        <a href="/admin_login" class="btn btn-success">إدارة النظام</a>
    </div>
    
    <form method="POST" action="/login" class="bg-white p-4 border rounded shadow-sm mx-auto" style="max-width: 400px;">
        <p class="text-danger text-center fw-bold">⚠️ للدخول: أدخل الرقم الوظيفي وكلمة المرور.</p>
        <p class="text-info text-center small">للمسجلين مسبقاً وليس لديهم كلمة مرور: أدخل الرقم الوظيفي واترك كلمة المرور فارغة لتعيين كلمة مرور جديدة.</p>

        <div class="mb-3">
            <label for="trainer_id" class="form-label fw-bold">الرقم الوظيفي:</label>
            <input type="text" id="trainer_id" name="trainer_id" pattern="[0-9]{5,}" title="أرقام فقط (5 أو أكثر)" required class="form-control">
        </div>
        <div class="mb-3">
            <label for="password" class="form-label fw-bold">كلمة المرور:</label>
            <input type="password" id="password" name="password" class="form-control"> </div>
        <button type="submit" class="btn btn-danger w-100">دخول النظام</button>
        <div class="text-center mt-3">
            <a href="/forgot_password" class="text-muted small">نسيت كلمة المرور؟ (إعادة تفعيل من الإدارة)</a>
        </div>
    </form>
'''

SET_PASSWORD_BODY = '''
    <h1 class="text-center text-warning">تنبيه: تحديث كلمة المرور إلزامي</h1>
    <p class="text-center lead">يرجى تعيين كلمة مرور لحسابك قبل المتابعة في النظام. سيتم تفعيل الدخول بكلمة المرور فقط مستقبلاً.</p>
    
    <form method="POST" action="/set_password" class="bg-white p-4 border rounded shadow-sm mx-auto" style="max-width: 450px;">
        <input type="hidden" name="trainer_id" value="{{ trainer_id }}">
        
        <div class="mb-3">
            <label for="password" class="form-label fw-bold">كلمة المرور الجديدة:</label>
            <input type="password" id="password" name="password" minlength="6" required class="form-control">
        </div>
        <div class="mb-3">
            <label for="confirm_password" class="form-label fw-bold">تأكيد كلمة المرور:</label>
            <input type="password" id="confirm_password" name="confirm_password" minlength="6" required class="form-control">
        </div>
        
        <button type="submit" class="btn btn-success w-100">تعيين كلمة المرور والمتابعة</button>
    </form>
'''

FORGOT_PASSWORD_BODY = '''
    <h1 class="text-center text-danger">نسيت كلمة المرور</h1>
    <p class="text-center lead">لإعادة تعيين كلمة المرور، يرجى إدخال رقمك الوظيفي. سيتم تعطيل حسابك تلقائياً وسيتطلب تفعيلاً من مدير النظام قبل أن تتمكن من تعيين كلمة مرور جديدة.</p>
    
    <form method="POST" action="/forgot_password" class="bg-white p-4 border rounded shadow-sm mx-auto" style="max-width: 450px;">
        <div class="mb-3">
            <label for="trainer_id" class="form-label fw-bold">الرقم الوظيفي:</label>
            <input type="text" id="trainer_id" name="trainer_id" pattern="[0-9]{5,}" title="أرقام فقط (5 أو أكثر)" required class="form-control">
        </div>
        
        <button type="submit" class="btn btn-danger w-100">إعادة تعيين (تعطيل الحساب)</button>
    </form>
    <div class="text-center mt-3">
        <a href="/login" class="btn btn-secondary btn-sm">العودة لصفحة الدخول</a>
    </div>
'''

SUBMIT_FORM_BODY = '''
    <h1>نموذج تسجيل مخالفة متدرب بالكلية</h1>
    <div class="d-flex gap-2 mb-3">
        <span class="badge bg-primary fs-6">مرحبا بك، {{ trainer_name }} ({{ trainer_id }})</span>
        <a href="/view" class="btn btn-info btn-sm">عرض المخالفات</a>
        <a href="/admin_login" class="btn btn-success btn-sm">إدارة النظام</a>
        <a href="/logout" class="btn btn-danger btn-sm">تسجيل خروج</a>
    </div>

    <form method="POST" action="/submit_violation" class="bg-white p-4 border rounded shadow-sm">
        <div class="row g-3">
            <input type="hidden" name="trainer_id" value="{{ trainer_id }}">
            
            <div class="col-md-6">
                <label class="form-label fw-bold">اسم المدرب:</label>
                <input type="text" value="{{ trainer_name }}" readonly class="form-control bg-light">
            </div>
            <div class="col-md-6">
                <label class="form-label fw-bold">القسم التدريبي:</label>
                <input type="hidden" name="department" value="{{ department }}">
                <input type="text" value="{{ department }}" readonly class="form-control bg-light">
            </div>
            
            <div class="col-md-6">
                <label for="course_name" class="form-label fw-bold">اسم المقرر <span class="text-danger">*</span>:</label>
                <input type="text" id="course_name" name="course_name" required class="form-control">
            </div>
            <div class="col-md-6">
                <label for="trainee_id" class="form-label fw-bold">رقم المتدرب <span class="text-danger">*</span>:</label>
                <input type="text" id="trainee_id" name="trainee_id" required class="form-control" oninput="debounceSearchTrainee(this.value)">
            </div>
            <div class="col-md-6">
                <label for="trainee_name" class="form-label fw-bold">اسم المتدرب <span class="text-danger">*</span>:</label>
                <input type="text" id="trainee_name" name="trainee_name" required class="form-control">
            </div>
            <div class="col-md-6">
                <label for="violation_level" class="form-label fw-bold">درجة المخالفة <span class="text-danger">*</span>:</label>
                <select id="violation_level" name="violation_level" required class="form-select">
                    <option value="">اختر الدرجة</option>
                    {% for level in violation_levels %}
                        <option value="{{ level }}">{{ level }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-6">
                <label for="date" class="form-label fw-bold">التاريخ <span class="text-danger">*</span>:</label>
                <input type="date" id="date" name="date" value="{{ today }}" required class="form-control">
            </div>
            <div class="col-md-6">
                <label for="building_number" class="form-label fw-bold">رقم المبنى <span class="text-danger">*</span>:</label>
                <select id="building_number" name="building_number" required class="form-select" onchange="loadRooms(this.value)">
                    <option value="">اختر المبنى</option>
                    {% for building in buildings %}
                        <option value="{{ building }}">{{ building }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-6">
                <label for="room_number" class="form-label fw-bold">رقم القاعة <span class="text-danger">*</span>:</label>
                <select id="room_number" name="room_number" required class="form-select">
                    <option value="">اختر القاعة</option>
                </select>
            </div>
            <div class="col-12">
                <label for="violation_desc" class="form-label fw-bold">وصف المخالفة (مختصر ومفصل) <span class="text-danger">*</span>:</label>
                <textarea id="violation_desc" name="violation_desc" required placeholder="اكتب وصف مختصر للمخالفة مع التفاصيل..." class="form-control" rows="4"></textarea>
            </div>
        </div>
        <button type="submit" class="btn btn-danger mt-4 w-100">تسجيل المخالفة</button>
    </form>
'''

ADMIN_NAV = '''
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">لوحة الإدارة</a>
            <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                <li class="nav-item"><a class="nav-link {% if active_tab == 'trainers' %}active{% endif %}" href="?tab=trainers">إدارة المدربين</a></li>
                <li class="nav-item"><a class="nav-link {% if active_tab == 'departments' %}active{% endif %}" href="?tab=departments">إدارة الأقسام</a></li>
                <li class="nav-item"><a class="nav-link {% if active_tab == 'levels' %}active{% endif %}" href="?tab=levels">إدارة الدرجات</a></li>
                <li class="nav-item"><a class="nav-link {% if active_tab == 'actions' %}active{% endif %}" href="?tab=actions">إدارة الإجراءات</a></li>
                <li class="nav-item"><a class="nav-link {% if active_tab == 'buildings' %}active{% endif %}" href="?tab=buildings">إدارة المباني</a></li>
                <li class="nav-item"><a class="nav-link {% if active_tab == 'rooms' %}active{% endif %}" href="?tab=rooms">إدارة القاعات</a></li>
            </ul>
            <a href="/logout" class="btn btn-outline-light">خروج</a>
        </div>
    </nav>
'''

ADMIN_CRUD_TAB = '''
    <h3>إدارة {{ title }}</h3>
    <form method="POST" action="/admin?tab={{ active_tab }}" class="row g-2 mb-4">
        <input type="hidden" name="action" value="add_{{ action_base }}">
        <div class="col-md-6">
            <input type="text" name="{{ input_name }}" placeholder="اسم/رقم {{ title_singular }} الجديد" required class="form-control">
        </div>
        <div class="col-md-auto">
            <button type="submit" class="btn btn-primary">إضافة {{ title_singular }}</button>
        </div>
    </form>
    <table class="table table-hover">
        <thead>
            <tr><th>{{ title_singular }}</th><th>إجراءات</th></tr>
        </thead>
        <tbody>
            {% for item in items %}
                <tr>
                    <td>{{ item }}</td>
                    <td>
                        <form method="POST" action="/admin?tab={{ active_tab }}" onsubmit="return confirm('حذف هذا العنصر؟');" class="d-inline">
                            <input type="hidden" name="action" value="delete_{{ action_base }}">
                            <input type="hidden" name="{{ input_name }}" value="{{ item }}">
                            <button type="submit" class="btn btn-danger btn-sm">حذف</button>
                        </form>
                    </td>
                </tr>
            {% endfor %}
        </tbody>
    </table>
'''

def hash_password(password):
    if not password:
        return None
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def check_password(stored_hash, provided_password):
    if not stored_hash:
        return False 
    return stored_hash == hash_password(provided_password)

def manage_csv_data(filename, header, item_to_add=None, item_to_remove=None):
    is_newly_created = not os.path.exists(filename)
    
    if is_newly_created:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([header])
    
    items = []
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader) 
            items = [row[0] for row in reader if row]
    except (StopIteration, Exception):
        items = []

    # Handle initial defaults (only if newly created and the list is still empty)
    if is_newly_created and not items:
        default_map = {
            'القسم': ['هندسة', 'إدارة'], 
            'الدرجة': ['أولى', 'ثانية'], 
            'رقم المبنى': ['A', 'B'],
            'الإجراء المتخذ': ['إنذار شفهي', 'إنذار خطي', 'خصم مكافأة فصل', 'إلغاء تسجيل مقرر'] # الإجراءات الافتراضية الجديدة
        }
        defaults = default_map.get(header, [])
        if defaults:
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for item in defaults:
                    writer.writerow([item])
                    items.append(item)
    
    if item_to_add and item_to_add not in items:
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([item_to_add])
        items.append(item_to_add)
    
    if item_to_remove and item_to_remove in items:
        items = [item for item in items if item != item_to_remove]
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([header])
            for item in items:
                writer.writerow([item])
    
    return items

def get_departments(): 
    return manage_csv_data(DEPARTMENTS_FILE, 'القسم')

def get_violation_levels(): 
    return manage_csv_data(VIOLATION_LEVELS_FILE, 'الدرجة')

def get_buildings(): 
    return manage_csv_data(BUILDINGS_FILE, 'رقم المبنى')

def get_actions(): 
    return manage_csv_data(ACTIONS_FILE, 'الإجراء المتخذ')

def ensure_trainers_file():
    if not os.path.exists(TRAINERS_FILE):
        with open(TRAINERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

def get_trainer_by_id(trainer_id):
    ensure_trainers_file()
    with open(TRAINERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f).get(trainer_id, None)

def get_all_trainers():
    ensure_trainers_file()
    with open(TRAINERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_trainer_data(trainer_id, updates):
    trainers = get_all_trainers()
    if trainer_id in trainers:
        if 'password' in updates and updates['password'] is not None:
             updates['password'] = hash_password(updates['password'])
        elif 'password' in updates and updates['password'] is None:
             trainers[trainer_id].pop('password', None)
             updates.pop('password')
        
        trainers[trainer_id].update(updates)
        with open(TRAINERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(trainers, f, ensure_ascii=False, indent=4)
        return True
    return False

def add_trainer(trainer_id, trainer_name, department, password):
    trainers = get_all_trainers()
    trainers[trainer_id] = {
        'name': trainer_name, 
        'department': department, 
        'status': 'inactive',
        'role': 'مدرب',
        'password': hash_password(password)
    }
    with open(TRAINERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(trainers, f, ensure_ascii=False, indent=4)

def ensure_csv_header(file):
    if not os.path.exists(file):
        with open(file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if file == CSV_FILE:
                writer.writerow(['التاريخ', 'رقم الوظيفي', 'القسم التدريبي', 'اسم المقرر', 'رقم المتدرب', 'اسم المتدرب', 'وصف المخالفة', 'درجة المخالفة', 'رقم المبنى', 'رقم القاعة', 'حالة المخالفة', 'الإجراء المتخذ'])
            elif file == ROOMS_FILE:
                writer.writerow(['رقم القاعة', 'رقم المبنى'])
            elif file == VIOLATION_LOGS_FILE:
                writer.writerow(['violation_index', 'timestamp', 'actor_role', 'actor_name', 'action_taken', 'notes'])

def get_rooms(building=None):
    ensure_csv_header(ROOMS_FILE)
    rooms = []
    with open(ROOMS_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try: next(reader)
        except StopIteration: pass
        for row in reader:
            if len(row) == 2:
                room_data = {'room_number': row[0], 'building_number': row[1]}
                if not building or room_data['building_number'] == building:
                    rooms.append(room_data)
    return rooms

def add_room(room_number, building_number):
    if not any(r['room_number'] == room_number and r['building_number'] == building_number for r in get_rooms()):
        with open(ROOMS_FILE, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([room_number, building_number])

def delete_room(room_number, building_number):
    new_rooms = [r for r in get_rooms() if not (r['room_number'] == room_number and r['building_number'] == building_number)]
    with open(ROOMS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['رقم القاعة', 'رقم المبنى'])
        for room in new_rooms:
            writer.writerow([room['room_number'], room['building_number']])

def get_viewer_context(viewer_id=None):
    if session.get('admin'):
        return {'role': 'مدير نظام', 'department': None, 'trainer_id': None, 'is_admin_session': True}
        
    if viewer_id:
        trainer_data = get_trainer_by_id(viewer_id)
        if trainer_data and trainer_data.get('status') == 'active':
            return {
                'role': trainer_data.get('role', 'مدرب'),
                'department': trainer_data.get('department'),
                'trainer_id': viewer_id,
                'is_admin_session': False
            }
    
    return {'role': 'guest', 'department': None, 'trainer_id': None, 'is_admin_session': False}

def read_violations_with_index():
    ensure_csv_header(CSV_FILE)
    violations = []
    try:
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            violations = list(reader)
            for i, v in enumerate(violations):
                v['index'] = i + 1 
    except Exception as e:
        print(f'Error reading violations: {e}')
    return violations

def update_violation_by_index(index, updates):
    all_violations = read_violations_with_index()
    violation_to_update = next((v for v in all_violations if v['index'] == index), None)
    
    if violation_to_update:
        for key, value in updates.items():
            if key in violation_to_update:
                violation_to_update[key] = value

        headers = ['التاريخ', 'رقم الوظيفي', 'القسم التدريبي', 'اسم المقرر', 'رقم المتدرب', 'اسم المتدرب', 'وصف المخالفة', 'درجة المخالفة', 'رقم المبنى', 'رقم القاعة', 'حالة المخالفة', 'الإجراء المتخذ']
        
        violations_to_write = [{k: v for k, v in violation.items() if k != 'index'} for violation in all_violations]

        try:
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(violations_to_write)
            return True
        except Exception as e:
            print(f'Error writing violations: {e}')
            return False
            
    return False

def log_violation_action(violation_index, actor_role, actor_name, action_taken, notes):
    ensure_csv_header(VIOLATION_LOGS_FILE)
    timestamp = datetime.now().isoformat()
    with open(VIOLATION_LOGS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([violation_index, timestamp, actor_role, actor_name, action_taken, notes])

def get_violation_history(violation_index):
    ensure_csv_header(VIOLATION_LOGS_FILE)
    history = []
    with open(VIOLATION_LOGS_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['violation_index'] == str(violation_index):
                history.append(row)
    history.sort(key=lambda x: x['timestamp'])  # Sort ascending (oldest to newest)
    return history

@app.before_request
def check_session_timeout():
    if 'logged_in_trainer_id' in session and session.get('last_activity'):
        last_activity = datetime.fromisoformat(session['last_activity'])
        if datetime.now() - last_activity > timedelta(minutes=30):
            session.pop('logged_in_trainer_id', None)
            flash('تم تسجيل الخروج بسبب الخمول.', 'warning')
            return redirect(url_for('login'))
    session['last_activity'] = datetime.now().isoformat()

@app.route('/')
def index():
    if session.get('logged_in_trainer_id'):
        trainer_id = session['logged_in_trainer_id']
        trainer_data = get_trainer_by_id(trainer_id)
        if trainer_data and trainer_data.get('password'):
            return redirect(url_for('submit_violation'))
        else:
            return redirect(url_for('set_password'))
    
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in_trainer_id'):
         return redirect(url_for('index'))
         
    if request.method == 'POST':
        trainer_id = request.form['trainer_id']
        password = request.form.get('password', '') 
        trainer_data = get_trainer_by_id(trainer_id)
        
        if not trainer_data:
            flash('خطأ: الرقم الوظيفي غير مسجل.', 'error')
            return redirect(url_for('login'))
        
        # 1. التحقق من التفعيل
        if trainer_data.get('status') != 'active':
            flash('فشل الدخول: حسابك غير مفعل. يرجى التواصل مع الإدارة للتفعيل.', 'error')
            return redirect(url_for('login'))
            
        # 2. التحقق من كلمة المرور (للمستخدمين ذوي كلمة المرور المسجلة أو الجديدة)
        if trainer_data.get('password'):
            if check_password(trainer_data['password'], password):
                session['logged_in_trainer_id'] = trainer_id
                return redirect(url_for('submit_violation'))
            else:
                flash('خطأ: كلمة المرور غير صحيحة.', 'error')
                return redirect(url_for('login'))
        
        # 3. معالجة المستخدمين القدامى (Legacy Users - لا يوجد حقل كلمة مرور مسجل)
        else:
            if not password:
                flash('تنبيه: يجب عليك تعيين كلمة مرور لحسابك للمتابعة.', 'warning')
                session['logged_in_trainer_id'] = trainer_id
                return redirect(url_for('set_password'))
            else:
                 flash('خطأ: حسابك لا يحتوي على كلمة مرور. يرجى ترك حقل كلمة المرور فارغاً لتعيين واحدة جديدة.', 'error')
                 return redirect(url_for('login'))

    return render_template_string(BASE_TEMPLATE, title="دخول المدربين", content=LOGIN_BODY)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        trainer_id = request.form['trainer_id']
        trainer_data = get_trainer_by_id(trainer_id)
        
        if not trainer_data:
            flash('خطأ: الرقم الوظيفي غير مسجل.', 'error')
            return redirect(url_for('forgot_password'))
            
        updates = {
            'password': None, # مسح كلمة المرور
            'status': 'inactive' # تعطيل الحساب
        }
        
        if update_trainer_data(trainer_id, updates):
            flash(f'تم مسح كلمة المرور لحساب {trainer_id} وتعطيله بنجاح. يرجى الانتظار حتى يتم تفعيل حسابك من قبل مدير النظام لتتمكن من تعيين كلمة مرور جديدة عند الدخول.', 'danger')
            return redirect(url_for('login'))
        else:
            flash('حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.', 'error')
            return redirect(url_for('forgot_password'))

    return render_template_string(BASE_TEMPLATE, title="نسيت كلمة المرور", content=FORGOT_PASSWORD_BODY)

@app.route('/set_password', methods=['GET', 'POST'])
def set_password():
    trainer_id = session.get('logged_in_trainer_id')
    trainer_data = get_trainer_by_id(trainer_id)
    
    if not trainer_id or not trainer_data:
        flash('خطأ: يجب تسجيل الدخول بالرقم الوظيفي أولاً.', 'error')
        return redirect(url_for('login'))
        
    if trainer_data.get('password'):
        return redirect(url_for('submit_violation'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('خطأ: كلمتا المرور غير متطابقتين.', 'error')
            return redirect(url_for('set_password'))
        
        if len(new_password) < 6:
             flash('خطأ: يجب أن لا تقل كلمة المرور عن 6 أحرف/أرقام.', 'error')
             return redirect(url_for('set_password'))
        
        if update_trainer_data(trainer_id, {'password': new_password}):
            flash('تم تعيين كلمة المرور بنجاح! يمكنك الآن المتابعة.', 'success')
            return redirect(url_for('submit_violation'))
        else:
            flash('خطأ غير متوقع أثناء تحديث البيانات.', 'error')
            return redirect(url_for('set_password'))

    return render_template_string(BASE_TEMPLATE, 
                                 title="تعيين كلمة مرور", 
                                 content=render_template_string(SET_PASSWORD_BODY, trainer_id=trainer_id))

@app.route('/submit_violation', methods=['GET', 'POST'])
def submit_violation():
    trainer_id = session.get('logged_in_trainer_id')
    trainer_data = get_trainer_by_id(trainer_id)
    
    if not trainer_id or not trainer_data or not trainer_data.get('password'):
        flash('يجب تسجيل الدخول بكلمة المرور للمتابعة.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # الحقول الأصلية
        fields = ['date', 'trainer_id', 'department', 'course_name', 'trainee_id', 'trainee_name', 'violation_desc', 'violation_level', 'building_number', 'room_number']
        data = [request.form.get(f) for f in fields]
        
        # إضافة الحقول الجديدة (الافتراضية)
        data.extend(['جديدة', 'لا يوجد']) 
        
        ensure_csv_header(CSV_FILE)
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(data)

        flash('تم تسجيل المخالفة بنجاح!', 'success')
        return redirect(url_for('submit_violation'))

    form_html = render_template_string(SUBMIT_FORM_BODY,
                                       today=date.today().isoformat(),
                                       trainer_id=trainer_id,
                                       trainer_name=trainer_data['name'],
                                       department=trainer_data['department'],
                                       violation_levels=get_violation_levels(), 
                                       buildings=get_buildings())
    script_content = '''
        <script>
            let debounceTimer2;
            function debounceSearchTrainee(traineeId) {
                clearTimeout(debounceTimer2);
                debounceTimer2 = setTimeout(() => {
                    if (traineeId.length >= 3) {
                        fetch('/search/' + encodeURIComponent(traineeId))
                            .then(response => response.json())
                            .then(data => {
                                document.getElementById('trainee_name').value = data.name || '';
                            });
                    } else { document.getElementById('trainee_name').value = ''; }
                }, 300);
            }
            
            function loadRooms(building) {
                const select = document.getElementById('room_number');
                select.innerHTML = '<option value="">اختر القاعة</option>';
                if (!building) return;
                fetch('/get_rooms/' + encodeURIComponent(building))
                    .then(response => response.json())
                    .then(data => {
                        data.rooms.forEach(room => {
                            select.innerHTML += `<option value="${room}">${room}</option>`;
                        });
                    });
            }
        </script>
    '''
    
    return render_template_string(BASE_TEMPLATE, 
                                 title="نموذج تسجيل مخالفة", 
                                 content=form_html, 
                                 scripts=script_content)

@app.route('/trainer_register', methods=['GET', 'POST'])
def trainer_register():
    if request.method == 'POST':
        trainer_id = request.form['trainer_id']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if not re.match(r'^[0-9]{5,}$', trainer_id):
            flash('الرقم الوظيفي يجب أن يكون أرقام فقط (5 أو أكثر)!', 'error')
        elif get_trainer_by_id(trainer_id):
            flash('رقم وظيفي موجود بالفعل! يرجى التواصل مع الإدارة للتفعيل أو محاولة الدخول.', 'error')
        elif password != confirm_password:
            flash('كلمتا المرور غير متطابقتين!', 'error')
        elif len(password) < 6:
            flash('كلمة المرور يجب أن لا تقل عن 6 أحرف/أرقام.', 'error')
        else:
            add_trainer(trainer_id, request.form['trainer_name'], request.form['department'], password)
            flash('تم حفظ بياناتك بنجاح! سيتم تفعيل حسابك من قبل مدير النظام لتتمكن من الدخول.', 'success')
            return redirect(url_for('login'))

    content = f'''
        <h1>تسجيل بيانات المدرب الذاتي</h1>
        <p class="text-danger fw-bold">⚠️ يجب تفعيل حسابك من قبل الإدارة بعد التسجيل لتتمكن من الدخول.</p>
        <form method="POST" action="" class="bg-white p-4 border rounded shadow-sm">
            <label for="trainer_id" class="form-label fw-bold">الرقم الوظيفي:</label>
            <input type="text" id="trainer_id" name="trainer_id" pattern="[0-9]{{5,}}" required class="form-control mb-3">
            <label for="trainer_name" class="form-label fw-bold">الاسم الكامل:</label>
            <input type="text" id="trainer_name" name="trainer_name" required class="form-control mb-3">
            <label for="department" class="form-label fw-bold">القسم التدريبي:</label>
            <select id="department" name="department" required class="form-select mb-3">
                <option value="">اختر القسم</option>
                {''.join([f'<option value="{d}">{d}</option>' for d in get_departments()])}
            </select>
            <label for="password" class="form-label fw-bold">كلمة المرور (6 أحرف/أرقام على الأقل):</label>
            <input type="password" id="password" name="password" minlength="6" required class="form-control mb-3">
            <label for="confirm_password" class="form-label fw-bold">تأكيد كلمة المرور:</label>
            <input type="password" id="confirm_password" name="confirm_password" minlength="6" required class="form-control mb-3">
            <button type="submit" class="btn btn-warning w-100">تسجيل</button>
            <div class="text-center mt-3">
                <a href="/login" class="btn btn-secondary btn-sm">العودة لصفحة الدخول</a>
            </div>
        </form>
    '''
    return render_template_string(BASE_TEMPLATE, title="تسجيل مدرب جديد", content=content)

@app.route('/logout')
def logout():
    session.pop('logged_in_trainer_id', None)
    session.pop('admin', None)
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('login'))

@app.route('/process_violation/<int:index>', methods=['GET', 'POST'])
def process_violation(index):
    trainer_id = session.get('logged_in_trainer_id')
    trainer_data = get_trainer_by_id(trainer_id)
    
    if not trainer_id or not trainer_data:
        flash('يجب تسجيل الدخول.', 'error')
        return redirect(url_for('view'))
        
    role = trainer_data.get('role')
    authorized_roles = ['رئيس قسم', 'وكيل شؤون متدربين', 'عميد']

    if role not in authorized_roles:
        flash('ليس لديك الصلاحية لمعالجة المخالفات.', 'error')
        return redirect(url_for('view'))
        
    all_violations = read_violations_with_index()
    violation = next((v for v in all_violations if v['index'] == index), None)

    if not violation:
        flash('خطأ: لم يتم العثور على المخالفة المطلوبة.', 'error')
        return redirect(url_for('view'))

    viewer_department = trainer_data.get('department')
    current_status = violation.get('حالة المخالفة')
    
    if role == 'رئيس قسم' and violation.get('القسم التدريبي') != viewer_department:
        flash('ليس لديك الصلاحية لمعالجة مخالفات هذا القسم.', 'error')
        return redirect(url_for('view'))
            
    if current_status == 'تم اتخاذ إجراء':
        flash('تم اتخاذ إجراء نهائي على هذه المخالفة ولا يمكن تعديلها.', 'danger')
        return redirect(url_for('view'))
    
    if current_status == 'محولة للوكيل' and role == 'رئيس قسم':
        flash('تم تحويل هذه المخالفة بالفعل لوكيل شؤون المتدربين ولا يمكن لرئيس القسم تعديلها.', 'danger')
        return redirect(url_for('view'))
            
    if request.method == 'POST':
        action_taken = request.form['action_taken']
        notes = request.form.get('notes', '')
        
        if action_taken == 'محولة للوكيل' and role == 'رئيس قسم':
            new_status = 'محولة للوكيل'
        elif action_taken == 'محولة للوكيل' and role != 'رئيس قسم':
            flash('خطأ في الإجراء: الوكيل/العميد لا يمكنه التحويل، يجب اختيار إجراء نهائي.', 'error')
            return redirect(url_for('process_violation', index=index))
        else:
            new_status = 'تم اتخاذ إجراء'
            
        updates = {
            'حالة المخالفة': new_status,
            'الإجراء المتخذ': f'{action_taken} (من قبل {role}: {trainer_data["name"]} بتاريخ {date.today().isoformat()}). ملاحظات: {notes}' 
        }
        
        if update_violation_by_index(index, updates):
            log_violation_action(index, role, trainer_data['name'], action_taken, notes)
            flash(f'تم تحديث حالة المخالفة رقم {index} إلى: {new_status} بنجاح.', 'success')
            return redirect(url_for('view'))
        else:
            flash('خطأ أثناء تحديث المخالفة.', 'error')
            return redirect(url_for('process_violation', index=index))

    actions = get_actions()
    
    transfer_option = ''
    if role == 'رئيس قسم':
        transfer_option = '<option value="محولة للوكيل" class="fw-bold text-danger">تحويل لوكيل شؤون المتدربين</option>'
        
    process_form = f'''
        <h1 class="text-center">معالجة المخالفة رقم {index}</h1>
        <p class="lead"><strong>المتدرب:</strong> {violation.get('اسم المتدرب')} ({violation.get('رقم المتدرب')})</p>
        <p><strong>القسم:</strong> {violation.get('القسم التدريبي')} | <strong>درجة المخالفة:</strong> {violation.get('درجة المخالفة')}</p>
        <p><strong>وصف المخالفة:</strong> {violation.get('وصف المخالفة')}</p>
        <p class="text-danger fw-bold">الرجاء اختيار الإجراء المناسب لهذه المخالفة (بصفتك: {role}):</p>
        
        <form method="POST" action="/process_violation/{index}" class="bg-light p-4 border rounded shadow-sm mx-auto" style="max-width: 600px;">
            <div class="mb-3">
                <label for="action_taken" class="form-label fw-bold">الإجراء/الحالة الجديدة:</label>
                <select id="action_taken" name="action_taken" required class="form-select">
                    <option value="">اختر الإجراء المتخذ</option>
                    <optgroup label="الإجراءات الإدارية">
                        {''.join([f'<option value="{a}">{a}</option>' for a in actions])}
                    </optgroup>
                    {transfer_option}
                </select>
            </div>
            <div class="mb-3">
                <label for="notes" class="form-label">ملاحظات {role} (اختياري):</label>
                <textarea id="notes" name="notes" class="form-control" rows="3" placeholder="ملاحظات حول الإجراء المتخذ أو سبب التحويل..."></textarea>
            </div>
            <button type="submit" class="btn btn-danger w-100">تطبيق الإجراء</button>
        </form>
        <div class="text-center mt-3">
            <a href="/view" class="btn btn-secondary btn-sm">العودة لصفحة العرض</a>
        </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, title=f"معالجة مخالفة {index}", content=process_form)

@app.route('/view', methods=['GET'])
def view():
    session_trainer_id = session.get('logged_in_trainer_id')
    viewer_id_param = request.args.get('viewer_id')
    viewer_id_for_context = session_trainer_id or viewer_id_param

    if not viewer_id_for_context and not session.get('admin'):
        login_form = '''
            <h2 class="text-center">عرض المخالفات - تسجيل الدخول</h2>
            <p class="text-center text-danger">يرجى إدخال رقمك الوظيفي لتحديد صلاحية العرض. (أو قم بتسجيل الدخول الكامل عبر زر "إضافة مخالفة جديدة")</p>
            <form method="GET" action="/view" class="bg-light p-4 border rounded shadow-sm mx-auto" style="max-width:400px;">
                <label for="viewer_id" class="form-label fw-bold">الرقم الوظيفي:</label>
                <input type="text" name="viewer_id" id="viewer_id" pattern="[0-9]{5,}" placeholder="الرقم الوظيفي (5 أرقام أو أكثر)" required class="form-control mb-3">
                <button type="submit" class="btn btn-info w-100">دخول للعرض</button>
            </form>
            <div class="text-center mt-3 d-flex justify-content-center gap-3">
                <a href="/login" class="btn btn-primary btn-sm">إضافة مخالفة جديدة (دخول المدربين)</a>
                <a href="/trainer_register" class="btn btn-warning btn-sm">تسجيل مدرب جديد</a>
            </div>
        ''' 
        return render_template_string(BASE_TEMPLATE, title="تسجيل الدخول للعرض", content=login_form)

    viewer_context = get_viewer_context(viewer_id_for_context)
    role = viewer_context['role']
    viewer_department = viewer_context['department']
    current_trainer_id = viewer_context['trainer_id']

    if role == 'guest' and not session.get('admin'):
        flash('فشل الدخول للعرض: الرقم الوظيفي غير مسجل أو غير مفعل.', 'error')
        return redirect(url_for('view')) 
        
    violations = read_violations_with_index()

    filtered_violations = []
    forwarded_filter = request.args.get('forwarded_to_dean')
    
    if role == 'مدرب':
        filtered_violations = [v for v in violations if v['رقم الوظيفي'] == current_trainer_id]
    elif role == 'رئيس قسم':
        filtered_violations = [v for v in violations if v['القسم التدريبي'] == viewer_department]
    elif role in ['وكيل شؤون متدربين', 'وكيل جودة', 'عميد', 'مدير نظام']:
        
        if role == 'وكيل شؤون متدربين' and forwarded_filter == 'yes':
             filtered_violations = [v for v in violations if v.get('حالة المخالفة') == 'محولة للوكيل']
        else:
             filtered_violations = violations
    else:
        filtered_violations = []

    search_query = request.args.get('search', '').strip()
    department_filter = request.args.get('department_filter')
    trainer_filter = request.args.get('trainer_filter')
    
    final_violations = filtered_violations
    
    is_admin_view = role in ['وكيل شؤون متدربين', 'وكيل جودة', 'عميد', 'مدير نظام']
    if is_admin_view:
        if department_filter:
            final_violations = [v for v in final_violations if v['القسم التدريبي'] == department_filter]
        
        if trainer_filter:
            final_violations = [v for v in final_violations if v['رقم الوظيفي'] == trainer_filter]
    
    if search_query:
        final_violations = [
            v for v in final_violations 
            if search_query in v['رقم المتدرب'] or search_query in v['اسم المتدرب'] or search_query in v['وصف المخالفة']
        ]
            
    final_violations.reverse()
    
    headers = ['التاريخ', 'رقم المتدرب', 'اسم المتدرب', 'القسم التدريبي', 'درجة المخالفة', 'وصف المخالفة', 'حالة المخالفة', 'الإجراء المتخذ', 'المدرب/إجراءات']
    
    all_departments = get_departments()
    all_trainers_ids = list(get_all_trainers().keys())
    
    dean_forwarded_button = ''
    if role == 'وكيل شؤون متدربين':
        total_forwarded = sum(1 for v in violations if v.get('حالة المخالفة') == 'محولة للوكيل')
        if forwarded_filter == 'yes':
            dean_forwarded_button = f'<a href="{url_for("view", viewer_id=viewer_id_param if viewer_id_param and not session_trainer_id else None)}" class="btn btn-warning btn-sm">عرض كل المخالفات</a>'
        else:
            dean_forwarded_button = f'<a href="{url_for("view", forwarded_to_dean="yes", viewer_id=viewer_id_param if viewer_id_param and not session_trainer_id else None)}" class="btn btn-danger btn-sm">عرض المحولة للوكيل فقط ({total_forwarded})</a>'

    
    hidden_viewer_id_input = ''
    if viewer_id_param and not session_trainer_id:
        hidden_viewer_id_input = f'<input type="hidden" name="viewer_id" value="{viewer_id_param}">'

    view_content = f'''
        <h1 class="text-center mb-4">عرض المخالفات المسجلة ({role})</h1>
        
        <div class="d-flex justify-content-between align-items-center mb-3">
            <span class="badge bg-primary fs-6">الرقم الوظيفي الحالي: {current_trainer_id or 'مدير نظام'}</span>
            <div class="d-flex gap-2">
                {dean_forwarded_button}
                <a href="/submit_violation" class="btn btn-danger btn-sm">إضافة مخالفة</a>
                <a href="/logout" class="btn btn-secondary btn-sm">تسجيل خروج</a>
            </div>
        </div>

        <form method="GET" action="/view" class="bg-light p-3 border rounded shadow-sm mb-4">
            {hidden_viewer_id_input}
            <input type="hidden" name="forwarded_to_dean" value="{forwarded_filter or ''}">
            <div class="row g-2">
                <div class="col-md-6">
                    <input type="text" name="search" placeholder="بحث برقم/اسم المتدرب أو الوصف" class="form-control" value="{search_query}">
                </div>
                {'<div class="col-md-3">' if is_admin_view else '<div class="col-md-6">'}
                    <button type="submit" class="btn btn-success w-100">تطبيق البحث/التصفية</button>
                </div>
                
                {''.join([f'''
                <div class="col-md-3">
                    <select name="{name}_filter" class="form-select">
                        <option value="">تصفية حسب {label}</option>
                        {''.join([f'<option value="{item}" {"selected" if locals().get(f"{name}_filter") == item else ""}>{item}</option>' for item in items])}
                    </select>
                </div>
                ''' for name, label, items in [
                    ('department', 'القسم', all_departments),
                    ('trainer', 'رقم المدرب', all_trainers_ids)
                ] if is_admin_view])}

            </div>
        </form>

        <p class="lead">عدد المخالفات المعروضة: <strong>{len(final_violations)}</strong></p>
        
        <div class="table-responsive">
            <table id="violationsTable" class="table table-striped table-bordered table-hover">
                <thead class="table-dark">
                    <tr>{''.join([f'<th>{h}</th>' for h in headers])}</tr>
                </thead>
                <tbody>
                    {
                        ''.join([
                            f'''<tr>
                                <td>{v.get('التاريخ', 'N/A')}</td>
                                <td>{v.get('رقم المتدرب', 'N/A')}</td>
                                <td>{v.get('اسم المتدرب', 'N/A')}</td>
                                <td>{v.get('القسم التدريبي', 'N/A')}</td>
                                <td>{v.get('درجة المخالفة', 'N/A')}</td>
                                <td>{v.get('وصف المخالفة', 'N/A')}</td>
                                <td class="fw-bold text-{'danger' if v.get('حالة المخالفة') == 'محولة للوكيل' else 'success' if v.get('حالة المخالفة') == 'تم اتخاذ إجراء' else 'info'}">{v.get('حالة المخالفة', 'N/A')}</td>
                                <td>{v.get('الإجراء المتخذ', 'N/A')}</td>
                                <td class="table-action-cell">
                                    {v.get('رقم الوظيفي', 'N/A')}
                                    { (lambda role, v, viewer_department:
                                        (
                                            f'<hr class="my-1"><a href="{url_for("process_violation", index=v["index"])}" class="btn btn-sm btn-warning w-100">اتخاذ إجراء</a>'
                                            if (
                                                role in ['رئيس قسم', 'وكيل شؤون متدربين', 'عميد'] and v.get('حالة المخالفة') != 'تم اتخاذ إجراء' and (
                                                    (role == 'رئيس قسم' and v.get('القسم التدريبي') == viewer_department and v.get('حالة المخالفة') != 'محولة للوكيل') or 
                                                    (role in ['وكيل شؤون متدربين', 'عميد'])
                                                )
                                            )
                                            else ''
                                        )
                                    )(role, v, viewer_department) }
                                    <hr class="my-1"><button class="btn btn-info btn-sm w-100" onclick="showHistory({v['index']})">📋 تتبّع الإجراءات</button>
                                </td>
                            </tr>'''
                            for v in final_violations
                        ])
                    }
                </tbody>
            </table>
        </div>
    '''
    
    history_script = '''
    <script>
        function showHistory(index) {
            fetch(`/get_violation_history/${index}`)
                .then(response => response.json())
                .then(data => {
                    const historyList = document.getElementById('historyList');
                    historyList.innerHTML = '';
                    if (data.length === 0) {
                        historyList.innerHTML = '<li class="list-group-item">لا يوجد سجل إجراءات لهذه المخالفة.</li>';
                    } else {
                        data.forEach(entry => {
                            const item = document.createElement('li');
                            item.classList.add('list-group-item');
                            item.innerHTML = `
                                <strong>التاريخ والوقت:</strong> ${entry.timestamp}<br>
                                <strong>الدور:</strong> ${entry.actor_role}<br>
                                <strong>الاسم:</strong> ${entry.actor_name}<br>
                                <strong>الإجراء:</strong> ${entry.action_taken}<br>
                                <strong>الملاحظات:</strong> ${entry.notes || 'لا يوجد'}
                            `;
                            historyList.appendChild(item);
                        });
                    }
                    const historyModal = new bootstrap.Modal(document.getElementById('historyModal'));
                    historyModal.show();
                })
                .catch(error => console.error('Error:', error));
        }
    </script>
    '''
    
    return render_template_string(BASE_TEMPLATE, title="عرض المخالفات", content=view_content, scripts=history_script)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['admin'] = True
            flash('تم تسجيل دخول المدير بنجاح.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('كلمة مرور المدير غير صحيحة.', 'error')
            return redirect(url_for('admin_login'))
            
    content = '''
        <h1 class="text-center">دخول مدير النظام</h1>
        <form method="POST" action="/admin_login" class="bg-white p-4 border rounded shadow-sm mx-auto" style="max-width: 400px;">
            <div class="mb-3">
                <label for="password" class="form-label fw-bold">كلمة المرور الإدارية:</label>
                <input type="password" id="password" name="password" required class="form-control">
            </div>
            <button type="submit" class="btn btn-success w-100">دخول كمدير</button>
            <div class="text-center mt-3">
                <a href="/login" class="btn btn-secondary btn-sm">العودة لصفحة الدخول</a>
            </div>
        </form>
    '''
    return render_template_string(BASE_TEMPLATE, title="دخول المدير", content=content)

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin'):
        flash('يجب تسجيل الدخول كمدير نظام.', 'error')
        return redirect(url_for('admin_login'))

    active_tab = request.args.get('tab', 'trainers')
    content = ''

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_trainer':
            trainer_id = request.form['trainer_id']
            updates = {
                'name': request.form['name'],
                'department': request.form['department'],
                'role': request.form['role'],
                'status': request.form['status']
            }
            if update_trainer_data(trainer_id, updates):
                flash(f'تم تحديث بيانات المدرب {trainer_id} بنجاح.', 'success')
            else:
                flash(f'خطأ: لم يتم العثور على المدرب {trainer_id}.', 'error')
            return redirect(url_for('admin_dashboard', tab='trainers'))
            
        elif action == 'reset_password':
            trainer_id = request.form['trainer_id']
            updates = {'password': None, 'status': 'active'} 
            if update_trainer_data(trainer_id, updates):
                flash(f'تم إعادة تعيين كلمة مرور المدرب {trainer_id}. سيطلب منه تعيين كلمة مرور جديدة عند الدخول.', 'warning')
            else:
                flash(f'خطأ في إعادة تعيين كلمة المرور للمدرب {trainer_id}.', 'error')
            return redirect(url_for('admin_dashboard', tab='trainers'))
            
        elif action.startswith('add_') or action.startswith('delete_'):
            
            parts = action.split('_')
            op = parts[0]
            base = parts[-1]
            
            input_map = {'departments': 'department', 'levels': 'level', 'actions': 'action', 'buildings': 'building', 'rooms': 'room'}
            header_map = {'departments': 'القسم', 'levels': 'الدرجة', 'actions': 'الإجراء المتخذ', 'buildings': 'رقم المبنى'}
            file_to_use_map = {'departments': DEPARTMENTS_FILE, 'levels': VIOLATION_LEVELS_FILE, 'actions': ACTIONS_FILE, 'buildings': BUILDINGS_FILE}
            
            input_name = input_map.get(base)
            item_value = request.form.get(input_name, '').strip()

            if base == 'rooms':
                building_number = request.form.get('building_number')
                if op == 'add' and item_value and building_number:
                    add_room(item_value, building_number)
                    flash(f'تم إضافة القاعة {item_value} للمبنى {building_number} بنجاح.', 'success')
                elif op == 'delete' and item_value and building_number:
                    delete_room(item_value, building_number)
                    flash(f'تم حذف القاعة {item_value} من المبنى {building_number} بنجاح.', 'danger')
            elif item_value:
                file_to_use = file_to_use_map.get(base)
                header = header_map.get(base)
                
                if op == 'add':
                    manage_csv_data(file_to_use, header, item_to_add=item_value)
                    flash(f'تم إضافة {item_value} بنجاح.', 'success')
                elif op == 'delete':
                    manage_csv_data(file_to_use, header, item_to_remove=item_value)
                    flash(f'تم حذف {item_value} بنجاح.', 'danger')
            return redirect(url_for('admin_dashboard', tab=active_tab))


    if active_tab == 'trainers':
        trainers = get_all_trainers()
        departments = get_departments()
        
        trainers_table = f'''
            <h3>إدارة المدربين ({len(trainers)} مدرب)</h3>
            <p class="text-info small">يمكن لمدير النظام تفعيل الحسابات المعطلة أو إعادة تعيين كلمة المرور (تتطلب تعيين كلمة جديدة عند الدخول).</p>
            <div class="table-responsive">
                <table class="table table-striped table-hover">
                    <thead class="table-dark">
                        <tr><th>ID</th><th>الاسم</th><th>القسم</th><th>الدور</th><th>الحالة</th><th>إجراءات</th></tr>
                    </thead>
                    <tbody>
                        {''.join([f'''
                        <tr>
                            <form method="POST" action="/admin?tab=trainers" class="d-inline-block">
                                <input type="hidden" name="action" value="update_trainer">
                                <input type="hidden" name="trainer_id" value="{id}">
                                <td>{id}</td>
                                <td><input type="text" name="name" value="{data['name']}" required class="form-control form-control-sm"></td>
                                <td>
                                    <select name="department" required class="form-select form-select-sm">
                                        {''.join([f'<option value="{d}" {"selected" if d == data["department"] else ""}>{d}</option>' for d in departments])}
                                    </select>
                                </td>
                                <td>
                                    <select name="role" required class="form-select form-select-sm">
                                        {''.join([f'<option value="{r}" {"selected" if r == data.get("role", "مدرب") else ""}>{r}</option>' for r in ROLES])}
                                    </select>
                                </td>
                                <td>
                                    <select name="status" required class="form-select form-select-sm {'bg-success text-white' if data.get("status") == "active" else 'bg-danger text-white'}">
                                        <option value="active" {"selected" if data.get("status") == "active" else ""}>مفعل</option>
                                        <option value="inactive" {"selected" if data.get("status") == "inactive" else ""}>معطل</option>
                                    </select>
                                </td>
                                <td class="d-flex gap-1">
                                    <button type="submit" class="btn btn-primary btn-sm">حفظ</button>
                                    <button type="submit" name="action" value="reset_password" class="btn btn-warning btn-sm" onclick="return confirm('إعادة تعيين كلمة مرور المدرب {id}؟');">إعادة تعيين PW</button>
                                </td>
                            </form>
                        </tr>
                        ''' for id, data in trainers.items()])}
                    </tbody>
                </table>
            </div>
        '''
        content = trainers_table
    
    elif active_tab == 'departments':
        content = render_template_string(ADMIN_CRUD_TAB, 
                                         active_tab=active_tab, 
                                         title="الأقسام التدريبية", 
                                         title_singular="قسم",
                                         action_base="departments",
                                         input_name="department",
                                         items=get_departments())

    elif active_tab == 'levels':
        content = render_template_string(ADMIN_CRUD_TAB, 
                                         active_tab=active_tab, 
                                         title="درجات المخالفات", 
                                         title_singular="درجة",
                                         action_base="levels",
                                         input_name="level",
                                         items=get_violation_levels())
                                         
    elif active_tab == 'actions': # التبويب الجديد لإدارة الإجراءات
        content = render_template_string(ADMIN_CRUD_TAB, 
                                         active_tab=active_tab, 
                                         title="الإجراءات المتخذة", 
                                         title_singular="إجراء",
                                         action_base="actions",
                                         input_name="action",
                                         items=get_actions())

    elif active_tab == 'buildings':
        content = render_template_string(ADMIN_CRUD_TAB, 
                                         active_tab=active_tab, 
                                         title="المباني", 
                                         title_singular="رقم مبنى",
                                         action_base="buildings",
                                         input_name="building",
                                         items=get_buildings())
                                         
    elif active_tab == 'rooms':
        all_rooms = get_rooms()
        buildings = get_buildings()
        
        rooms_content = f'''
            <h3>إدارة القاعات</h3>
            <form method="POST" action="/admin?tab=rooms" class="row g-2 mb-4">
                <input type="hidden" name="action" value="add_rooms">
                <div class="col-md-3">
                    <input type="text" name="room" placeholder="رقم القاعة الجديدة" required class="form-control">
                </div>
                <div class="col-md-3">
                    <select name="building_number" required class="form-select">
                        <option value="">اختر المبنى</option>
                        {''.join([f'<option value="{b}">{b}</option>' for b in buildings])}
                    </select>
                </div>
                <div class="col-md-auto">
                    <button type="submit" class="btn btn-primary">إضافة قاعة</button>
                </div>
            </form>
            <table class="table table-hover">
                <thead>
                    <tr><th>رقم القاعة</th><th>رقم المبنى</th><th>إجراءات</th></tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td>{r['room_number']}</td>
                        <td>{r['building_number']}</td>
                        <td>
                            <form method="POST" action="/admin?tab=rooms" onsubmit="return confirm('حذف هذه القاعة؟');" class="d-inline">
                                <input type="hidden" name="action" value="delete_rooms">
                                <input type="hidden" name="room" value="{r['room_number']}">
                                <input type="hidden" name="building_number" value="{r['building_number']}">
                                <button type="submit" class="btn btn-danger btn-sm">حذف</button>
                            </form>
                        </td>
                    </tr>
                    ''' for r in all_rooms])}
                </tbody>
            </table>
        '''
        content = rooms_content
                                         
    return render_template_string(BASE_TEMPLATE, 
                                 title="لوحة تحكم المدير", 
                                 content=ADMIN_NAV + content, 
                                 active_tab=active_tab)

@app.route('/search/<trainee_id>')
def search_trainee(trainee_id):
    mock_data = {
        '100100': 'محمد علي أحمد',
        '200200': 'سارة خالد فهد',
        '300300': 'عبدالله ناصر سعيد',
    }
    
    found_name = next((name for id_num, name in mock_data.items() if id_num.startswith(trainee_id)), None)
    
    if found_name:
        return jsonify({'id': trainee_id, 'name': found_name})
    else:
        return jsonify({'id': trainee_id, 'name': f'متدرب-{trainee_id}'})

@app.route('/get_rooms/<building>')
def api_get_rooms(building):
    rooms_data = get_rooms(building)
    room_numbers = [r['room_number'] for r in rooms_data]
    return jsonify(rooms=room_numbers)

@app.route('/get_violation_history/<int:index>')
def get_violation_history_route(index):
    history = get_violation_history(index)
    return jsonify(history)

@app.route('/reports')
def reports():
    violations = read_violations_with_index()
    department_counts = Counter(v['القسم التدريبي'] for v in violations)
    level_counts = Counter(v['درجة المخالفة'] for v in violations)
    content = f'''
        <h1>تقارير المخالفات</h1>
        <h3>عدد المخالفات حسب القسم:</h3>
        <ul>{''.join([f'<li>{dept}: {count}</li>' for dept, count in department_counts.items()])}</ul>
        <h3>عدد المخالفات حسب الدرجة:</h3>
        <ul>{''.join([f'<li>{level}: {count}</li>' for level, count in level_counts.items()])}</ul>
    '''
    return render_template_string(BASE_TEMPLATE, title="تقارير", content=content)

if __name__ == '__main__':
    # تهيئة الملفات عند التشغيل لأول مرة
    ensure_trainers_file()
    ensure_csv_header(CSV_FILE)
    get_departments()
    get_violation_levels()
    get_buildings()
    get_rooms()
    get_actions() # تهيئة ملف الإجراءات الجديد
    ensure_csv_header(VIOLATION_LOGS_FILE)
    
    print("Application starting...")
app.run(host='0.0.0.0', port=5000, debug=True)


