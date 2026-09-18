# Widgets de escritorio — Wayland + GNOME

Reloj Rolex Submariner, Agenda de Lujo, Clima Dorado, Monitor Dorado y
Cronógrafo Mecánico: ventanas GTK4 flotantes, sin bordes, dibujadas 100%
en vectorial con Cairo. Sin imágenes externas.

> Nota Wayland/GNOME: `gtk-layer-shell` **no funciona en GNOME**. Son ventanas
> GTK4 sin decoración, transparentes, que no roban foco. No quedan como fondo
> real detrás del wallpaper, pero sí flotantes siempre visibles.

## Filosofía común (todos los widgets)

- Render en memoria: `pycairo` (ARGB32) → `Gtk.Picture` vía `Gdk.MemoryTexture`
  (`B8G8R8A8_PREMULTIPLIED`). Sin archivos temporales, sin `python3-gi-cairo`.
- Nitidez HiDPI con escala ×2.
- Movimiento por protocolo Wayland (`surface.begin_move()`); en GNOME también
  vale `Super + arrastrar`.
- Doble-click / tecla `L`: bloquear (sin arrastre, sin menú, sin botones).
  Agenda/Clima/Sysmon/Chrono dibujan candadito dorado vectorial abajo-derecha.
- Click derecho: menú contextual. `+ / −`: tamaño. `Q / Esc`: salir.
- Config en JSON con sanitizado de rangos al cargar. La posición en pantalla
  la recuerda la extensión `rolex-below@local`, no la app.
- Autostart copiando el `.desktop` a `~/.config/autostart/`.
- La extensión `rolex-below@local` (fuente en `gnome-extension/`, instalar con
  `./gnome-extension/install-extension.sh` + cerrar sesión + `gnome-extensions
  enable rolex-below@local`) los mantiene al fondo de la pila, visibles en
  todos los escritorios (`lower()` + `stick()`) y **restaura su última
  posición** (`~/.config/desktop-widgets/positions.json`).

## Requisitos

- Python 3.14, GTK 4.22, PyGObject, pycairo (ver `requirements.txt`).
- `psutil` para el Monitor (`pip install psutil`).
- `nvidia-smi` opcional para GPU/VRAM reales.
- Si falta algo: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-psutil`.

---

## 1. Rolex Submariner (`rolex_widget.py`)

Reloj analógico estilo Submariner: caja dorada con degradado radial, bisel
negro con marcas y números 10–50, esfera con lume, coronita, textos
(`ROLEX / OYSTER PERPETUAL / SUBMARINER / 1000ft = 300m`), ventana de fecha a
las 3 con lupa, manecillas Mercedes/hora/minuto/segundero y reflejo de cristal.

### Uso

```bash
python3 rolex_widget.py
# o
./rolex.sh
```

### Controles

| Acción | Efecto |
|---|---|
| Arrastrar (botón izq.) | Mover (Wayland gestiona el move; bloqueado = no mueve) |
| Click derecho | Menú: sweep, bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear / desbloquear clicks |
| `+` / `−` | Tamaño 100–600 px |
| `Q` / `Esc` | Salir |

### Config (`config.json`)

```json
{ "size": 340, "sweep": true, "locked": false, "opacity": 1.0 }
```

- `sweep: true` = segundero suave (50 ms); `false` = tick cada segundo.
- `size` se recorta a 100–600; la clave legacy `always_on_top` se ignora
  (Wayland no permite keep-above desde la app).

### Archivos

- `rolex_widget.py` — ventana, timer 50/1000 ms, menú, drag.
  Función clave: `render_texture(size)`; clase `RolexWidget(Gtk.Application)`.
- `rolex_draw.py` — `draw_rolex(cr, w, h, hour, minute, second_float, day)`.
- `config.json`, `rolex.sh`, `rolex-widget.desktop`, `requirements.txt`.

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
  `.clima_cache.json`. Sin red muestra `· sin conexión` con último cache.
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
- `clima_config.json`, `.clima_cache.json`, `run_clima.sh`, `clima-widget.desktop`.

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

## Autostart en GNOME

```bash
cp rolex-widget.desktop agenda-widget.desktop clima-widget.desktop sysmon-widget.desktop chrono-widget.desktop ~/.config/autostart/
```

(Revisar que `Exec=` apunte a la ruta real.)

## Solución de problemas

- **No veo la ventana**: buscar `Rolex Submariner` / `Agenda de Lujo` / `Clima Dorado` /
  `Monitor Dorado` / `Cronógrafo Mecánico` con `Alt+Tab` o en Activities/Overview; probar con `--debug`.
- **Parece "muerto" (no responde)**: está bloqueado — doble-click o tecla `L`.
  Agenda/Clima/Sysmon/Chrono muestran candadito dorado vectorial cuando están bloqueados.
- **Logs**: todos imprimen a stdout (`[rolex]…` / `[agenda] vista -> …` / `[clima]…` / `[sysmon]…` / `[chrono]…`).
- **Clima offline**: ver cache `.clima_cache.json` y probar URL Open-Meteo manual.
- **Sysmon sin datos**: instalar `psutil`; para GPU instalar driver NVIDIA + `nvidia-smi`.
