# Mi Centro de Control 4.0 — versión completa

Aplicación Python con interfaz web adaptable al celular, SQLite y gráficas interactivas.

## Funciones
- Resumen: tareas, hábitos, minutos de estudio y promedio estimado.
- Universidad: materias, créditos, notas de C1/C2/C3, pesos configurables, estimado y promedio requerido en cortes faltantes.
- Estudio: sesiones, duración, método, concentración y gráficas.
- Agenda: tareas/eventos, categoría, fecha, hora, duración, prioridad y estado.
- Hábitos: estudio, movimiento, estiramiento, diario, uso consciente del celular, sueño y agua.
- Ejercicio: registro de actividad, duración y notas.
- Diario: valoración del día, energía, logros, obstáculos, gratitud y plan para mañana.
- Objetivos: metas por área y fecha.
- Informes: exportación CSV por tabla y copia de la base de datos.
- Configuración: meta de promedio, pesos de cortes y objetivos diarios.
- Persistencia local en SQLite.

## Ejecutar en computador
1. Instala Python 3.10+.
2. Abre una terminal en la carpeta.
3. `python -m pip install -r requirements.txt`
4. `python -m streamlit run app.py`
5. Abre la URL local que indica Streamlit.

## Android
Recomendado: desplegar `app.py` y `requirements.txt` en un repositorio GitHub y lanzar desde Streamlit Community Cloud. Luego abre la URL en Chrome y elige “Añadir a pantalla de inicio”.
La base SQLite puede no ser persistente en hosting gratuito; descarga copias de seguridad con frecuencia. La primera versión no sincroniza datos entre dispositivos.

## Precisión académica
El estimado de una materia usa la media ponderada de los cortes registrados según los pesos configurados, pero las notas faltantes se muestran como parte de una estimación y no como definitiva oficial. No calcula los componentes internos de cada corte ni las reglas de redondeo particulares de la plataforma. Verifica los resultados con tu sistema universitario.
