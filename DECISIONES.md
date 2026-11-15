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

## Cambios de validez (rama feat/validez-honestidad)

Correcciones de errores, no decisiones nuevas de parámetros. Ningún valor por defecto cambió.

| Cambio | Motivo |
|---|---|
| Empates de CHECK 1 con rango máximo; D6 `no_evaluable` si CHECK 1 no discrimina | Un empate en WRSI 100 no es un acierto (aplica D6) |
| Semáforo eliminado | Usaba la estrategia A (frijol) como si fuera maíz y no tenía base validada |
| TARGET_YEAR fuera de validación, rangos, skill y comparación de lluvia | Aplica D1 |
| Empate entre estrategias: se mantiene la práctica actual | Sin margen no se recomienda cambiar |
| Umbral de lectura del veredicto del sitio 0.05 | SUPUESTO; no es una medida del error |
