# Widgets de escritorio — Wayland + GNOME

Reloj Rolex Submariner y Agenda de Lujo: ventanas GTK4 flotantes, sin bordes,
dibujadas 100% en vectorial con Cairo. Sin imágenes externas.

> Nota Wayland/GNOME: `gtk-layer-shell` **no funciona en GNOME**. Son ventanas
> GTK4 sin decoración, transparentes, que no roban foco. No quedan como fondo
> real detrás del wallpaper, pero sí flotantes siempre visibles.

## Filosofía común (ambos widgets)

- Render en memoria: `pycairo` (ARGB32) → `Gtk.Picture` vía `Gdk.MemoryTexture`
  (`B8G8R8A8_PREMULTIPLIED`). Sin archivos temporales, sin `python3-gi-cairo`.
- Nitidez HiDPI con escala ×2.
- Movimiento por protocolo Wayland (`surface.begin_move()`); en GNOME también
  vale `Super + arrastrar`.
- Doble-click / tecla `L`: bloquear (sin arrastre, sin menú, sin botones).
- Click derecho: menú contextual. `+ / −`: tamaño. `Q / Esc`: salir.
- Config en JSON con sanitizado de rangos al cargar.
- Modo `--debug` (o var. `ROLEX_DEBUG=1` / `AGENDA_DEBUG=1`): ventana decorada
  y con borde para permitir varias instancias.
- Autostart copiando el `.desktop` a `~/.config/autostart/`.
- Compatibles con la extensión `rolex-below@local`
  (`~/.local/share/gnome-shell/extensions/`), que los mantiene al fondo de la
  pila y visibles en todos los escritorios (`lower()` + `stick()`). Requiere
  cerrar sesión una vez tras instalarla y luego
  `gnome-extensions enable rolex-below@local`.

## Requisitos

- Python 3.14, GTK 4.22, PyGObject, pycairo (ver `requirements.txt`).
- Si falta algo: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0`.

---

## 1. Rolex Submariner (`rolex_widget.py`)

Reloj analógico estilo Submariner: caja de acero con degradado radial, bisel
negro con marcas y números 10–50, esfera con lume, coronita, textos
(`ROLEX / OYSTER PERPETUAL / SUBMARINER / 1000ft = 300m`), ventana de fecha a
las 3 con lupa, manecillas Mercedes/hora/minuto/segundero y reflejo de cristal.

### Uso

```bash
python3 rolex_widget.py
# o
./run.sh
```

### Controles

| Acción | Efecto |
|---|---|
| Arrastrar (botón izq.) | Mover (Wayland gestiona el move) |
| Click derecho | Menú: sweep, bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear / desbloquear clicks |
| `+` / `−` | Tamaño 200–600 px |
| `Q` / `Esc` | Salir |

### Config (`config.json`)

```json
{ "size": 340, "sweep": true, "locked": false, "opacity": 1.0 }
```

- `sweep: true` = segundero suave (50 ms); `false` = tick cada segundo.
- `size` se recorta a 200–600; la clave legacy `always_on_top` se ignora
  (Wayland no permite keep-above desde la app).

### Archivos

- `rolex_widget.py` — ventana, timer 50/1000 ms, menú, drag.
  Función clave: `render_texture(size)`; clase `RolexWidget(Gtk.Application)`.
- `rolex_draw.py` — `draw_rolex(cr, w, h, hour, minute, second_float, day)`.
- `config.json`, `run.sh`, `rolex-widget.desktop`, `requirements.txt`.

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
| Arrastrar (botón izq.) | Mover (no arrastra desde flechas ni footer) |
| Botones dorados `‹` `›` | Mes anterior / siguiente (botones GTK reales, glow en hover) |
| Click en footer (`Hoy · …`) | Volver al mes actual |
| Click derecho | Menú: mes ±, ir a hoy, bloquear, tamaño, salir |
| Doble-click / `L` | Bloquear (aparece candadito dorado abajo-derecha) |
| `←` / `→` | Mes anterior / siguiente |
| `↑` / `↓` | Año anterior / siguiente |
| `H` / `T` | Volver a hoy |
| `+` / `−` | Alto 400–800 px (ancho = alto × 0.70) |
| `Q` / `Esc` | Salir |

### Config (`agenda_config.json`)

```json
{ "height": 600, "locked": false, "opacity": 1.0, "monday_first": true, "view_year": null, "view_month": null }
```

- `view_year/view_month: null` = seguir el mes actual; al navegar se guardan,
  "Ir a hoy" los devuelve a `null`.
- `height` se recorta a 400–800.
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

## Autostart en GNOME

```bash
cp rolex-widget.desktop ~/.config/autostart/
cp agenda-widget.desktop ~/.config/autostart/
```

(Revisar que `Exec=` apunte a la ruta real.)

## Solución de problemas

- **No veo la ventana**: buscar `Rolex Submariner` / `Agenda de Lujo` con
  `Alt+Tab` o en Activities/Overview; probar con `--debug`.
- **Parece "muerto" (no responde)**: está bloqueado — doble-click o tecla `L`.
  La agenda muestra un candadito dorado cuando está bloqueada.
- **Logs**: ambos imprimen a stdout (`[rolex]…` / `[agenda] vista -> …`).
