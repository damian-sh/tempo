# Hindcast 2001-2025 (leave-one-out)

Generado por `hindcast_md.py` desde `out/<zona>.json` (`hindcast.years`). No editar a mano.

Clase WRSI: good >= 80, partial 60-80, failure < 60. Score: 1 bueno, 0.5 parcial, 0 fallo.

## parcela — Parcela del usuario, El Salvador (13.796406, -89.801031)

Lluvia: 100 % de los días desde IMERG; el resto desde NASA POWER PRECTOTCORR. Suelo clayey, WHC 130 mm. Corrección de temperatura: -0.96 °C.

| Año | Canícula | Elegida (LOO) | Score elegida | Score A | WRSI Maíz | WRSI Frijol | WRSI Sorgo | Maíz primera (WRSI, rango) | Documentado | D6 | Fuente |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2001 | long | C | 1.00 | 1.00 | 94.1 good | 100.0 good | 92.4 good | 100.0 (#25) | no | — | — |
| 2002 | normal | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#25) | no | — | — |
| 2003 | short | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 99.2 good | 100.0 (#25) | no | — | — |
| 2004 | long | C | 1.00 | 0.50 | 98.9 good | 100.0 partial | 98.1 good | 100.0 (#25) | no | — | — |
| 2005 | short | C | 1.00 | 1.00 | 96.3 good | 100.0 good | 94.2 good | 100.0 (#25) | no | — | — |
| 2006 | normal | C | 1.00 | 1.00 | 100.0 good | 99.9 good | 100.0 good | 100.0 (#25) | no | — | — |
| 2007 | short | C | 1.00 | 0.50 | 97.6 good | 100.0 partial | 95.9 good | 100.0 (#25) | no | — | — |
| 2008 | normal | C | 1.00 | 1.00 | 96.6 good | 100.0 good | 93.5 good | 100.0 (#25) | no | — | — |
| 2009 | long | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 99.9 good | 100.0 (#25) | no | — | — |
| 2010 | short | C | 1.00 | 1.00 | 82.0 good | 100.0 good | 82.1 good | 100.0 (#25) | no | — | — |
| 2011 | short | C | 1.00 | 0.50 | 98.7 good | 100.0 partial | 99.5 good | 100.0 (#25) | no | — | — |
| 2012 | short | C | 1.00 | 1.00 | 99.3 good | 100.0 good | 97.4 good | 100.0 (#25) | no | — | — |
| 2013 | long | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#25) | no | — | — |
| 2014 | long | C | 1.00 | 0.50 | 100.0 good | 100.0 partial | 99.6 good | 100.0 (#25) | sí | no evaluable | [1] |
| 2015 | long | C | 1.00 | 0.50 | 100.0 good | 100.0 partial | 100.0 good | 100.0 (#25) | no | — | — |
| 2016 | normal | C | 1.00 | 0.50 | 98.3 good | 100.0 partial | 96.2 good | 98.8 (#1) | no | — | — |
| 2017 | short | C | 1.00 | 1.00 | 99.7 good | 100.0 good | 97.5 good | 99.9 (#2) | no | — | — |
| 2018 | short | C | 1.00 | 0.50 | 100.0 good | 100.0 partial | 100.0 good | 100.0 (#25) | sí | no evaluable | [2] |
| 2019 | normal | C | 1.00 | 0.50 | 100.0 good | 100.0 partial | 98.2 good | 100.0 (#25) | no | — | — |
| 2020 | normal | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#25) | no | — | — |
| 2021 | long | C | 1.00 | 1.00 | 98.6 good | 100.0 good | 96.3 good | 100.0 (#25) | no | — | — |
| 2022 | short | C | 1.00 | 1.00 | 99.5 good | 100.0 good | 99.9 good | 100.0 (#25) | no | — | — |
| 2023 | normal | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#25) | no | — | — |
| 2024 | short | C | 1.00 | 1.00 | 100.0 good | 100.0 good | 100.0 good | 100.0 (#25) | no | — | — |
| 2025 | normal | C | 1.00 | 0.50 | 98.7 good | 100.0 partial | 96.8 good | 100.0 (#25) | no | — | — |

D6: no evaluable. 23 de 25 años empatan en WRSI 100 en maíz de primera, así que el ranking no separa años secos; los años documentados ([2014, 2018]) no cuentan como hit ni como fallo. Empates con rango máximo.

Media (25 años): Tempo 1.0 · práctica A 0.82 · misma estrategia siempre 1.0 · mejor posible 1.0 · Tempo mejor en 9, peor en 0 · margen medio frente a A 0.18 (prueba de signos p = 0.0039) · elecciones {'C': 25}

Sensibilidad (base: WHC 130 mm, regla de frijol 150 mm). Años cuya elección LOO cambia frente a la base:

| Variante | Años que cambian | Tempo | Práctica A | Margen | Elecciones | CHECK 1 discrimina |
|---|---|---|---|---|---|---|
| WHC 60 mm | 3 de 25 (2007, 2011, 2018) | 0.88 | 0.82 | 0.06 | {'C': 22, 'A': 3} | sí |
| WHC 90 mm | 0 de 25 (—) | 0.98 | 0.82 | 0.16 | {'C': 25} | no |
| WHC 130 mm | 0 de 25 (—) | 1.00 | 0.82 | 0.18 | {'C': 25} | no |
| sin regla 150 mm de frijol | 25 de 25 (2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025) | 1.00 | 1.00 | 0.00 | {'A': 25} | no |

Fuentes (D6):

1. FAO, 29 Jun 2016, ReliefWeb GLIDE DR-2014-000132-HND (https://reliefweb.int/disaster/dr-2014-000132-hnd): loss of staple grain crops in El Salvador since mid-2014.
2. ReliefWeb GLIDE DR-2018-000106-SLV (https://reliefweb.int/disaster/dr-2018-000106-slv): over 90,000 metric tons of corn lost, red alert.
