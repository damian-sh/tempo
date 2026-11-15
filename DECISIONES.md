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
