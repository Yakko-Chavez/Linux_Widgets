# Widgets de escritorio para Wayland (Ubuntu + GNOME)

Rolex Submariner, Agenda de Lujo, Clima Dorado y Monitor Dorado: ventanas GTK4
flotantes, sin bordes, dibujadas 100% en vectorial con Cairo. Sin imágenes externas.

> Nota Wayland/GNOME: `gtk-layer-shell` **no funciona en GNOME**. Son ventanas
> GTK4 sin decoración, transparentes, que no roban foco. No quedan como fondo
> real detrás del wallpaper, pero sí flotantes siempre visibles.

## Filosofía común

- Render en memoria: `pycairo` (ARGB32) → `Gtk.Picture` vía `Gdk.MemoryTexture`
  (`B8G8R8A8_PREMULTIPLIED`). Sin archivos temporales, sin `python3-gi-cairo`.
- Nitidez HiDPI con escala ×2.
- Movimiento por protocolo Wayland (`surface.begin_move()`); en GNOME también
  vale `Super + arrastrar`.
- Doble-click / tecla `L`: bloquear (sin arrastre, sin menú; aparece candadito
  dorado vectorial abajo-derecha en Agenda/Clima/Sysmon).
- Click derecho: menú contextual. `+ / −`: tamaño. `Q / Esc`: salir.
- Config en JSON con sanitizado de rangos al cargar + posición `x,y` guardada.
- Modo `--debug` (o var. `ROLEX_DEBUG=1` / `AGENDA_DEBUG=1` / `CLIMA_DEBUG=1` /
  `SYSMON_DEBUG=1`): ventana decorada para permitir varias instancias.
- Autostart copiando el `.desktop` a `~/.config/autostart/`.

## Requisitos

- Python 3.14, GTK 4.22, PyGObject, pycairo (ver `requirements.txt`).
- `psutil` solo para el Monitor (`pip install psutil` o `sudo apt install python3-psutil`).
- `nvidia-smi` opcional (si hay NVIDIA muestra GPU/VRAM reales, si no muestra N/A).
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

- **Arrastrar** con botón izquierdo para mover (el compositor Wayland gestiona el move).
- **Click derecho**: menú (sweep/tick, bloquear, tamaño +/−, salir).
- **Doble click / tecla L**: bloquea o desbloquea (bloqueado = no arrastra ni abre menú).
- **+ / −**: cambia tamaño (100–600px). **Q / Esc**: salir.

### Config (`config.json`)

```json
{ "size": 340, "sweep": true, "locked": false, "opacity": 1.0 }
```

- `sweep: true` = segundero suave (50ms), `false` = tick cada segundo.
- `size` se recorta a 100–600; la clave legacy `always_on_top` se ignora
  (Wayland no permite keep-above desde la app).

### Archivos

- `rolex_widget.py` — ventana, timer 50/1000ms, menú, drag.
- `rolex_draw.py` — `draw_rolex(cr, w, h, hour, minute, second_float, day)`.
- `config.json`, `rolex.sh`, `rolex-widget.desktop`, `requirements.txt`.

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

- Fetch cada 20 min en hilo + cache en `.clima_cache.json` (funciona offline,
  muestra "· sin conexión").
- Cambia `lat/lon/city` para otra ciudad y borra `.clima_cache.json` o pulsa `R`.

### Archivos

- `clima_widget.py` — ventana, fetch Open-Meteo, cache, timer 60s.
- `clima_draw.py` — `draw_clima(cr, w, h, data, locked)`, `wmo_label()`.
- `clima_config.json`, `.clima_cache.json`, `run_clima.sh`, `clima-widget.desktop`.

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

## Modo "siempre atrás" (extensión GNOME Shell)

Wayland no deja a una app ponerse debajo sola. La extensión `rolex-below@local`
(ya creada en `~/.local/share/gnome-shell/extensions/`) mantiene los relojes al
fondo de la pila (`lower()`) y visibles en todos los escritorios (`stick()`).

Activación (solo la primera vez, GNOME detecta extensiones nuevas al iniciar sesión):

```bash
# 1. Cierra sesión y vuelve a entrar (obligatorio en Wayland)
# 2. Luego:
gnome-extensions enable rolex-below@local
python3 rolex_widget.py
```

Para desactivar: `gnome-extensions disable rolex-below@local`.

Límites: queda debajo de las ventanas pero encima del wallpaper (no es fondo
real). Activa "Bloquear clicks" (doble-click o tecla `L`) para que no estorbe
al hacer clic en el escritorio.

## Autostart en GNOME

```bash
cp rolex-widget.desktop agenda-widget.desktop clima-widget.desktop sysmon-widget.desktop ~/.config/autostart/
```

(Revisa que `Exec=` apunte a tu ruta real.)

## Solución de problemas

- **No veo la ventana**: buscar `Rolex Submariner` / `Agenda de Lujo` / `Clima Dorado` /
  `Monitor Dorado` con `Alt+Tab` o en Activities/Overview; probar con `--debug`.
- **Parece "muerto" (no responde)**: está bloqueado — doble-click o tecla `L`.
  Agenda/Clima/Sysmon muestran candadito dorado cuando están bloqueados.
- **Logs**: imprimen a stdout (`[rolex]…` / `[agenda]…` / `[clima]…` / `[sysmon]…`).
- **Clima siempre offline**: revisa internet / `python3 -c "import urllib.request; print(urllib.request.urlopen('https://api.open-meteo.com/v1/forecast?latitude=19&longitude=-98&current=temperature_2m').status)"`.
- **Sysmon en `--`**: `pip install psutil` o `sudo apt install python3-psutil`.
