# Hindcast 2001-2025 (leave-one-out)

Generado por `hindcast_md.py` desde `out/<zona>.json` (`hindcast.years`). No editar a mano.

Clase WRSI: good >= 80, partial 60-80, failure < 60. Score: 1 bueno, 0.5 parcial, 0 fallo.

## parcela — Parcela del usuario, El Salvador (13.796406, -89.801031)

Lluvia: 0 % de los días desde IMERG; el resto desde NASA POWER PRECTOTCORR. Suelo clayey, WHC 130 mm. Corrección de temperatura: ninguna (null).

> Advertencia: sin corrección por elevación: falta elevation_m (parcela); temperatura de NASA POWER sin ajustar

| Año | Canícula | Elegida (LOO) | Score elegida | Score A | WRSI Maíz | WRSI Frijol | WRSI Sorgo | Maíz primera (WRSI, rango) | Documentado | D6 | Fuente |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2001 | short | C | 1.00 | 1.00 | 80.1 good | 100.0 good | 80.7 good | 100.0 (#10) | no | — | — |
| 2002 | long | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 99.2 good | 88.9 (#1) | no | — | — |
| 2003 | short | C | 1.00 | 1.00 | 98.5 good | 100.0 good | 98.3 good | 100.0 (#10) | no | — | — |
| 2004 | short | C | 1.00 | 1.00 | 91.7 good | 100.0 good | 90.3 good | 100.0 (#10) | no | — | — |
| 2005 | short | C | 1.00 | 1.00 | 95.3 good | 100.0 good | 93.4 good | 100.0 (#10) | no | — | — |
| 2006 | short | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#10) | no | — | — |
| 2007 | short | A | 0.50 | 0.50 | 98.3 good | 100.0 partial | 96.7 good | 100.0 (#10) | no | — | — |
| 2008 | normal | A | 1.00 | 1.00 | 96.7 good | 100.0 good | 94.7 good | 99.2 (#7) | no | — | — |
| 2009 | short | C | 1.00 | 1.00 | 97.7 good | 100.0 good | 99.9 good | 100.0 (#10) | no | — | — |
| 2010 | short | C | 0.50 | 1.00 | 74.4 partial | 99.9 good | 74.1 partial | 100.0 (#10) | no | — | — |
| 2011 | short | C | 1.00 | 1.00 | 89.9 good | 100.0 good | 87.5 good | 98.6 (#6) | no | — | — |
| 2012 | long | C | 1.00 | 1.00 | 96.2 good | 100.0 good | 95.5 good | 99.5 (#8) | no | — | — |
| 2013 | normal | A | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#10) | no | — | — |
| 2014 | long | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 99.2 good | 90.7 (#2) | sí | hit | [1] |
| 2015 | long | A | 0.50 | 0.50 | 100.0 good | 100.0 partial | 100.0 good | 91.8 (#3) | no | — | — |
| 2016 | short | C | 1.00 | 1.00 | 95.6 good | 100.0 good | 93.4 good | 100.0 (#10) | no | — | — |
| 2017 | short | C | 1.00 | 1.00 | 96.3 good | 100.0 good | 94.8 good | 100.0 (#10) | no | — | — |
| 2018 | normal | A | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#10) | sí | fallo | [2] |
| 2019 | long | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 99.5 good | 99.9 (#9) | no | — | — |
| 2020 | normal | A | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#10) | no | — | — |
| 2021 | short | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 99.3 good | 100.0 (#10) | no | — | — |
| 2022 | short | A | 0.50 | 0.50 | 99.4 good | 100.0 partial | 99.4 good | 100.0 (#10) | no | — | — |
| 2023 | normal | A | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#10) | no | — | — |
| 2024 | short | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 94.8 (#5) | no | — | — |
| 2025 | short | C | 1.00 | 1.00 | 99.9 good | 100.0 good | 99.8 good | 100.0 (#10) | no | — | — |

D6: 1 hit de 2 años documentados (hit = WRSI de maíz de primera entre los 9 peores del registro). Hits: [2014]; fallos: [2018].

Media (25 años): Tempo 0.92 · práctica A 0.94 · misma estrategia siempre 0.98 · mejor posible 1.0 · Tempo mejor en 0, peor en 1 · elecciones {'C': 17, 'A': 8}

Fuentes (D6):

1. FAO, 29 Jun 2016, ReliefWeb GLIDE DR-2014-000132-HND (https://reliefweb.int/disaster/dr-2014-000132-hnd): loss of staple grain crops in El Salvador since mid-2014.
2. ReliefWeb GLIDE DR-2018-000106-SLV (https://reliefweb.int/disaster/dr-2018-000106-slv): over 90,000 metric tons of corn lost, red alert.
