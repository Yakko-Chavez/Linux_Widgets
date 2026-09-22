# Widgets de escritorio para Wayland (Ubuntu + GNOME)

Reloj Diver, Agenda de Lujo, Clima Dorado, Monitor Dorado, Cronógrafo
Mecánico y Calculadora Dorada: ventanas GTK4 flotantes, sin bordes, dibujadas
100% en vectorial con Cairo. Sin imágenes externas y sin marcas registradas.

> Nota Wayland/GNOME: `gtk-layer-shell` **no funciona en GNOME**. Son ventanas
> GTK4 sin decoración, transparentes, que no roban foco. No quedan como fondo
> real detrás del wallpaper, pero sí flotantes siempre visibles.

## Filosofía común

- Render en memoria: `pycairo` (ARGB32) → `Gtk.Picture` vía `Gdk.MemoryTexture`
  (`B8G8R8A8_PREMULTIPLIED`). Sin archivos temporales, sin `python3-gi-cairo`.
- Buffer = tamaño lógico × escala real del monitor (`widget_scale()`): la
  ventana mide lo configurado en x1 y se ve nítida en HiDPI.
- Infraestructura común en `widget_base.py` (config, render, ventana, gestos,
  menú, bloqueo, teclas).
- Movimiento por protocolo Wayland (`surface.begin_move()`); en GNOME también
  vale `Super + arrastrar`.
- Doble-click / tecla `L`: bloquear (sin arrastre, sin menú; aparece candadito
  dorado vectorial abajo-derecha en Agenda/Clima/Sysmon/Chrono, arriba-derecha
  en la Calculadora).
- Click derecho: menú contextual. `+ / −`: tamaño. `Q / Esc`: salir.
- **Configuración…** en el menú: diálogo para tamaño/alto, opacidad y opciones
  propias de cada widget (ciudad y coordenadas en el clima, sweep en el reloj,
  semana en lunes en la agenda).
- **Idiomas ES/EN**: menús, diálogos y textos dibujados (meses, clima,
  DISCO/RED) siguen automáticamente el idioma del sistema (`i18n.py`).
- Config en JSON con sanitizado de rangos al cargar, **por usuario** en
  `~/.config/desktop-widgets/` (se siembra sola al primer arranque desde tu
  config previa o desde el `*.example.json`). La posición en pantalla la
  recuerda la extensión `desktop-widgets@yakko-chavez.github.io` (ver abajo),
  no la app.
- Modo `--debug` (o var. `RELOJ_DEBUG=1` / `AGENDA_DEBUG=1` / `CLIMA_DEBUG=1` /
  `SYSMON_DEBUG=1` / `CHRONO_DEBUG=1` / `CALC_DEBUG=1`): ventana decorada para
  permitir varias instancias.
- Autostart opcional copiando el `.desktop` a `~/.config/autostart/` (con la
  extensión activa no hace falta: ella lanza lo que falte).

## Requisitos

- Python 3.14, GTK 4.22, PyGObject, pycairo (ver `requirements.txt`).
- `psutil` solo para el Monitor (`pip install psutil` o `sudo apt install python3-psutil`).
- `nvidia-smi` opcional (si hay NVIDIA muestra GPU/VRAM reales, si no muestra N/A).
- Si falta algo: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-psutil`.

---

## 1. Reloj Diver (`reloj_widget.py`)

Reloj analógico de buceo: caja dorada con degradado radial, bisel negro con
marcas y números 10–50, esfera con lume, marca triangular genérica, textos
(`DIVER / AUTOMATIC / SUBMARINOS / 1000ft = 300m`), ventana de fecha a las 3
con lupa, manecillas Mercedes/hora/minuto/segundero y reflejo de cristal.

### Uso

```bash
python3 reloj_widget.py
# o
./reloj.sh
```

### Controles

- **Arrastrar** con botón izquierdo para mover (el compositor Wayland gestiona el move).
- **Click derecho**: menú (sweep/tick, bloquear, tamaño +/−, salir).
- **Doble click / tecla L**: bloquea o desbloquea (bloqueado = no arrastra ni abre menú).
- **+ / −**: cambia tamaño (100–600px). **Q / Esc**: salir.

### Config (`~/.config/desktop-widgets/config.json`)

```json
{ "size": 340, "sweep": true, "locked": false, "opacity": 1.0 }
```

- `sweep: true` = segundero suave (50ms), `false` = tick cada segundo.
- `size` se recorta a 100–600; la clave legacy `always_on_top` se ignora
  (Wayland no permite keep-above desde la app).

### Archivos

- `reloj_widget.py` — ventana, timer 50/1000ms, menú, drag.
- `reloj_draw.py` — `draw_diver(cr, w, h, hour, minute, second_float, day)`.
- `reloj.sh`, `reloj-widget.desktop`, `requirements.txt`. Config por usuario
  en `~/.config/desktop-widgets/config.json`.

---

## 2. Agenda de Lujo (`agenda_widget.py`)

Calendario de mes completo estilo agenda de cuero negro con filetes dorados,
marco dorado doble con remaches, header `MES AÑO` en Serif, semana `L–D`
(lunes primero, configurable), rejilla 6×7 con día actual en pastilla dorada,
domingos rojizos, días de otros meses atenuados y footer `Hoy · …`.
Vista navegable, solo fecha del sistema (sin eventos externos).

### Uso

```bash
python3 agenda_widget.py
# o
./run_agenda.sh
```

### Controles

- **Arrastrar** con botón izquierdo para mover (no arrastra desde las flechas ni el footer; bloqueado = no arrastra).
- **Botones dorados ‹ ›** en el header: click para mes anterior/siguiente (botones GTK reales sobre el dibujo, con glow dorado al pasar el mouse). **Click en el footer** ("Hoy · ..."): vuelve a hoy.
- **Click derecho**: menú (mes anterior/siguiente, ir a hoy, bloquear, tamaño, salir).
- **Doble click / tecla L**: bloquear clicks (aparece candadito dorado vectorial abajo-derecha).
- **← / →**: mes anterior/siguiente. **↑ / ↓**: año anterior/siguiente.
- **H / T**: volver a hoy. **+ / −**: tamaño (alto 100–800px). **Q / Esc**: salir.

### Config (`agenda_config.json`)

```json
{ "height": 600, "locked": false, "opacity": 1.0, "monday_first": true, "view_year": null, "view_month": null }
```

- `view_year/view_month: null` = seguir el mes actual del sistema.
- Al navegar se guardan el año/mes visibles; "Ir a hoy" los vuelve a `null`.
- `height` se recorta a 100–800 (ancho = alto × 0.70).

### Archivos

- `agenda_widget.py` — ventana, timer 30s, overlay, menú, drag, navegación.
- `agenda_draw.py` — `draw_agenda()`, `header_arrow_zones()`.
- `agenda_config.json`, `run_agenda.sh`, `agenda-widget.desktop`.

---

## 3. Clima Dorado (`clima_widget.py`)

Clima de Puebla (Open-Meteo, sin API key) estilo cuero negro + dorado a juego
con la Agenda. Iconos 100% vectoriales (sol, nube, lluvia, nieve, tormenta,
niebla). Tira de 5 días con máx/mín + detalles (sensación, humedad, viento).

### Uso

```bash
python3 clima_widget.py
# o
./run_clima.sh
```

### Controles

- **Arrastrar** botón izquierdo para mover. **Doble click / L**: bloquear.
- **Click derecho**: menú (Actualizar ahora, bloquear, tamaño, salir).
- **R**: forzar fetch. **+ / −**: alto 100–750px (ancho = alto × 0.62). **Q / Esc**: salir.

### Config (`clima_config.json`)

```json
{ "city": "Puebla", "lat": 19.04778, "lon": -98.20723, "height": 540, "locked": false, "opacity": 1.0 }
```

- Fetch cada 20 min en hilo + cache en `~/.cache/desktop-widgets/.clima_cache.json`
  (funciona offline, muestra "· sin conexión").
- Cambia `lat/lon/city` para otra ciudad y borra la cache o pulsa `R`.

### Archivos

- `clima_widget.py` — ventana, fetch Open-Meteo, cache, timer 60s.
- `clima_draw.py` — `draw_clima(cr, w, h, data, locked)`, `wmo_label()`.
- `clima_config.json` (por usuario), `run_clima.sh`, `clima-widget.desktop`.

---

## 4. Monitor Dorado (`sysmon_widget.py`)

Monitor apaisado con 6 diales (CPU, RAM, VRAM, GPU, DISCO, RED) + minis EFI/SWAP
y footer `load`. Aros dorados, ticks 270°, aguja y arco de valor.

### Uso

```bash
python3 sysmon_widget.py
# o
./run_sysmon.sh
```

### Controles

- **Arrastrar** botón izquierdo para mover. **Doble click / L**: bloquear.
- **Click derecho**: menú (bloquear, tamaño, salir).
- **+ / −**: alto 100–500px (ancho = alto × 2.7). **Q / Esc**: salir.

### Config (`sysmon_config.json`)

```json
{ "height": 320, "locked": false, "opacity": 1.0 }
```

- Requiere `psutil`. Sin `psutil` muestra `--` / `sin psutil`.
- Sin `nvidia-smi` muestra GPU/VRAM como `N/A`.
- RED con auto-escala de sesión (máximo visto = 100%).

### Archivos

- `sysmon_widget.py` — `collect()`, `net_rates()`, `query_nvidia()`, timer 1s.
- `sysmon_draw.py` — `draw_sysmon()`, `sysmon_layout()`.
- `sysmon_config.json`, `run_sysmon.sh`, `sysmon-widget.desktop`.

---

## 5. Cronógrafo Mecánico (`chrono_widget.py`)

Cronómetro estilo mecánico: aguja central de segundos con barrido suave,
subesferas de 30 minutos, 12 horas y décimas (1 vuelta = 1 s), ventana
digital `HH:MM:SS.D` y pushers START/STOP (aro verde/rojo según estado) y
RESET. Al cerrar se pierde la medición, por diseño.

### Uso

```bash
python3 chrono_widget.py
# o
./run_chrono.sh
```

### Controles

- **Pushers dorados** (botones GTK reales sobre el dibujo, como la Agenda):
  START/STOP arriba, RESET abajo (solo activo en pausa, como un mecánico real).
- **Arrastrar** botón izquierdo para mover. **Doble click / L**: bloquear
  (deshabilita pushers, aparece candadito dorado abajo-derecha).
- **Click derecho**: menú (Iniciar/Pausar, Reset, bloquear, tamaño, salir).
- **Espacio**: start/stop. **R**: reset. **+ / −**: tamaño (100–600px).
  **Q / Esc**: salir.

### Config (`chrono_config.json`)

```json
{ "size": 340, "locked": false, "opacity": 1.0 }
```

- Timer interno a 50 ms (`time.monotonic()`); el digital redondea a décimas
  desde el total (`format_elapsed()`), sin estado persistente.

### Archivos

- `chrono_widget.py` — estados (`toggle()`/`reset()`), timer 50ms, overlay, menú, drag.
- `chrono_draw.py` — `draw_chrono()`, `chrono_button_zones()`, `format_elapsed()`.
- `chrono_config.json`, `run_chrono.sh`, `chrono-widget.desktop`.

---

## 6. Calculadora Dorada (`calc_widget.py`)

Calculadora científica con memoria: caja cuadrada redondeada a juego con
Agenda/Clima, pantalla oscura con dígitos LUME y línea con la operación
pendiente, indicador `M` y modo `DEG`/`RAD`. Teclado 6×7 vectorial: memoria
(MC MR M− M+), científicas (sin cos tan ln log √ x² xʸ 1/x π e + DEG/RAD),
operadores dorados, `C` con aro rojo, `=` alto (2 filas) y `0` de ancho
completo. `%` = x/100; dominios inválidos (√ negativo, ÷0, tan 90°…) →
`Error`.

### Uso

```bash
python3 calc_widget.py
# o
./run_calc.sh
```

### Controles

- **Teclas del widget** (botones GTK reales con glow dorado al pasar el mouse).
- **Arrastrar** botón izquierdo para mover. **Doble click / L**: bloquear
  (teclas insensibles, candadito dorado arriba-derecha).
- **Click derecho**: menú (bloquear, tamaño, salir).
- **Teclado físico**: `0-9 . + - * /`, `Enter`/`=`, `Backspace`,
  `c`/`Delete` = C, `m` = MR. **Q / Esc**: salir.
- Nota: `+`/`−` no redimensionan aquí (son operadores); el tamaño va por
  menú o Configuración.

### Config (`calc_config.json`)

```json
{ "size": 440, "locked": false, "opacity": 1.0, "angle": "DEG" }
```

- `size` se recorta a 300–700; `angle` = `DEG`/`RAD` (trigonometricas).
- Sin estado persistente (ni memoria `M`).

### Archivos

- `calc_widget.py` — `CalcEngine` científico (puro, testeable), overlay de
  teclas, menú, drag.
- `calc_draw.py` — `draw_calc()`, `calc_button_zones()`, `KEY_GRID`.
- `calc_config.json`, `run_calc.sh`, `calc-widget.desktop`.

---

## Lanzador + "siempre atrás" + memoria de posición (extensión GNOME Shell)

Wayland no deja a una app ponerse debajo sola ni recordar su posición. La
extensión `desktop-widgets@yakko-chavez.github.io` (fuente en
`gnome-extension/`) **lanza sola los 6 widgets** al activarse —solo los que no
estén ya corriendo: si los abres por lanzador o autostart, simplemente los
adopta—, los mantiene al fondo de la pila (`lower()`), visibles en todos los
escritorios (`stick()`) y **restaura la última posición** de cada uno al abrirlo
(estado en `~/.config/desktop-widgets/positions.json`).

Instalación local (solo la primera vez; GNOME detecta extensiones nuevas al iniciar sesión):

```bash
./gnome-extension/install-extension.sh
# 1. Cierra sesión y vuelve a entrar (obligatorio en Wayland)
# 2. Luego:
gnome-extensions enable desktop-widgets@yakko-chavez.github.io
```

Para desactivar: `gnome-extensions disable desktop-widgets@yakko-chavez.github.io`.
Al desactivarse termina los procesos que ella lanzó; los que abriste por tu
cuenta siguen corriendo.

**Preferencias**: desde el Gestor de Extensiones (o
`gnome-extensions prefs desktop-widgets@yakko-chavez.github.io`) eliges con
interruptores qué widgets lanza la extensión al activarse.

Límites: queda debajo de las ventanas pero encima del wallpaper (no es fondo
real). Activa "Bloquear clicks" (doble-click o tecla `L`) para que no estorbe
al hacer clic en el escritorio.

## Publicar en extensions.gnome.org (EGO)

El zip que espera EGO se genera con:

```bash
bash gnome-extension/package.sh   # -> desktop-widgets@yakko-chavez.github.io.zip
```

Pasos:

1. Push del repo a `https://github.com/Yakko-Chavez/Linux_Widgets` (público).
2. Cuenta en `gitlab.gnome.org` y entra con ella en `https://extensions.gnome.org`.
3. Sube el zip en `https://extensions.gnome.org/upload/`. Revisa antes las
   [reglas de revisión](https://gjs.guide/extensions/review-guidelines/review-guidelines.html):
   sin marcas registradas, scripts con licencia OSI (aquí MIT), procesos que
   salen limpios, `metadata.json` bien formado y sin archivos innecesarios.
4. **Screenshot** (la foto que muestra el Gestor de Extensiones): con los
   widgets en pantalla pulsa `PrtScn` y recorta la zona; en la página de tu
   extensión en EGO usa "Upload screenshot" para subir ese PNG/JPG.
5. Atiende los comentarios de la revisión y vuelve a subir si te lo piden.

El UUID (`desktop-widgets@yakko-chavez.github.io`) es la identidad permanente
de la extensión en EGO: no lo cambies después de publicar.

## Autostart en GNOME (opcional, sin extensión)

```bash
cp reloj-widget.desktop agenda-widget.desktop clima-widget.desktop sysmon-widget.desktop chrono-widget.desktop calc-widget.desktop ~/.config/autostart/
```

(Revisa que `Exec=` apunte a tu ruta real; los `*-widget-local.desktop` ya la
llevan corregida.)

## Solución de problemas

- **No veo la ventana**: buscar `Reloj Diver` / `Agenda de Lujo` / `Clima Dorado` /
  `Monitor Dorado` / `Cronógrafo Mecánico` / `Calculadora Dorada` con `Alt+Tab` o
  en Activities/Overview; probar con `--debug`.
- **Parece "muerto" (no responde)**: está bloqueado — doble-click o tecla `L`.
  Agenda/Clima/Sysmon/Chrono muestran candadito dorado cuando están bloqueados
  (la Calculadora arriba-derecha).
- **Logs**: imprimen a stdout (`[reloj]…` / `[agenda]…` / `[clima]…` / `[sysmon]…` / `[chrono]…` / `[calc]…`).
- **La extensión no lanza nada**: mira los logs de gnome-shell
  (`journalctl --user -u org.gnome.Shell@wayland.service | grep desktop-widgets`)
  y confirma `python3-gi`, `gir1.2-gtk-4.0` y `python3-cairo`.
- **Clima siempre offline**: revisa internet / `python3 -c "import urllib.request; print(urllib.request.urlopen('https://api.open-meteo.com/v1/forecast?latitude=19&longitude=-98&current=temperature_2m').status)"`.
- **Sysmon en `--`**: `pip install psutil` o `sudo apt install python3-psutil`.
