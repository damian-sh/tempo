# Pitch de 30 segundos

Unas 80 palabras por idioma, lo que cabe en 30 segundos dichos con calma. Cada cifra sale de la
instantánea de demo (`web/app/demo/`) o del código; la tabla del final dice de dónde.

## Español

**Problema.** En el Corredor Seco, la canícula, un periodo seco a mitad de las lluvias, pone en riesgo la siembra de postrera. En Nacaome,
Honduras, la canícula de 2026 duró 18 días y en julio y agosto llovieron 43 mm, frente a 331 en un
año normal.

**Qué hace Tempo.** Tocas tu parcela en el mapa. Tempo revisa 25 años de lluvia satelital de NASA,
el relieve y el suelo, compara tres opciones de siembra y recomienda la que mejor aguanta su peor
escenario, con una confianza alta, media o baja.

**Demostración en 3 clics.**
1. «Ver un ejemplo ya analizado»: Ahuachapán, frijol en relevo, confianza baja.
2. El chip «Nacaome»: la misma opción con confianza media; el gráfico muestra los 7 escenarios.
3. «Por qué la confianza no es más alta»: Tempo dice qué supuesto la frena.

**Honestidad.** Tempo no estima cosechas ni dinero y no está validado en campo. En los 9 puntos
analizados ninguna recomendación llega a confianza alta, y la app lo dice.

**Siguiente paso.** Validar los parámetros de cultivo y la regla de 150 mm del frijol con agrónomos
locales (CENTA) y rendimientos reales.

## English

**Problem.** In Central America's Dry Corridor, the midsummer dry spell (canícula) puts the second
planting (postrera) at risk. In Nacaome, Honduras, the 2026 canícula lasted 18 days and July
and August brought 43 mm of rain, against 331 mm in a normal year.

**What Tempo does.** You tap your plot on the map. Tempo reviews 25 years of NASA satellite rainfall,
terrain and soil, compares three planting options and recommends the one that holds up best in its
worst scenario, with high, medium or low confidence.

**Demo in 3 clicks.**
1. "See an analyzed example": Ahuachapán, relay bean, low confidence.
2. The "Nacaome" chip: the same option with medium confidence; the chart shows the 7 scenarios.
3. "Why confidence is not higher": Tempo names the assumption holding it back.

**Honesty.** Tempo does not estimate yields or income and has not been validated in the field. Across
the 9 analyzed points no recommendation reaches high confidence, and the app says so.

**Next step.** Validate crop parameters and the 150 mm bean rule with local agronomists (CENTA) and
real yields.

## De dónde sale cada afirmación

| Afirmación | Fuente |
|---|---|
| Nacaome: canícula 18 días, 43 mm jul–ago frente a 331 normales | `web/app/demo/63e1cac4e49c6a6c.json`: `resumen.lluvia.canicula_dias` = 18, `jul_ago_actual_mm` = 42.6, `jul_ago_mediana_mm` = 330.5 (la mediana 2001–2025 es el "año normal") |
| 25 años de lluvia satelital | IMERG 2001–2025 (`resumen.lluvia.anios`, `anios_comparados` = 25) |
| Tres opciones, peor escenario, confianza alta/media/baja | `engine.py` (`robust_pick`, `robust_confidence`), DECISIONES.md D10 rev. 2 |
| Ahuachapán: frijol en relevo (A), confianza baja | `c994b1f9c85a940e.json`: `recomendacion.clave` = A, `confianza` = baja |
| Nacaome: A, confianza media, 7 escenarios | `63e1cac4e49c6a6c.json`: `confianza` = media, `n_escenarios` = 7 |
| Ninguna de las 9 llega a confianza alta | `web/app/demo/jobs.json`: 7 baja, 2 media (Nacaome y Chinandega) |
| Sin rendimientos ni validación de campo; regla de 150 mm es un supuesto | README.md (Supuestos, Límites conocidos, Pendiente) |
