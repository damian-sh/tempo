# Informe de la noche: rama `noche/pulido-jurado`

Base: `integracion/fase4` (f6d5eed). Trabajo hecho sin nadie a quien consultar; donde había que decidir,
decidí lo más conservador y lo dejo anotado abajo.

## Qué cambió

| Tarea | Archivos | Resumen |
|---|---|---|
| 1. Modo demo estático | `web/app/app.js`, `web/app/index.html`, `export_demo.py`, `web/app/demo/sitios.json` (nuevo) | Si `/api/*` no responde o devuelve algo que no es JSON, la app pasa a modo demo y lee `demo/jobs.json`, `demo/<id>.json` y `demo/sitios.json`. Al elegir un punto nuevo, un aviso explica que hace falta el servidor de Tempo y ofrece abrir el análisis guardado más cercano (distancia calculada). El botón «Analizar» da el mismo mensaje. El inicio muestra «Demo sin servidor: 9 análisis reales…». El enlace de la marca pasó de `/app/` a `./`. El JSON descargable apunta a `demo/<id>.json` en demo. `export_demo.py --sitios` regenera solo el buscador. |
| 1. Pruebas E2E | `tests/e2e/e2e_web.py` | Ruta de la app configurable (`TEMPO_E2E_APP`, `/` para la demo estática). Nueva prueba 16 del modo demo. Las capturas van a `TEMPO_E2E_OUT` en vez de una ruta fija de otra sesión. No se borró ninguna comprobación; la prueba del análisis nuevo real pasó a ser la 17. |
| 2. Diseño | `web/app/app.js`, `web/app/style.css`, `web/app/index.html` | Ver detalle abajo. |
| 3. Pitch | `docs/pitch.md` | ES e EN, ~80 palabras cada uno, con una tabla que dice de qué archivo y campo sale cada cifra. |
| 4. Guía del jurado | `docs/jurado.md`, `docs/img/*` | Cómo abrir la demo, qué mirar en 3 clics (tabla), cómo leer el gráfico, fuentes y límites, con 4 capturas. |
| README | `README.md` | Un párrafo que enlaza la demo estática y `docs/jurado.md`. |

### Diseño (tarea 2)

Se aplicaron las skills `impeccable` y `frontend-design` en modo Operate, como refinamiento del diseño
existente: no hay PRODUCT.md ni DESIGN.md y no había a quién hacer la entrevista de `init`, así que se
partió del código y del enunciado.

- **Confianza visual:** medidor de tres tramos (baja ocre, media/alta verde) junto a la palabra
  «Confianza media», sin depender solo del color.
- **Gráfico de escenarios** dentro del veredicto: por opción, un punto por escenario, el peor caso como
  punto grande, y una línea punteada en el peor caso de la recomendada. Así se ve el maximin sin leer
  la tabla. Todo número sale de `recomendacion.escenarios` y `peor_puntaje`; los extremos del eje se
  redondean a 0,05 a partir de esos valores.
- **Menos texto a la vista:** los motivos de la confianza y la incertidumbre de lluvia van en un
  plegable dentro del veredicto. La tabla de escenarios, la prueba con años pasados, las pruebas
  estrictas y los datos técnicos van en plegables bajo «Detalle para revisar». Se mantienen visibles:
  las tres opciones, cómo va la postrera, el gráfico de lluvia y la temporada.
- **Título sin etiqueta encima:** la línea «Lectura de la postrera… para planificar…» pasó debajo del
  título y se reescribió: «Recomendada para planificar 2027, según la postrera 2026».
- **Mapa:** cada análisis muestra la letra recomendada (A/B/C). Relleno verde = confianza media o alta;
  blanco = baja. La leyenda lo explica.
- **Paleta:** hoja, tierra, lluvia y maíz como tokens (`--accent`, `--soil`, `--rain`, `--maize`), fondo
  verdoso en lugar de crema y modo oscuro revisado. Contraste calculado: todo el texto ≥ 4.5:1 en claro
  y oscuro (mínimo 5.37:1).
- **Tipografía:** Figtree (Google Fonts) con respaldo de fuentes del sistema. Primero probé Atkinson
  Hyperlegible Next, pero su cero tachado («Ø,866») confundía en los puntajes.
- Pasos de inicio numerados (es una secuencia real), cursor, `accent-color` y barra de desplazamiento
  con la paleta. Se mantuvo el ícono (pin, brote y gota).
- Nada de degradados, vidrio, tarjetas iguales con ícono, etiquetas en mayúsculas, emoji ni bordes
  gruesos a la izquierda.

No se tocaron `engine.py`, `robust_pick`, `robust_confidence`, los parámetros ni los JSON de demo de
los análisis.

## Qué verifiqué y cómo

- `uv run --no-project --with pytest --with-requirements requirements.txt pytest -q`: 82 pasan, 10 se
  saltan (igual que al empezar).
- E2E con Playwright (Firefox), 16/16 OK y 0 errores de consola en los dos modos:
  - demo estática: `cd web/app && python -m http.server 8831`, y luego
    `TEMPO_E2E_APP=/ uv run --no-project --with playwright python tests/e2e/e2e_web.py http://127.0.0.1:8831`;
  - servidor real: `python server.py --port 8830` con la caché local de esta máquina.
- Móvil 390 px: `scrollWidth` = 390, sin scroll horizontal (prueba 15 y capturas propias).
- Capturas en Chromium de escritorio 1440×900 (claro y oscuro) y de móvil 390×844, revisadas a ojo
  después de cada cambio.
- Contraste: cálculo WCAG de los pares de tokens (texto, texto atenuado, acento, avisos) en claro y
  oscuro.
- `impeccable detect`: un solo aviso («cramped padding» en las pestañas). Es un falso positivo por el
  subrayado de la pestaña activa.
- Inglés: prueba 11 (cambio de idioma y vuelta); todos los textos nuevos tienen versión ES y EN.

## Capturas

`docs/img/inicio.jpg`, `docs/img/resultado-nacaome.png`, `docs/img/por-que-confianza.png`,
`docs/img/movil-oscuro.png` (generadas con Playwright sobre la demo estática).

## Qué no pude hacer y por qué

- **Abrir `index.html` con doble clic (`file://`)** no funciona: los navegadores bloquean `fetch` de
  JSON locales. Para eso habría que incrustar los 9 resultados en un `.js` (unos MB). Lo dejé así y la
  guía lo explica.
- **Sin internet**, el mapa y la tipografía no cargan (Leaflet y los mosaicos ya dependían de la red).
- **Foco y teclado** se revisaron leyendo el código (`:focus-visible` global, `summary` nativos) y con
  las pruebas, no con un lector de pantalla real.
- **Los textos de los motivos de confianza** (`limites`) y de las condiciones vienen del motor solo en
  español; en inglés se muestran en español con `lang="es"`. Ya era así antes.

## Decisiones pendientes para el dueño

1. **Tipografía externa:** Figtree se carga desde Google Fonts. Si se prefiere cero dependencias,
   bórrense las tres líneas `<link>` de `index.html`: la app cae a la fuente del sistema.
2. **Marcadores con letra:** en el mapa, el relleno distingue «media o alta» de «baja». Si algún día hay
   confianza alta, quizá convenga un tercer estilo.
3. **¿Publicar la demo?** No publiqué nada (D9 sigue pendiente). La carpeta `web/app` sirve tal cual
   en cualquier hosting estático.
4. **`demo/sitios.json`** se generó con `export_demo.py --sitios` desde `parcelas.json` sin regenerar
   los análisis. Al volver a exportar todo (`python export_demo.py`) se regenera junto con ellos.
5. **El pitch** cita Nacaome (canícula de 18 días, 43 mm frente a 331). Si se regenera la demo, hay
   que revisar esas cifras con la tabla de fuentes de `docs/pitch.md`.
