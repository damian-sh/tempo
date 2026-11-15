# Decisiones del proyecto

Registro de decisiones. Cada una la respondió el usuario en el chat. Fecha: 2026-11-14.

| ID | Decisión | Elegido | Estado |
|---|---|---|---|
| D1 | 2026 en la lista de sequías | Quitar de validación; queda como evento reportado, no usado | Aprobada |
| D2 | Fracción de agotamiento `p` | `p` por cultivo, tabla 22 de FAO-56, con ajuste por ETc | Aprobada |
| D3 | Temperatura sin elevación | dT = 0 con advertencia visible en el JSON y la página | Aprobada |
| D4 | Hargreaves: temperatura media | (Tmax+Tmin)/2, forma original FAO-56 eq. 52; reportar delta de ET0 vs T2M | Aprobada |
| D5 | Alcance del balance hídrico | Declarar "tipo WRSI simplificado, no FAO-56 completo" para esta entrega | Aprobada |
| D6 | Verdad para acierto/fallo | Solo años con fuente citada (FEWS NET, WFP, MAG/gobierno) | Aprobada |
| D7 | Umbral 150 mm frijol | Queda como SUPUESTO, salvo fuente encontrada en T3.1 | Aprobada |
| D8 | Proporciones 0.6/0.4 y SW inicial 0.5·WHC | SUPUESTO declarado | Aprobada |
| D9 | Publicación y push | Pendiente. Ninguna acción de publicación sin tu aprobación explícita | Pendiente |
| D10 | Recomendar aunque el veredicto no sea claro | Recomendación robusta: la opción con el mejor puntaje en su peor escenario (maximin), con confianza alta/media/baja y la tabla de escenarios visible | Aprobada (2026-11-15) |

## Cambios de validez (rama feat/validez-honestidad)

Correcciones de errores, no decisiones nuevas de parámetros. Ningún valor por defecto cambió.

| Cambio | Motivo |
|---|---|
| Empates de CHECK 1 con rango máximo; D6 `no_evaluable` si CHECK 1 no discrimina | Un empate en WRSI 100 no es un acierto (aplica D6) |
| Semáforo eliminado | Usaba la estrategia A (frijol) como si fuera maíz y no tenía base validada |
| TARGET_YEAR fuera de validación, rangos, skill y comparación de lluvia | Aplica D1 |
| Empate entre estrategias: se mantiene la práctica actual | Sin margen no se recomienda cambiar |
| Umbral de lectura del veredicto del sitio 0.05 | SUPUESTO; no es una medida del error |

## D10: recomendación robusta (2026-11-15)

El veredicto estricto (cuatro condiciones) no nombró ganador en ningún punto: la elección cambia sin la
regla de 150 mm del frijol y con NASA POWER en lugar de IMERG. Para poder recomendar sin esconder esa
incertidumbre, el motor (`engine.robust_recommendation`) calcula el puntaje de cada opción en el año
actual bajo cada escenario y recomienda la de mejor peor caso. Ningún parámetro por defecto cambió.

| Pieza | Valor | Estado |
|---|---|---|
| Escenarios | IMERG y POWER × con/sin regla de 150 mm, y suelo de 60/90/130 mm distinto del del punto | Fijo |
| Elección | Maximin; empate → mayor promedio → práctica actual (A) | Fijo |
| Empate entre puntajes | 0,005 (`ROBUST_TIE`) | SUPUESTO |
| Margen base | En el escenario base la opción debe superar a la siguiente por ≥ 0,05; si no, confianza baja ("no hay razón para cambiar") | SUPUESTO (rev. 2, tras el debate) |
| Confianza alta | Primera o empatada en todos los escenarios, peor caso ≥ 0,05 sobre la segunda y pruebas estrictas (regla de 150 mm y fuente de lluvia) sin cambios | SUPUESTO (rev. 2) |
| Confianza media | Nunca más de 0,05 detrás de la mejor de cada escenario | SUPUESTO |
| Confianza baja | El resto; se recomienda igual y se dice por qué | SUPUESTO |
| Topes | Sin IMERG: máximo baja. Suelo por defecto, prueba de sequías no evaluable o pruebas estrictas fallidas: máximo media | Fijo |
| Veredicto claro | Si pasan las cuatro condiciones, se recomienda esa opción con confianza alta | Fijo |

Suelo: si la API REST de ISRIC falla o no tiene valor en el punto (zonas urbanas, agua), se usan los
mismos mapas SoilGrids v2.0 desde Earth Engine: el punto, o el promedio en 1 y 2 km. El radio usado se
muestra. Si nada responde, queda el valor por defecto del modelo, marcado.

### D10 rev. 2 (2026-11-15, tras un debate fiscal/defensa/juez)

El juez dio por procedentes dos objeciones: "confianza alta" convivía con pruebas estrictas fallidas,
y márgenes de 0,002 y 0,007 salían "media". Se endurecieron las reglas (tabla de arriba). La página
ahora presenta el resultado como lectura de la postrera en curso para planificar la siguiente
siembra, muestra la incertidumbre de lluvia y la prueba con años pasados (con y sin la regla de 150 mm).
