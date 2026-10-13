from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta, time
import json
import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "centro_control.db"
st.set_page_config(page_title="Mi Centro de Control 4.0", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")

# -------------------- Datos / persistencia --------------------
def connect():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c

def execute(sql, args=()):
    with connect() as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid

def read_df(sql, args=()):
    with connect() as c:
        return pd.read_sql_query(sql, c, params=args)

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subjects(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
            credits REAL NOT NULL DEFAULT 0, notes TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS grades(
            id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER NOT NULL,
            cut INTEGER NOT NULL CHECK(cut IN (1,2,3)), grade REAL NOT NULL CHECK(grade>=0 AND grade<=5),
            label TEXT DEFAULT '', created_at TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS study_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT NOT NULL, subject_id INTEGER,
            minutes INTEGER NOT NULL, method TEXT DEFAULT '', focus INTEGER DEFAULT 3, notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS workouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, workout_date TEXT NOT NULL, activity TEXT NOT NULL,
            minutes INTEGER NOT NULL, notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_date TEXT NOT NULL, title TEXT NOT NULL,
            event_type TEXT DEFAULT 'Personal', details TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS goals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, area TEXT NOT NULL,
            target_date TEXT DEFAULT '', why TEXT DEFAULT '', done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL,
            due_date TEXT NOT NULL, due_time TEXT DEFAULT '', duration INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'Media', details TEXT DEFAULT '', done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS habit_logs(
            log_date TEXT PRIMARY KEY, study INTEGER NOT NULL DEFAULT 0, movement INTEGER NOT NULL DEFAULT 0,
            stretching INTEGER NOT NULL DEFAULT 0, journal INTEGER NOT NULL DEFAULT 0,
            mindful_phone INTEGER NOT NULL DEFAULT 0, sleep_hours REAL DEFAULT 0,
            water_glasses INTEGER DEFAULT 0, reflection TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS journal(
            entry_date TEXT PRIMARY KEY, mood INTEGER NOT NULL DEFAULT 3, energy INTEGER DEFAULT 3,
            went_well TEXT DEFAULT '', obstacle TEXT DEFAULT '', tomorrow TEXT DEFAULT '',
            gratitude TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS study_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT NOT NULL, subject_id INTEGER,
            minutes INTEGER NOT NULL, method TEXT DEFAULT '', focus INTEGER DEFAULT 3,
            notes TEXT DEFAULT '', FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE SET NULL);
        CREATE TABLE IF NOT EXISTS workouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, workout_date TEXT NOT NULL, activity TEXT NOT NULL,
            minutes INTEGER NOT NULL, notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_date TEXT NOT NULL, title TEXT NOT NULL,
            event_type TEXT DEFAULT 'Personal', details TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS goals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, area TEXT NOT NULL,
            target_date TEXT DEFAULT '', why TEXT DEFAULT '', done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_date TEXT NOT NULL, title TEXT NOT NULL,
            event_type TEXT DEFAULT 'Personal', details TEXT DEFAULT '');
        """)
        defaults = {
            "target_average": "4.0",
            "cut1_weight": "0.30",
            "cut2_weight": "0.30",
            "cut3_weight": "0.40",
            "semester_name": "Semestre actual",
            "daily_study_target": "120",
            "daily_sleep_target": "8",
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))
        c.commit()

def get_setting(key, default=""):
    row = read_df("SELECT value FROM settings WHERE key=?", (key,))
    return str(row.iloc[0]["value"]) if len(row) else default

def set_setting(key, value):
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,str(value)))

def fmt(x, decimals=2):
    if x is None or pd.isna(x): return "—"
    return f"{float(x):.{decimals}f}".rstrip("0").rstrip(".")

def download_csv(df, filename, label):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), file_name=filename, mime="text/csv", use_container_width=True)

init_db()
today = date.today()
today_s = today.isoformat()
weights = [float(get_setting("cut1_weight","0.3")), float(get_setting("cut2_weight","0.3")), float(get_setting("cut3_weight","0.4"))]
weight_sum = sum(weights) or 1

# -------------------- Estilos --------------------
st.markdown("""
<style>
.block-container{padding-top:1.1rem;max-width:1250px;padding-bottom:3rem}
[data-testid="stMetric"]{background:rgba(120,120,120,.07);padding:13px;border-radius:13px;border:1px solid rgba(120,120,120,.12)}
div.stButton>button{border-radius:10px;min-height:2.5rem}
div[data-testid="stForm"]{border-radius:12px}
.small-muted{font-size:.86rem;opacity:.75}
</style>
""", unsafe_allow_html=True)

st.title("🎯 Mi Centro de Control 4.0")
st.caption("Tu panel personal para Ingeniería Civil, hábitos, agenda, bienestar y progreso.")
pages = ["Resumen", "Universidad", "Estudio", "Agenda", "Hábitos", "Ejercicio", "Diario", "Objetivos", "Informes y copias", "Configuración"]
page = st.sidebar.radio("Navegación", pages)
st.sidebar.divider()
st.sidebar.caption("Meta académica")
st.sidebar.metric("Promedio objetivo", get_setting("target_average","4.0"))
st.sidebar.caption("La aplicación guarda los datos en SQLite. Haz copias de seguridad periódicas.")

# -------------------- Helpers --------------------
def subject_table():
    return read_df("""SELECT s.id,s.name,s.credits,s.notes,
        AVG(CASE WHEN g.cut=1 THEN g.grade END) c1,
        AVG(CASE WHEN g.cut=2 THEN g.grade END) c2,
        AVG(CASE WHEN g.cut=3 THEN g.grade END) c3,
        COUNT(g.id) n_grades
        FROM subjects s LEFT JOIN grades g ON s.id=g.subject_id
        WHERE s.active=1 GROUP BY s.id ORDER BY s.name""")

def estimate_courses():
    d = subject_table()
    if len(d):
        w = weights
        d["estimated_final"] = d["c1"].fillna(0)*w[0] + d["c2"].fillna(0)*w[1] + d["c3"].fillna(0)*w[2]
        # If a cut has not been recorded, do not count its missing grade as zero for a rough observed estimate.
        for idx, row in d.iterrows():
            vals = [(row["c1"],w[0]),(row["c2"],w[1]),(row["c3"],w[2])]
            observed = [(v,wt) for v,wt in vals if pd.notna(v)]
            d.loc[idx,"observed_weight"] = sum(wt for _,wt in observed)
            d.loc[idx,"observed_average"] = sum(v*wt for v,wt in observed)/sum(wt for _,wt in observed) if observed and sum(wt for _,wt in observed)>0 else None
            d.loc[idx,"needed_remaining"] = None
            rem = sum(wt for v,wt in vals if pd.isna(v))
            if rem > 0:
                earned = sum(v*wt for v,wt in vals if pd.notna(v))
                d.loc[idx,"needed_remaining"] = (float(get_setting("target_average","4.0"))-earned)/rem
        return d
    return d

def semester_average(d):
    if not len(d): return None
    valid = d.dropna(subset=["observed_average"])
    if not len(valid): return None
    credit_rows = valid[valid["credits"] > 0]
    if len(credit_rows):
        return float((credit_rows["observed_average"]*credit_rows["credits"]).sum()/credit_rows["credits"].sum())
    return float(valid["observed_average"].mean())

def get_habits():
    return read_df("SELECT * FROM habit_logs ORDER BY log_date")

def habits_count(row):
    return int(sum(int(row[k]) for k in ["study","movement","stretching","journal","mindful_phone"]))

def mood_label(n):
    return {1:"Muy difícil",2:"Difícil",3:"Intermedio",4:"Bueno",5:"Muy bueno"}.get(int(n),"—")

# -------------------- Resumen --------------------
if page == "Resumen":
    st.subheader("Tu panorama")
    grades = estimate_courses()
    avg = semester_average(grades)
    pending = int(read_df("SELECT COUNT(*) n FROM tasks WHERE done=0").iloc[0]["n"])
    tasks_today = read_df("SELECT * FROM tasks WHERE due_date=? ORDER BY done, due_time", (today_s,))
    habits = read_df("SELECT * FROM habit_logs WHERE log_date=?", (today_s,))
    hc = habits_count(habits.iloc[0]) if len(habits) else 0
    minutes = int(read_df("SELECT COALESCE(SUM(minutes),0) n FROM study_sessions WHERE session_date=?", (today_s,)).iloc[0]["n"])
    a,b,c,d = st.columns(4)
    a.metric("Tareas pendientes", pending)
    b.metric("Hábitos de hoy", f"{hc}/5")
    c.metric("Estudio hoy", f"{minutes//60} h {minutes%60} min")
    d.metric("Promedio estimado", fmt(avg) if avg is not None else "—")
    target = float(get_setting("target_average","4.0"))
    if avg is not None:
        if avg >= target: st.success(f"Tu promedio estimado es {avg:.2f}; está en la meta de {target:.2f} o por encima.")
        else: st.info(f"Promedio estimado {avg:.2f}. Diferencia hasta la meta: {target-avg:.2f}. El cálculo es orientativo según los registros disponibles.")
    else: st.caption("Añade materias y notas en Universidad para ver una estimación.")

    l,r = st.columns([1.15,1])
    with l:
        st.markdown("#### Agenda de hoy")
        if len(tasks_today):
            for _, t in tasks_today.iterrows():
                st.write(f"{'✅' if t['done'] else '🕒'} **{t['title']}** · {t['due_time'] or 'Sin hora'} · {t['category']}")
        else: st.caption("No hay tareas programadas para hoy.")
    with r:
        st.markdown("#### Reto principal")
        with st.form("challenge"):
            challenge = st.text_input("Una acción concreta para hoy", value=st.session_state.get("challenge",""), placeholder="Ej. Resolver cinco ejercicios")
            if st.form_submit_button("Guardar reto"):
                st.session_state["challenge"] = challenge.strip()
                st.success("Reto guardado en esta sesión.")
        if st.session_state.get("challenge"): st.info(st.session_state["challenge"])

    st.markdown("#### Tendencias")
    h = get_habits()
    if len(h):
        h["Fecha"] = pd.to_datetime(h["log_date"])
        h["Acciones"] = h[["study","movement","stretching","journal","mindful_phone"]].sum(axis=1)
        fig = px.bar(h.tail(30), x="Fecha", y="Acciones", range_y=[0,5], title="Hábitos completados por día")
        st.plotly_chart(fig, use_container_width=True)
    else: st.caption("Registra tus hábitos para empezar a ver tendencias.")

# -------------------- Universidad --------------------
elif page == "Universidad":
    st.subheader("🎓 Universidad")
    st.caption("Pesos configurables de los cortes. El estimado usa las notas ingresadas y estos pesos; confirma la definitiva con tu plataforma oficial.")
    with st.expander("Añadir materia", expanded=len(subject_table()) == 0):
        with st.form("subject_add", clear_on_submit=True):
            name = st.text_input("Nombre de la materia")
            credits = st.number_input("Créditos", 0.0, 30.0, 3.0, 0.5)
            notes = st.text_input("Notas o detalles")
            if st.form_submit_button("Añadir materia"):
                if not name.strip(): st.error("Escribe el nombre de la materia.")
                else:
                    try:
                        execute("INSERT INTO subjects(name,credits,notes) VALUES(?,?,?)",(name.strip(),credits,notes.strip()))
                        st.success("Materia añadida."); st.rerun()
                    except sqlite3.IntegrityError: st.error("Ya existe una materia con ese nombre.")
    subs = read_df("SELECT * FROM subjects WHERE active=1 ORDER BY name")
    if len(subs):
        mp = {row["name"]:int(row["id"]) for _,row in subs.iterrows()}
        with st.form("grade_add", clear_on_submit=True):
            sub_name = st.selectbox("Materia",list(mp.keys()))
            cut = st.selectbox("Corte",[1,2,3],format_func=lambda x:f"C{x}")
            grade = st.number_input("Nota registrada (0–5)",0.0,5.0,4.0,0.1)
            label = st.text_input("Descripción opcional",placeholder="Ej. Parcial, definitiva de corte")
            if st.form_submit_button("Guardar nota"):
                execute("INSERT INTO grades(subject_id,cut,grade,label,created_at) VALUES(?,?,?,?,?)",(mp[sub_name],cut,grade,label.strip(),datetime.now().isoformat(timespec="seconds")))
                st.success("Nota guardada."); st.rerun()
        data = estimate_courses()
        if len(data):
            display = data[["name","credits","c1","c2","c3","observed_average","needed_remaining","n_grades"]].copy()
            display.columns = ["Materia","Créditos","C1","C2","C3","Promedio observado","Promedio necesario restante*","Notas"]
            for col in ["C1","C2","C3","Promedio observado","Promedio necesario restante*"]:
                display[col] = display[col].apply(fmt)
            st.dataframe(display,use_container_width=True,hide_index=True)
            st.caption("*Promedio aproximado que necesitarías en los cortes sin nota, según los pesos configurados y meta actual. Puede superar 5 o ser negativo.")
            chart = data.melt(id_vars=["name"],value_vars=["c1","c2","c3"],var_name="Corte",value_name="Nota").dropna()
            if len(chart):
                chart["Corte"] = chart["Corte"].str.upper()
                st.plotly_chart(px.bar(chart,x="name",y="Nota",color="Corte",barmode="group",range_y=[0,5],title="Notas por corte"),use_container_width=True)
            with st.expander("Historial de notas"):
                history = read_df("""SELECT s.name Materia,g.cut Corte,g.grade Nota,g.label Descripcion,g.created_at Fecha
                                     FROM grades g JOIN subjects s ON s.id=g.subject_id ORDER BY g.created_at DESC""")
                st.dataframe(history,use_container_width=True,hide_index=True)
                if len(history):
                    to_delete = st.selectbox("Eliminar una nota",history.index.tolist(),format_func=lambda i:f"{history.loc[i,'Materia']} · C{history.loc[i,'Corte']} · {history.loc[i,'Nota']} · {history.loc[i,'Fecha']}",key="grade_delete")
                    if st.button("Eliminar nota seleccionada"):
                        row = history.loc[to_delete]
                        execute("DELETE FROM grades WHERE subject_id=(SELECT id FROM subjects WHERE name=?) AND cut=? AND grade=? AND created_at=?",(row["Materia"],int(row["Corte"]),float(row["Nota"]),row["Fecha"]))
                        st.rerun()
            with st.expander("Eliminar materia"):
                delete_sub = st.selectbox("Materia",list(mp.keys()),key="sub_delete")
                if st.button("Eliminar materia y sus notas"):
                    execute("DELETE FROM grades WHERE subject_id=?",(mp[delete_sub],))
                    execute("DELETE FROM subjects WHERE id=?",(mp[delete_sub],))
                    st.rerun()
    else: st.info("Añade tus materias para empezar.")

# -------------------- Estudio --------------------
elif page == "Estudio":
    st.subheader("📚 Sesiones de estudio")
    subs = read_df("SELECT id,name FROM subjects WHERE active=1 ORDER BY name")
    opts = {"Sin materia específica": None}
    if len(subs):
        opts.update({r["name"]:int(r["id"]) for _,r in subs.iterrows()})
    with st.form("study_session",clear_on_submit=True):
        d = st.date_input("Fecha",today)
        subject_name = st.selectbox("Materia",list(opts.keys()))
        minutes = st.number_input("Duración (minutos)",min_value=5,max_value=600,value=50,step=5)
        method = st.selectbox("Método",["Ejercicios prácticos","Repaso activo","Lectura y apuntes","Clase o laboratorio","Trabajo grupal","Otro"])
        focus = st.slider("Nivel de concentración",1,5,3)
        notes = st.text_area("Qué avancé / siguiente paso")
        if st.form_submit_button("Guardar sesión"):
            execute("INSERT INTO study_sessions(session_date,subject_id,minutes,method,focus,notes) VALUES(?,?,?,?,?,?)",(d.isoformat(),opts[subject_name],minutes,method,focus,notes.strip()))
            st.success("Sesión guardada."); st.rerun()
    sessions = read_df("""SELECT ss.*,COALESCE(s.name,'Sin materia') materia FROM study_sessions ss
                          LEFT JOIN subjects s ON s.id=ss.subject_id ORDER BY session_date DESC,id DESC""")
    if len(sessions):
        sessions["Horas"] = (sessions["minutes"]/60).round(2)
        st.metric("Minutos de estudio registrados",int(sessions["minutes"].sum()))
        st.dataframe(sessions[["session_date","materia","minutes","method","focus","notes"]].rename(columns={"session_date":"Fecha","materia":"Materia","minutes":"Minutos","method":"Método","focus":"Concentración","notes":"Notas"}),use_container_width=True,hide_index=True)
        sessions["Fecha"] = pd.to_datetime(sessions["session_date"])
        byday = sessions.groupby("Fecha",as_index=False)["minutes"].sum()
        st.plotly_chart(px.bar(byday,x="Fecha",y="minutes",title="Minutos de estudio por día"),use_container_width=True)

# -------------------- Agenda --------------------
elif page == "Agenda":
    st.subheader("🗓️ Agenda")
    with st.form("task_add",clear_on_submit=True):
        title = st.text_input("Tarea o evento")
        category = st.selectbox("Categoría",["Universidad","Ejercicio","Estiramientos","Personal","Descanso","Trámite","Otro"])
        d = st.date_input("Fecha",today)
        t = st.time_input("Hora",datetime.strptime("08:00","%H:%M").time())
        no_time = st.checkbox("Sin hora específica")
        duration = st.number_input("Duración estimada (minutos)",min_value=0,max_value=1440,value=0,step=5)
        priority = st.selectbox("Prioridad",["Alta","Media","Baja"])
        details = st.text_area("Detalles")
        if st.form_submit_button("Añadir a la agenda"):
            if not title.strip(): st.error("Escribe un título.")
            else:
                execute("INSERT INTO tasks(title,category,due_date,due_time,duration,priority,details,created_at) VALUES(?,?,?,?,?,?,?,?)",
                        (title.strip(),category,d.isoformat(),"" if no_time else t.strftime("%H:%M"),duration,priority,details.strip(),datetime.now().isoformat(timespec="seconds")))
                st.success("Tarea añadida."); st.rerun()
    tab1,tab2 = st.tabs(["Por fecha","Todas"])
    with tab1:
        selected = st.date_input("Ver fecha",today,key="agenda_selected")
        items = read_df("SELECT * FROM tasks WHERE due_date=? ORDER BY done,due_time",(selected.isoformat(),))
        if len(items):
            for _,row in items.iterrows():
                left,right = st.columns([.09,.91])
                with left: done = st.checkbox("Hecha",bool(row["done"]),key=f"taskdone{row['id']}",label_visibility="collapsed")
                with right:
                    st.markdown(f"**{row['title']}** · {row['due_time'] or 'Sin hora'} · {row['category']} · Prioridad: {row['priority']}")
                    if row["duration"]: st.caption(f"Duración estimada: {row['duration']} min")
                    if row["details"]: st.caption(row["details"])
                if int(done)!=int(row["done"]):
                    execute("UPDATE tasks SET done=? WHERE id=?",(int(done),int(row["id"]))); st.rerun()
        else: st.caption("No hay tareas para esta fecha.")
    with tab2:
        items = read_df("SELECT * FROM tasks ORDER BY due_date,due_time")
        if len(items):
            st.dataframe(items[["title","category","due_date","due_time","duration","priority","done","details"]].rename(columns={"title":"Tarea","category":"Categoría","due_date":"Fecha","due_time":"Hora","duration":"Minutos","priority":"Prioridad","done":"Hecha","details":"Detalles"}),use_container_width=True,hide_index=True)
            ids = {f"{r['due_date']} · {r['title']} · #{r['id']}":int(r["id"]) for _,r in items.iterrows()}
            choice = st.selectbox("Seleccionar tarea para eliminar",list(ids),key="task_delete")
            if st.button("Eliminar tarea seleccionada"):
                execute("DELETE FROM tasks WHERE id=?",(ids[choice],)); st.rerun()

# -------------------- Hábitos --------------------
elif page == "Hábitos":
    st.subheader("🌱 Hábitos")
    st.caption("Registra lo que pasó; los datos sirven para aprender de tus patrones, no para juzgarte.")
    old = read_df("SELECT * FROM habit_logs WHERE log_date=?",(today_s,))
    row = old.iloc[0] if len(old) else None
    with st.form("habit_form"):
        study = st.checkbox("Hice un bloque importante de estudio",bool(row["study"]) if row is not None else False)
        movement = st.checkbox("Hice ejercicio o movimiento",bool(row["movement"]) if row is not None else False)
        stretching = st.checkbox("Hice los estiramientos previstos",bool(row["stretching"]) if row is not None else False)
        journal_done = st.checkbox("Escribí en mi diario",bool(row["journal"]) if row is not None else False)
        phone = st.checkbox("Usé el celular conscientemente",bool(row["mindful_phone"]) if row is not None else False)
        sleep = st.number_input("Horas de sueño",0.0,24.0,float(row["sleep_hours"]) if row is not None else 0.0,0.5)
        water = st.number_input("Vasos de agua (opcional)",0,50,int(row["water_glasses"]) if row is not None else 0)
        reflection = st.text_area("Nota del día",str(row["reflection"]) if row is not None else "")
        if st.form_submit_button("Guardar hábitos"):
            execute("""INSERT INTO habit_logs VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(log_date) DO UPDATE SET
                study=excluded.study,movement=excluded.movement,stretching=excluded.stretching,journal=excluded.journal,
                mindful_phone=excluded.mindful_phone,sleep_hours=excluded.sleep_hours,water_glasses=excluded.water_glasses,
                reflection=excluded.reflection""",
                (today_s,int(study),int(movement),int(stretching),int(journal_done),int(phone),sleep,water,reflection.strip()))
            st.success("Registro guardado."); st.rerun()
    hist = read_df("SELECT * FROM habit_logs ORDER BY log_date DESC")
    if len(hist):
        hist["Acciones"] = hist[["study","movement","stretching","journal","mindful_phone"]].sum(axis=1)
        st.dataframe(hist.rename(columns={"log_date":"Fecha","study":"Estudio","movement":"Movimiento","stretching":"Estiramientos","journal":"Diario","mindful_phone":"Celular consciente","sleep_hours":"Sueño (h)","water_glasses":"Vasos de agua","reflection":"Nota"}),use_container_width=True,hide_index=True)
        plot = hist.sort_values("log_date").copy(); plot["Fecha"] = pd.to_datetime(plot["log_date"])
        st.plotly_chart(px.line(plot,x="Fecha",y="Acciones",markers=True,range_y=[0,5],title="Acciones cumplidas por día"),use_container_width=True)
        sleep_plot = plot[plot["sleep_hours"]>0]
        if len(sleep_plot): st.plotly_chart(px.line(sleep_plot,x="Fecha",y="sleep_hours",markers=True,title="Horas de sueño registradas"),use_container_width=True)

# -------------------- Ejercicio --------------------
elif page == "Ejercicio":
    st.subheader("🏃 Movimiento y entrenamiento")
    with st.form("workout_form",clear_on_submit=True):
        d = st.date_input("Fecha",today)
        activity = st.selectbox("Actividad",["Gimnasio","Caminar","Movilidad/estiramiento","Deporte","Bicicleta","Otra"])
        minutes = st.number_input("Duración (minutos)",5,600,45,5)
        notes = st.text_area("Notas (opcional)")
        if st.form_submit_button("Registrar actividad"):
            execute("INSERT INTO workouts(workout_date,activity,minutes,notes) VALUES(?,?,?,?)",(d.isoformat(),activity,minutes,notes.strip()))
            st.success("Actividad registrada."); st.rerun()
    workouts = read_df("SELECT * FROM workouts ORDER BY workout_date DESC,id DESC")
    if len(workouts):
        c1,c2 = st.columns(2)
        c1.metric("Sesiones registradas",len(workouts))
        c2.metric("Minutos acumulados",int(workouts["minutes"].sum()))
        st.dataframe(workouts.rename(columns={"workout_date":"Fecha","activity":"Actividad","minutes":"Minutos","notes":"Notas"}),use_container_width=True,hide_index=True)
        w = workouts.copy(); w["Fecha"] = pd.to_datetime(w["workout_date"])
        st.plotly_chart(px.bar(w.groupby("Fecha",as_index=False)["minutes"].sum(),x="Fecha",y="minutes",title="Minutos de actividad por día"),use_container_width=True)
    else: st.caption("Registra tu primera sesión de movimiento.")

# -------------------- Diario --------------------
elif page == "Diario":
    st.subheader("📔 Diario personal")
    chosen = st.date_input("Fecha de la entrada",today,key="journal_date")
    old = read_df("SELECT * FROM journal WHERE entry_date=?",(chosen.isoformat(),))
    row = old.iloc[0] if len(old) else None
    with st.form("journal_form"):
        mood = st.slider("Cómo estuvo tu día (1 difícil – 5 muy bueno)",1,5,int(row["mood"]) if row is not None else 3)
        energy = st.slider("Energía (1 baja – 5 alta)",1,5,int(row["energy"]) if row is not None else 3)
        well = st.text_area("¿Qué salió bien?",str(row["went_well"]) if row is not None else "")
        obstacle = st.text_area("¿Qué me frenó o distrajo?",str(row["obstacle"]) if row is not None else "")
        gratitude = st.text_area("Algo que agradezco",str(row["gratitude"]) if row is not None else "")
        tomorrow = st.text_area("¿Qué quiero intentar mañana?",str(row["tomorrow"]) if row is not None else "")
        if st.form_submit_button("Guardar entrada"):
            execute("""INSERT INTO journal VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(entry_date) DO UPDATE SET
                mood=excluded.mood,energy=excluded.energy,went_well=excluded.went_well,obstacle=excluded.obstacle,
                tomorrow=excluded.tomorrow,gratitude=excluded.gratitude""",
                (chosen.isoformat(),mood,energy,well.strip(),obstacle.strip(),tomorrow.strip(),gratitude.strip(),datetime.now().isoformat(timespec="seconds")))
            st.success("Entrada guardada."); st.rerun()
    history = read_df("SELECT * FROM journal ORDER BY entry_date DESC")
    if len(history):
        st.markdown("#### Historial")
        st.dataframe(history[["entry_date","mood","energy","went_well","obstacle","gratitude","tomorrow"]].rename(columns={"entry_date":"Fecha","mood":"Día","energy":"Energía","went_well":"Qué salió bien","obstacle":"Obstáculo","gratitude":"Gratitud","tomorrow":"Para mañana"}),use_container_width=True,hide_index=True)
        plot = history.sort_values("entry_date").copy(); plot["Fecha"] = pd.to_datetime(plot["entry_date"])
        st.plotly_chart(px.line(plot,x="Fecha",y=["mood","energy"],markers=True,range_y=[1,5],title="Estado del día y energía"),use_container_width=True)

# -------------------- Objetivos --------------------
elif page == "Objetivos":
    st.subheader("🎯 Objetivos")
    with st.form("goal_form",clear_on_submit=True):
        title = st.text_input("Objetivo concreto",placeholder="Ej. Resolver 20 ejercicios de programación esta semana")
        area = st.selectbox("Área",["Universidad","Hábitos","Salud","Personal","Proyecto familiar","Otra"])
        target_date = st.date_input("Fecha objetivo",today+timedelta(days=7))
        why = st.text_area("¿Por qué importa?")
        if st.form_submit_button("Añadir objetivo"):
            if title.strip():
                execute("INSERT INTO goals(title,area,target_date,why,created_at) VALUES(?,?,?,?,?)",(title.strip(),area,target_date.isoformat(),why.strip(),datetime.now().isoformat(timespec="seconds")))
                st.rerun()
            else: st.error("Escribe el objetivo.")
    goals = read_df("SELECT * FROM goals ORDER BY done,target_date")
    if len(goals):
        for _,g in goals.iterrows():
            a,b = st.columns([.85,.15])
            with a:
                st.write(f"{'✅' if g['done'] else '⬜'} **{g['title']}** · {g['area']} · objetivo: {g['target_date']}")
                if g["why"]: st.caption(g["why"])
            with b:
                if not g["done"] and st.button("Completar",key=f"goal{g['id']}"):
                    execute("UPDATE goals SET done=1 WHERE id=?",(int(g["id"]),)); st.rerun()
        with st.expander("Eliminar objetivo"):
            choices = {f"{g['title']} · #{g['id']}":int(g["id"]) for _,g in goals.iterrows()}
            choice = st.selectbox("Objetivo",list(choices))
            if st.button("Eliminar objetivo seleccionado"):
                execute("DELETE FROM goals WHERE id=?",(choices[choice],)); st.rerun()
    else: st.caption("Define un objetivo pequeño y concreto para empezar.")

# -------------------- Informes y copias --------------------
elif page == "Informes y copias":
    st.subheader("📊 Informes y copias de seguridad")
    tables = ["subjects","grades","tasks","habit_logs","journal","study_sessions","workouts","goals"]
    st.write("Descarga copias CSV de tus registros. Guarda además una copia del archivo `centro_control.db` para conservar la base completa.")
    for table in tables:
        data = read_df(f"SELECT * FROM {table}")
        st.download_button(f"Descargar {table}.csv",data.to_csv(index=False).encode("utf-8-sig"),file_name=f"{table}.csv",mime="text/csv",key=f"csv_{table}")
    if DB_PATH.exists():
        st.download_button("Descargar base de datos completa",DB_PATH.read_bytes(),file_name="centro_control.db",mime="application/octet-stream")
    st.warning("Si alojas la app en un servicio gratuito, el archivo SQLite puede no persistir tras ciertos reinicios. Descarga copias con regularidad.")

# -------------------- Configuración --------------------
elif page == "Configuración":
    st.subheader("⚙️ Configuración")
    st.write("Adapta la aplicación a tu semestre. Los pesos predeterminados reflejan C1=30 %, C2=30 %, C3=40 %; cámbialos si tu curso usa otros.")
    with st.form("settings_form"):
        semester = st.text_input("Nombre del semestre",get_setting("semester_name","Semestre actual"))
        target_avg = st.number_input("Promedio objetivo",0.0,5.0,float(get_setting("target_average","4.0")),0.05)
        w1 = st.number_input("Peso C1",0.0,1.0,float(get_setting("cut1_weight","0.30")),0.05)
        w2 = st.number_input("Peso C2",0.0,1.0,float(get_setting("cut2_weight","0.30")),0.05)
        w3 = st.number_input("Peso C3",0.0,1.0,float(get_setting("cut3_weight","0.40")),0.05)
        study_target = st.number_input("Meta diaria de estudio (minutos)",0,1000,int(get_setting("daily_study_target","120")),5)
        sleep_target = st.number_input("Meta de sueño (horas)",0.0,24.0,float(get_setting("daily_sleep_target","8")),0.5)
        if st.form_submit_button("Guardar configuración"):
            if abs(w1+w2+w3-1.0) > 0.001:
                st.error("Los pesos de C1, C2 y C3 deben sumar 1.00 (100 %).")
            else:
                for k,v in [("semester_name",semester),("target_average",target_avg),("cut1_weight",w1),("cut2_weight",w2),("cut3_weight",w3),("daily_study_target",study_target),("daily_sleep_target",sleep_target)]:
                    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
                st.success("Configuración guardada."); st.rerun()
    st.markdown("#### Exportar datos")
    all_tables = {}
    for table in ["subjects","grades","tasks","habit_logs","journal","study_sessions","workouts","goals","events"]:
        all_tables[table] = read_df(f"SELECT * FROM {table}").to_dict(orient="records")
    st.download_button("Exportar datos como JSON",json.dumps(all_tables,ensure_ascii=False,indent=2,default=str).encode("utf-8"),file_name="mi_centro_control_backup.json",mime="application/json")

st.sidebar.divider()
st.sidebar.caption("Versión completa inicial · Streamlit + SQLite + Plotly")
