# Widgets de escritorio — Wayland + GNOME

Reloj Diver, Agenda de Lujo, Clima Dorado, Monitor Dorado, Cronógrafo
Mecánico y Calculadora Dorada: ventanas GTK4 flotantes, sin bordes, dibujadas
100% en vectorial con Cairo. Sin imágenes externas y sin marcas registradas.

> Nota Wayland/GNOME: `gtk-layer-shell` **no funciona en GNOME**. Son ventanas
> GTK4 sin decoración, transparentes, que no roban foco. No quedan como fondo
> real detrás del wallpaper, pero sí flotantes siempre visibles.

## Filosofía común (todos los widgets)

- Render en memoria: `pycairo` (ARGB32) → `Gtk.Picture` vía `Gdk.MemoryTexture`
  (`B8G8R8A8_PREMULTIPLIED`). Sin archivos temporales, sin `python3-gi-cairo`.
- Buffer = tamaño lógico × escala real del monitor (`widget_scale()`): la
  ventana mide lo configurado en x1 y se ve nítida en HiDPI.
- Infraestructura común en `widget_base.py` (config, render, ventana, gestos,
  menú, bloqueo, teclas).
- Movimiento por protocolo Wayland (`surface.begin_move()`); en GNOME también
  vale `Super + arrastrar`.
- Doble-click / tecla `L`: bloquear (sin arrastre, sin menú, sin botones).
  Agenda/Clima/Sysmon/Chrono dibujan candadito dorado vectorial abajo-derecha;
  la Calculadora arriba-derecha.
- Click derecho: menú contextual. `+ / −`: tamaño. `Q / Esc`: salir.
  "Configuración…" abre un diálogo (GTK, `WB.settings_dialog()`) para
  tamaño/alto, opacidad y opciones propias (sweep, ciudad/lat/lon, lunes primero).
- **Idiomas ES/EN** (`i18n.py`, sin gettext): claves en inglés + diccionario
  "es"; el idioma se detecta de `LANGUAGE`/`LC_ALL`/`LANG` del sistema. Menús,
  diálogos y textos dibujados (meses/días de agenda, descripciones WMO del
  clima, DISCO/RED de sysmon) quedan cubiertos.
- Config en JSON con sanitizado de rangos al cargar, **por usuario** en
  `~/.config/desktop-widgets/` (se siembra sola al primer arranque desde la
  config previa o el `*.example.json`). La posición en pantalla
  la recuerda la extensión `desktop-widgets@yakko-chavez.github.io`, no la app.
- Autostart opcional con el `.desktop` en `~/.config/autostart/` (con la
  extensión activa no hace falta).
- La extensión `desktop-widgets@yakko-chavez.github.io` (fuente en
  `gnome-extension/`, instalar con
  `./gnome-extension/install-extension.sh` + cerrar sesión + `gnome-extensions
  enable desktop-widgets@yakko-chavez.github.io`) **lanza sola los widgets que
  falten** (los ya corriendo los adopta), los mantiene al fondo de la pila,
  visibles en todos los escritorios (`lower()` + `stick()`) y **restaura su
  última posición** (`~/.config/desktop-widgets/positions.json`). Preferencias
  de la extensión (qué widgets lanzar, schema GSettings
  `org.gnome.shell.extensions.desktop-widgets` + `prefs.js`): botón de
  engranaje en el Gestor de Extensiones o
  `gnome-extensions prefs desktop-widgets@yakko-chavez.github.io`.
  Empaquetado para EGO: `bash gnome-extension/package.sh`.

## Requisitos

- Python 3.14, GTK 4.22, PyGObject, pycairo (ver `requirements.txt`).
- `psutil` para el Monitor (`pip install psutil`).
- `nvidia-smi` opcional para GPU/VRAM reales.
- Si falta algo: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-psutil`.

---

## 1. Reloj Diver (`reloj_widget.py`)

Reloj analógico de buceo: caja dorada con degradado radial, bisel
negro con marcas y números 10–50, esfera con lume, marca triangular genérica,
textos (`DIVER / AUTOMATIC / SUBMARINOS / 1000ft = 300m`), ventana de fecha a
las 3 con lupa, manecillas Mercedes/hora/minuto/segundero y reflejo de cristal.

### Uso

```bash
python3 reloj_widget.py
# o
./reloj.sh
```

### Controles

| Acción | Efecto |
|---|---|
| Arrastrar (botón izq.) | Mover (Wayland gestiona el move; bloqueado = no mueve) |
| Click derecho | Menú: sweep, bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear / desbloquear clicks |
| `+` / `−` | Tamaño 100–600 px |
| `Q` / `Esc` | Salir |

### Config (`~/.config/desktop-widgets/config.json`)

```json
{ "size": 340, "sweep": true, "locked": false, "opacity": 1.0 }
```

- `sweep: true` = segundero suave (50 ms); `false` = tick cada segundo.
- `size` se recorta a 100–600; la clave legacy `always_on_top` se ignora
  (Wayland no permite keep-above desde la app).

### Archivos

- `reloj_widget.py` — ventana, timer 50/1000 ms, menú, drag.
  Función clave: `render_texture(size, scale)`; clase `RelojWidget(Gtk.Application)`.
- `reloj_draw.py` — `draw_diver(cr, w, h, hour, minute, second_float, day)`.
- `reloj.sh`, `reloj-widget.desktop`, `requirements.txt`; config por usuario
  en `~/.config/desktop-widgets/config.json`.

---

## 2. Agenda de Lujo (`agenda_widget.py`)

Calendario de mes completo estilo agenda de cuero negro con filetes dorados:
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

| Acción | Efecto |
|---|---|
| Arrastrar (botón izq.) | Mover (no arrastra desde flechas ni footer; bloqueado = no mueve) |
| Botones dorados `‹` `›` | Mes anterior / siguiente (botones GTK reales, glow en hover) |
| Click en footer (`Hoy · …`) | Volver al mes actual |
| Click derecho | Menú: mes ±, ir a hoy, bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear (aparece candadito dorado vectorial abajo-derecha) |
| `←` / `→` | Mes anterior / siguiente |
| `↑` / `↓` | Año anterior / siguiente |
| `H` / `T` | Volver a hoy |
| `+` / `−` | Alto 100–800 px (ancho = alto × 0.70) |
| `Q` / `Esc` | Salir |

### Config (`agenda_config.json`)

```json
{ "height": 600, "locked": false, "opacity": 1.0, "monday_first": true, "view_year": null, "view_month": null }
```

- `view_year/view_month: null` = seguir el mes actual; al navegar se guardan,
  "Ir a hoy" los devuelve a `null`.
- `height` se recorta a 100–800.
- Timer de refresco cada 30 s (el calendario no necesita más) + redibujado
  inmediato al navegar, redimensionar o (des)bloquear.

### Detalles de implementación

- `Gtk.Overlay`: `Gtk.Picture` como hijo + 3 `Gtk.Button` transparentes
  (clase `flat` + CSS `button.nav`) posicionados por `_layout_nav()` con la
  geometría de `header_arrow_zones()` de `agenda_draw.py`. Sin hit-testing por
  coordenadas: GTK entrega el click directo.
- `draw_agenda(cr, w, h, year, month, today_ymd, monday_first=True, locked=False)`
  dibuja todo, incluido el candado de bloqueo y los botones `‹ ›`
  (con `new_sub_path()` antes de cada arco para evitar líneas fantasma Cairo).

### Archivos

- `agenda_widget.py` — ventana, timer 30 s, overlay, menú, drag, navegación.
  Clases/funciones clave: `AgendaWidget`, `current_view()`, `render_texture()`.
- `agenda_draw.py` — `draw_agenda()`, `header_arrow_zones()`.
- `agenda_config.json`, `run_agenda.sh`, `agenda-widget.desktop`.

---

## 3. Clima Dorado (`clima_widget.py`)

Clima de Puebla vía Open-Meteo (sin key): ciudad + icono vectorial grande +
temperatura + descripción WMO + detalles (sensación/humedad/viento) + tira de
5 días (máx/mín) + footer de actualización. Estilo cuero negro + dorado.

### Uso

```bash
python3 clima_widget.py
# o
./run_clima.sh
```

### Controles

| Acción | Efecto |
|---|---|
| Arrastrar (botón izq.) | Mover (bloqueado = no mueve) |
| Click derecho | Menú: actualizar ahora, bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear (candadito vectorial) |
| `R` | Forzar fetch Open-Meteo |
| `+` / `−` | Alto 100–750 px (ancho = alto × 0.62) |
| `Q` / `Esc` | Salir |

### Config (`clima_config.json`)

```json
{ "city": "Puebla", "lat": 19.04778, "lon": -98.20723, "height": 540, "locked": false, "opacity": 1.0 }
```

- `height` 100–750. Fetch en hilo cada 20 min (`FETCH_EVERY`) + cache en
  `~/.cache/desktop-widgets/.clima_cache.json`. Sin red muestra `· sin conexión` con último cache.
- `current_data()` sin fetch fresco marca `offline=True` para no fingir frescura.

### Detalles de implementación

- `fetch_weather()` con `urllib` + `User-Agent`; `parse_payload()` extrae
  `current` + 5 días siguientes (`daily time/weather_code/max/min`).
- `refresh_data_async(cfg, on_done)`: hilo daemon + `GLib.idle_add(on_done)`,
  flag `_state["fetching"]` para no solapar.
- `draw_clima(cr, w, h, data, locked)`: iconos por código WMO (`_draw_icon`),
  tira anclada abajo para no dejar hueco.

### Archivos

- `clima_widget.py` — `fetch_weather()`, `parse_payload()`, `current_data()`.
- `clima_draw.py` — `draw_clima()`, `wmo_label()`.
- `clima_config.json` (por usuario), `run_clima.sh`, `clima-widget.desktop`.

---

## 4. Monitor Dorado (`sysmon_widget.py`)

Monitor apaisado 6 diales en horizontal: CPU, RAM, VRAM, GPU, DISCO, RED +
minis EFI/SWAP + footer `load`. Requiere `psutil`; GPU/VRAM vía `nvidia-smi`
(cache 2 s), si no hay muestra `N/A`.

### Uso

```bash
python3 sysmon_widget.py
# o
./run_sysmon.sh
```

### Controles

| Acción | Efecto |
|---|---|
| Arrastrar (botón izq.) | Mover (bloqueado = no mueve) |
| Click derecho | Menú: bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear (candadito vectorial) |
| `+` / `−` | Alto 100–500 px (ancho = alto × 2.7) |
| `Q` / `Esc` | Salir |

### Config (`sysmon_config.json`)

```json
{ "height": 320, "locked": false, "opacity": 1.0 }
```

- `height` 100–500. Timer 1 s (`restart_timer`).
- `net_rates()`: derivada de `psutil.net_io_counters()` con auto-escala
  (`max` de sesión = 100%).
- `cpu_temp()`: busca `k10temp/coretemp/zenpower/acpitz`.

### Detalles de implementación

- `collect()` junta el dict que espera `draw_sysmon()`: `dials[6]` + `minis[2]`.
- `sysmon_layout(w,h)`: `title_y`, 6 centros `dials_xy`, radio `r = min(w*0.068, area_h*0.27)`.
- `_draw_dial()`: aro dorado radial + ticks 270° (135°→405°) + arco valor con
  gradiente + aguja + textos `main/sub` fuera del dial.

### Archivos

- `sysmon_widget.py` — `collect()`, `net_rates()`, `query_nvidia()`, `cpu_temp()`.
- `sysmon_draw.py` — `draw_sysmon()`, `sysmon_layout()`.
- `sysmon_config.json`, `run_sysmon.sh`, `sysmon-widget.desktop`.

---

## 5. Cronógrafo Mecánico (`chrono_widget.py`)

Cronómetro estilo mecánico: aguja central de segundos (barrido 0–60),
subesferas de 30 min / 12 h / décimas (1 vuelta = 1 s), ventana digital
`HH:MM:SS.D` y pushers START/STOP (aro verde en pausa, rojo en marcha) y
RESET (solo en pausa). Al cerrar se pierde la medición.

### Uso

```bash
python3 chrono_widget.py
# o
./run_chrono.sh
```

### Controles

| Acción | Efecto |
|---|---|
| Pushers dorados | START/STOP y RESET (botones GTK reales sobre el dibujo) |
| Arrastrar (botón izq.) | Mover (bloqueado = no mueve) |
| Click derecho | Menú: iniciar/pausar, reset, bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear (candadito vectorial, pushers deshabilitados) |
| `Espacio` | Start / stop |
| `R` | Reset (solo en pausa) |
| `+` / `−` | Tamaño 100–600 px |
| `Q` / `Esc` | Salir |

### Config (`chrono_config.json`)

```json
{ "size": 340, "locked": false, "opacity": 1.0 }
```

- Timer a 50 ms con `time.monotonic()`; sin estado persistente.

### Detalles de implementación

- `toggle()` / `reset()` / `elapsed_now()` puros (testeables sin GUI);
  `refresh()` no hace nada si aún no hay ventana.
- `Gtk.Overlay` + 2 `Gtk.Button` transparentes (clase `go`) posicionados por
  `_layout_buttons()` con `chrono_button_zones()` de `chrono_draw.py`.
- `draw_chrono(cr, w, h, elapsed_s, running, locked)`; geometría de pushers
  compartida en `_geometry()` para que dibujo y botones coincidan.

### Archivos

- `chrono_widget.py` — estados, timer 50 ms, overlay, menú, drag.
- `chrono_draw.py` — `draw_chrono()`, `chrono_button_zones()`, `format_elapsed()`.
- `chrono_config.json`, `run_chrono.sh`, `chrono-widget.desktop`.

---

## 6. Calculadora Dorada (`calc_widget.py`)

Calculadora científica con memoria: caja cuadrada redondeada a juego con
Agenda/Clima (filetes y remaches dorados), pantalla oscura con dígitos LUME,
línea pequeña con la operación pendiente, indicador `M` de memoria y modo
`DEG`/`RAD`. Teclado 6×7 dibujado en vectorial: memoria (MC MR M− M+),
científicas (sin cos tan ln log, √ x² xʸ 1/x π e, conmutador DEG/RAD),
operadores con filete dorado, `C` con aro rojo, `=` dorado sólido que ocupa
2 filas y `0` de ancho completo. `%` = x/100; divisiones/raíces/dominios
inválidos (√ de negativo, log de 0, tan 90°…) muestran `Error` (se limpia
con `C`).

### Uso

```bash
python3 calc_widget.py
# o
./run_calc.sh
```

### Controles

| Acción | Efecto |
|---|---|
| Teclas del widget | Botones GTK reales sobre el dibujo (glow dorado en hover) |
| Arrastrar (botón izq.) | Mover (bloqueado = no mueve) |
| Click derecho | Menú: bloquear, tamaño ±, salir |
| Doble-click / `L` | Bloquear (candadito vectorial arriba-derecha, teclas insensibles) |
| `0-9` `.` `+ - * /` | Dígitos y operadores (teclado físico) |
| `Enter` / `=` | Resultado (`=` encadena) |
| `Backspace` | Borrar último dígito |
| `c` / `Delete` | C (limpiar todo) |
| `m` | MR (recuperar memoria) |
| `Q` / `Esc` | Salir |

Las teclas científicas (sin/cos/tan/ln/log/√/x²/xʸ/1/x/π/e/DEG) van por
click; `DEG` conmuta grados/radianes y la tecla siempre muestra el modo
actual (la pantalla también lo indica). Nota: a diferencia del resto de la
colección, `+`/`−` no redimensionan aquí (son operadores); el tamaño va por
menú o Configuración.

### Config (`calc_config.json`)

```json
{ "size": 440, "locked": false, "opacity": 1.0, "angle": "DEG" }
```

- `size` se recorta a 300–700; `angle` es `DEG` o `RAD` (trigonometricas).
- Sin estado persistente de cálculo: al cerrar se pierde la operación y la
  memoria `M`.

### Detalles de implementación

- `CalcEngine` puro (sin GTK, testeable): `entry/acc/op/fresh/memory` +
  `format_number()` que recorta artefactos float (`0.1+0.2 → 0.3`) y snap a
  cero de residuos < 1e-10 (`sin(π)` en RAD no muestra `-0`).
- Las funciones unarias operan sobre el display y respetan el operador
  pendiente: `5 + √(25) =` da `10`.
- `Gtk.Overlay` + 36 `Gtk.Button` transparentes (clase `key`) posicionados
  por `_layout_buttons()` con `calc_button_zones()` de `calc_draw.py`; el
  hueco entre teclas también es clickeable (zonas crecidas medio gap).
- `draw_calc(cr, w, h, display, sub_display, has_memory, locked, angle_mode)`;
  geometría del teclado compartida en `_keypad_geometry()` para que dibujo y
  botones coincidan. Fuente `DejaVu Sans` explícita: la `Sans` genérica
  (Noto) no trae `−` (U+2212), `⌫` (U+232B) ni `ʸ` (U+02B8).

### Archivos

- `calc_widget.py` — `CalcEngine`, overlay de teclas, menú, drag.
- `calc_draw.py` — `draw_calc()`, `calc_button_zones()`, `KEY_GRID`.
- `calc_config.json`, `run_calc.sh`, `calc-widget.desktop`.

---

## Autostart en GNOME

```bash
cp reloj-widget.desktop agenda-widget.desktop clima-widget.desktop sysmon-widget.desktop chrono-widget.desktop calc-widget.desktop ~/.config/autostart/
```

(Revisar que `Exec=` apunte a la ruta real.)

## Solución de problemas

- **No veo la ventana**: buscar `Reloj Diver` / `Agenda de Lujo` / `Clima Dorado` /
  `Monitor Dorado` / `Cronógrafo Mecánico` / `Calculadora Dorada` con `Alt+Tab` o
  en Activities/Overview; probar con `--debug`.
- **Parece "muerto" (no responde)**: está bloqueado — doble-click o tecla `L`.
  Agenda/Clima/Sysmon/Chrono muestran candadito dorado vectorial cuando están
  bloqueados (la Calculadora arriba-derecha).
- **Logs**: todos imprimen a stdout (`[reloj]…` / `[agenda] vista -> …` / `[clima]…` / `[sysmon]…` / `[chrono]…` / `[calc]…`).
- **Clima offline**: ver cache `~/.cache/desktop-widgets/.clima_cache.json` y probar URL Open-Meteo manual.
- **Sysmon sin datos**: instalar `psutil`; para GPU instalar driver NVIDIA + `nvidia-smi`.
