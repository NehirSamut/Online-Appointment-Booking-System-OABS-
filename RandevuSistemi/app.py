from flask import Flask, request, render_template_string, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os, webbrowser, json, calendar
from threading import Timer
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "nehos_double_calendar_v11"

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'nehos_v11.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELLER ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(10), default='USER') 
    appointments = db.relationship('Appointment', backref='owner', lazy=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100))
    service = db.Column(db.String(100))
    date = db.Column(db.String(50))
    time = db.Column(db.String(50))
    status = db.Column(db.String(20), default='PENDING')
    rejection_reason = db.Column(db.String(255), default='')
    rating = db.Column(db.Integer, default=0)
    comment = db.Column(db.Text, default='')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# --- HİZMET DATA ---
SERVICES_CONFIG = {
    "💆‍♀️ Cilt Bakımı İşlemleri": ["Klasik Cilt Bakımı", "Hydrafacial", "Medikal Cilt Bakımı", "Anti-Aging Bakım", "Nem Bakımı"],
    "✨ Epilasyon & Tüy Alma": ["Lazer Epilasyon", "Buz Lazer", "İğneli Epilasyon", "Ağda", "Tüm Vücut Ağda"],
    "💄 Kalıcı Makyaj": ["Microblading", "Pudralama Kaş", "Dudak Renklendirme", "Kalıcı Eyeliner"],
    "💅 El & Ayak Bakımı": ["Manikür", "Pedikür", "Kalıcı Oje", "Protez Tırnak"],
    "🧘‍♀️ Bölgesel İncelme & Vücut": ["Bölgesel İncelme", "G5 Masajı", "Lenf Drenaj", "Selülit Tedavisi", "Masaj"]
}

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="admin@nehos.com").first():
        db.session.add(User(name="Personel Nehir", email="admin@nehos.com", 
                            password=generate_password_hash("admin123", method='pbkdf2:sha256'), role="ADMIN"))
        db.session.commit()

# --- CSS TASARIM ---
LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Nehoş Güzellik | {{ title }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root { --p: #d63384; --lp: #fff0f6; --hp: #ff85a2; }
        body { background-color: var(--lp); font-family: 'Poppins', sans-serif; font-size: 14px; }
        .navbar { background: linear-gradient(45deg, var(--hp), var(--p)); border: none; }
        .card { border-radius: 15px; border: none; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }
        .btn-pink { background: var(--p); color: white; font-weight: bold; border-radius: 8px; border: none; }
        
        /* ÇİFT TAKVİM STİLLERİ */
        .calendar-box { background: white; border-radius: 10px; overflow: hidden; margin-bottom: 20px; }
        .cal-header { background: var(--p); color: white; text-align: center; padding: 5px; font-weight: bold; }
        .day-header { background: #f8f9fa; text-align: center; font-size: 11px; font-weight: bold; border: 0.5px solid #eee; }
        .day-cell { min-height: 80px; border: 0.5px solid #eee; padding: 3px; font-size: 11px; position: relative; }
        .day-cell.today { background: #fff9c4; }
        .job-tag { background: var(--p); color: white; font-size: 9px; padding: 1px 3px; border-radius: 3px; margin-top: 2px; line-height: 1.1; }
        
        /* PEMBE YILDIZLAR */
        .rating { display: flex; flex-direction: row-reverse; justify-content: flex-start; }
        .rating input { display: none; }
        .rating label { font-size: 28px; color: #ddd; cursor: pointer; }
        .rating input:checked ~ label, .rating label:hover, .rating label:hover ~ label { color: var(--p) !important; }
        .rating label:before { content: '★'; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark mb-4 px-4 shadow">
        <a class="navbar-brand fw-bold" href="/">🌸 NEHOŞ GÜZELLİK</a>
        <div class="ms-auto">{% if 'user_id' in session %}<a href="/logout" class="btn btn-sm btn-outline-light">Çıkış</a>{% endif %}</div>
    </nav>
    <div class="container-fluid px-lg-5">
        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-warning py-2">{{m}}</div>{% endfor %}{% endwith %}
        {{ content | safe }}
    </div>
</body>
</html>
"""

def get_calendar_html(year, month, appointments):
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    month_name = calendar.month_name[month]
    
    html = f"<div class='calendar-box'><div class='cal-header'>{month_name} {year}</div>"
    html += "<div class='row g-0'>"
    for d in ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]: html += f"<div class='col day-header'>{d}</div>"
    html += "</div>"
    
    for week in month_days:
        html += "<div class='row g-0'>"
        for day in week:
            if day == 0:
                html += "<div class='col day-cell' style='background:#f9f9f9'></div>"
            else:
                date_str = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
                jobs = [a for a in appointments if a.date == date_str and a.status == 'APPROVED']
                html += f"<div class='col day-cell'><strong>{day}</strong>"
                for j in jobs: html += f"<div class='job-tag'>{j.time} {j.service}</div>"
                html += "</div>"
        html += "</div>"
    html += "</div>"
    return html

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    if user.role == 'ADMIN':
        apps = Appointment.query.all()
        now = datetime.now()
        
        # Çift Takvim Mantığı
        cal1 = get_calendar_html(now.year, now.month, apps)
        next_m = now.month + 1 if now.month < 12 else 1
        next_y = now.year if now.month < 12 else now.year + 1
        cal2 = get_calendar_html(next_y, next_m, apps)
        
        content = f"<h3>📅 Personel İş Planı (2 Aylık Takvim)</h3>"
        content += f"<div class='row'><div class='col-md-6'>{cal1}</div><div class='col-md-6'>{cal2}</div></div>"
        
        content += "<div class='card p-4 mt-3'><h4>Onay Bekleyenler & Yorumlar</h4><table class='table small'><thead><tr><th>Müşteri</th><th>Hizmet</th><th>Tarih</th><th>Puan/Yorum</th><th>İşlem</th></tr></thead><tbody>"
        for a in apps:
            fb = f"<span style='color:var(--p)'>{'★'*a.rating}</span><br><small>'{a.comment}'</small>" if a.rating > 0 else "-"
            content += f"<tr><td>{a.owner.name}</td><td>{a.service}</td><td>{a.date} {a.time}</td><td>{fb}</td><td>"
            if a.status == 'PENDING':
                content += f"<a href='/status/{a.id}/APPROVED' class='btn btn-sm btn-success py-0'>Onayla</a> "
                content += f"<button class='btn btn-sm btn-danger py-0' onclick='document.getElementById(\"rj-{a.id}\").style.display=\"block\"'>Reddet</button>"
                content += f"<div id='rj-{a.id}' style='display:none' class='mt-1'><form action='/reject/{a.id}' method='POST'><input name='reason' placeholder='Neden?' class='form-control form-control-sm' required><button class='btn btn-sm btn-dark w-100 mt-1'>Reddet</button></form></div>"
            else: content += f"<span class='badge bg-light text-dark'>{a.status}</span>"
            content += "</td></tr>"
        return render_template_string(LAYOUT, content=content + "</tbody></table></div>", title="Personel")
    
    else:
        my_apps = Appointment.query.filter_by(user_id=user.id).all()
        content = '<div class="row"><div class="col-md-4"><div class="card p-4"><h4>Randevu Al</h4><p class="small text-muted">Sadece önümüzdeki 60 gün için randevu alabilirsiniz.</p><form action="/book" method="POST">'
        content += '<select id="cat" name="category" class="form-select mb-2" onchange="upd()"><option value="">Kategori Seç...</option>'
        for k in SERVICES_CONFIG.keys(): content += f'<option value="{k}">{k}</option>'
        content += '</select><select id="ser" name="service" class="form-control mb-2"></select>'
        content += '<input type="date" name="date" class="form-control mb-2" required><input type="time" name="time" class="form-control mb-3" required><button class="btn btn-pink w-100">Talep Gönder</button></form></div>'
        content += '<script>const d = ' + json.dumps(SERVICES_CONFIG) + '; function upd(){const c=document.getElementById("cat").value; const s=document.getElementById("ser"); s.innerHTML=""; if(c){d[c].forEach(x=>{let o=document.createElement("option"); o.value=x; o.innerHTML=x; s.appendChild(o);});}}</script></div>'
        
        content += '<div class="col-md-8"><div class="card p-4"><h4>İşlemlerim ve Değerlendirme</h4>'
        for ma in my_apps:
            content += f"<div class='border-bottom py-3'><b>{ma.service}</b> | {ma.date} {ma.time} <span class='badge border ms-2'>{ma.status}</span>"
            if ma.status == 'APPROVED' and ma.rating == 0:
                content += f"""<div class='mt-2 p-2 bg-light rounded'><form action='/rate/{ma.id}' method='POST'><div class='rating'><input type='radio' id='s5-{ma.id}' name='rating' value='5' required/><label for='s5-{ma.id}'></label><input type='radio' id='s4-{ma.id}' name='rating' value='4'/><label for='s4-{ma.id}'></label><input type='radio' id='s3-{ma.id}' name='rating' value='3'/><label for='s3-{ma.id}'></label><input type='radio' id='s2-{ma.id}' name='rating' value='2'/><label for='s2-{ma.id}'></label><input type='radio' id='s1-{ma.id}' name='rating' value='1'/><label for='s1-{ma.id}'></label></div><textarea name='comment' class='form-control form-control-sm mb-1' placeholder='Yorumunuz...' required></textarea><button class='btn btn-pink btn-sm w-100'>Puanla</button></form></div>"""
            elif ma.rating > 0: content += f"<br><span style='color:var(--p)'>{'★'*ma.rating}</span> <i class='small'>\"{ma.comment}\"</i>"
            content += "</div>"
        return render_template_string(LAYOUT, content=content + "</div></div></div>", title="Müşteri")

@app.route('/book', methods=['POST'])
def book():
    dt_str, t = request.form.get('date'), request.form.get('time')
    try:
        req_date = datetime.strptime(dt_str, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # 60 Gün Sınırı Kontrolü
        if req_date < today or req_date > (today + timedelta(days=60)):
            flash("Üzgünüz! Randevular sadece önümüzdeki 60 gün (2 ay) için alınabilir.")
            return redirect(url_for('index'))
    except: pass

    hr = int(t.split(':')[0])
    if hr < 9 or hr >= 19 or hr == 12: flash("Mesai saatleri (09-19) veya öğle arası (12:00) seçilemez!"); return redirect(url_for('index'))
    db.session.add(Appointment(category=request.form.get('category'), service=request.form.get('service'), date=dt_str, time=t, user_id=session['user_id']))
    db.session.commit(); flash("Randevu talebiniz başarıyla iletildi."); return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form.get('email')).first(); lt = request.form.get('login_type')
        if u and check_password_hash(u.password, request.form.get('password')):
            if lt == 'staff' and u.role != 'ADMIN': flash("Hata: Personel yetkiniz yok!")
            else: session['user_id'], session['user_name'], session['role'] = u.id, u.name, u.role; return redirect(url_for('index'))
        else: flash("Hatalı giriş!")
    return render_template_string(LAYOUT, content="""<div class="row justify-content-center mt-5"><div class="col-md-5 card p-4 shadow-lg"><h3 class="text-center mb-4 text-pink">🌸 NEHOŞ GİRİŞ</h3><form method="POST"><div class="btn-group w-100 mb-3"><input type="radio" class="btn-check" name="login_type" id="c" value="cust" checked><label class="btn btn-outline-danger" for="c">Müşteri</label><input type="radio" class="btn-check" name="login_type" id="s" value="staff"><label class="btn btn-outline-dark" for="s">Personel</label></div><input name="email" class="form-control mb-2" placeholder="E-posta" required><input name="password" type="password" class="form-control mb-3" placeholder="Şifre" required><button class="btn btn-pink w-100">Giriş</button></form><div class="text-center mt-3 small"><a href="/register">Kayıt Ol</a></div></div></div>""", title="Giriş")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db.session.add(User(name=request.form.get('name'), email=request.form.get('email'), password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'))); db.session.commit(); flash("Kayıt Başarılı!"); return redirect(url_for('login'))
    return render_template_string(LAYOUT, content="""<div class="row justify-content-center mt-5"><div class="col-md-4 card p-4"><h4>Yeni Kayıt</h4><form method="POST"><input name="name" class="form-control mb-2" placeholder="Ad Soyad" required><input name="email" class="form-control mb-2" placeholder="E-posta" required><input name="password" type="password" class="form-control mb-3" placeholder="Şifre" required><button class="btn btn-pink w-100">Kayıt Ol</button></form></div></div>""", title="Kayıt")

@app.route('/rate/<int:id>', methods=['POST'])
def rate(id):
    a = Appointment.query.get(id); a.rating, a.comment = request.form.get('rating'), request.form.get('comment'); db.session.commit(); return redirect(url_for('index'))

@app.route('/status/<int:id>/<string:new_status>')
def status(id, new_status):
    a = Appointment.query.get(id); a.status = new_status; db.session.commit(); return redirect(url_for('index'))

@app.route('/reject/<int:id>', methods=['POST'])
def reject(id):
    a = Appointment.query.get(id); a.status = 'REJECTED'; a.rejection_reason = request.form.get('reason'); db.session.commit(); return redirect(url_for('index'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new("http://127.0.0.1:5001")).start()
    app.run(debug=True, port=5001, use_reloader=False)