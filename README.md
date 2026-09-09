# Rolex Submariner — Widget de escritorio para Wayland (Ubuntu 26.04 + GNOME)

Reloj analógico de manecillas estilo Submariner, dibujado 100% en vectorial con
Cairo. Sin imágenes externas.

> Nota Wayland/GNOME: `gtk-layer-shell` **no funciona en GNOME**. Por eso es una
> ventana GTK4 sin bordes, transparente, que no roba foco. No puede quedar como
> fondo real detrás del wallpaper, pero sí flotante siempre visible.

## Cómo funciona (sin dependencias extra)

Render en memoria con `pycairo` → `Gtk.Picture` vía `Gdk.MemoryTexture`
(sin archivos temporales, sin `python3-gi-cairo`, sin carreras de lectura).

- Python 3.14, GTK 4.22, PyGObject, pycairo (ya instalados)
- Si falta algo: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0`

## Uso

```bash
python3 rolex_widget.py
# o
./run.sh
```

## Controles

- **Arrastrar** con botón izquierdo para mover (el compositor Wayland gestiona el move).
- **Click derecho**: menú (sweep/tick, bloquear, tamaño +/−, salir).
- **Doble click / tecla L**: bloquea o desbloquea (bloqueado = no arrastra ni abre menú).
- **+ / −**: cambia tamaño (200–600px). **Q / Esc**: salir.

## Config (`config.json`)

```json
{ "size": 340, "sweep": true, "locked": false, "opacity": 1.0 }
```

- `sweep: true` = segundero suave (50ms), `false` = tick cada segundo.

## Modo "siempre atrás" (extensión GNOME Shell)

Wayland no deja a una app ponerse debajo sola. La extensión `rolex-below@local`
(ya creada en `~/.local/share/gnome-shell/extensions/`) mantiene el reloj al
fondo de la pila (`lower()`) y visible en todos los escritorios (`stick()`).

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
cp rolex-widget.desktop ~/.config/autostart/
```

(Revisa que `Exec=` apunte a tu ruta real.)

## Archivos

- `rolex_widget.py` — ventana, timers, menú, drag.
- `rolex_draw.py` — dibujo Cairo del Submariner.
- `config.json`, `run.sh`, `rolex-widget.desktop`, `requirements.txt`.

---

# Agenda de Lujo — Calendario mensual para Wayland (GNOME)

Calendario de mes completo estilo agenda de cuero negro con filetes dorados,
dibujado 100% en vectorial con Cairo. Misma filosofía que el Rolex: sin
imágenes, render en memoria `pycairo → Gtk.Picture` vía `Gdk.MemoryTexture`.

## Uso

```bash
python3 agenda_widget.py
# o
./run_agenda.sh
```

## Controles

- **Arrastrar** con botón izquierdo para mover (no arrastra desde las flechas ni el footer).
- **Botones dorados ‹ ›** en el header: click para mes anterior/siguiente (botones GTK reales sobre el dibujo, con glow dorado al pasar el mouse). **Click en el footer** ("Hoy · ..."): vuelve a hoy.
- **Click derecho**: menú (mes anterior/siguiente, ir a hoy, bloquear, tamaño, salir).
- **Doble click / tecla L**: bloquear clicks (aparece un candadito dorado abajo a la derecha; bloqueado = no arrastra, no navega ni abre menú).
- **← / →**: mes anterior/siguiente. **↑ / ↓**: año anterior/siguiente.
- **H / T**: volver a hoy. **+ / −**: tamaño (alto 400–800px). **Q / Esc**: salir.

## Config (`agenda_config.json`)

```json
{ "height": 600, "locked": false, "opacity": 1.0, "monday_first": true, "view_year": null, "view_month": null }
```

- `view_year/view_month: null` = seguir el mes actual del sistema.
- Al navegar se guardan el año/mes visibles; "Ir a hoy" los vuelve a `null`.

## Archivos

- `agenda_widget.py` — ventana, timer 30s, menú, drag, navegación.
- `agenda_draw.py` — dibujo Cairo (cuero, dorado, rejilla 6×7, footer hoy).
- `agenda_config.json`, `run_agenda.sh`, `agenda-widget.desktop`.
