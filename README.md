<div align="center">

# Sol Cesto Solver

### *Lee el tablero. Decide la mejor fila. Sobrevive.*

Asistente por visión por computador para [**Sol Cesto**](https://store.steampowered.com/app/2738490/Sol_Cesto/),
el roguelite táctico de Goblinz Studio. Captura la ventana del juego, reconoce el
estado del tablero, y **recomienda qué fila elegir** para minimizar la pérdida
esperada de HP. Construido sobre OpenCV y `mss` — sin redes neuronales, sin
entrenamiento, 100% determinista.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.10-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-2-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Poetry](https://img.shields.io/badge/Poetry-managed-60A5FA?style=flat-square&logo=poetry&logoColor=white)](https://python-poetry.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

</div>

---

## ✨ Qué hace

**Sol Cesto** es un roguelite con tablero 4×4. Eliges una fila y caes con probabilidad
uniforme (1/4) en una de las casillas. Si la casilla tiene un monstruo más fuerte que tú,
pierdes corazones. Este asistente automatiza la pregunta *"¿qué fila tiene la menor
pérdida esperada de HP?"*:

```
Sol Cesto (en ejecución)  →  captura ventana  →  reconocimiento  →  GameState
                                                                         │
                                                                         ▼
                                                                Algoritmo decisión
                                                                         │
                                                                         ▼
                                                            { state, recommendation } JSON
```

Salida ejemplo (recortada):

```json
{
  "state": {
    "board": [
      [{"content": "physical", "value": 3}, {"content": "magic", "value": 1}, ...],
      ...
    ],
    "player": {"hp": 5, "max_hp": 5, "sword": 2, "magic": 1, ...}
  },
  "recommendation": {
    "best_row": 3,
    "rows": [
      {"row": 0, "expected_hp_change": -0.5, "worst_case_hp_change": -1.0, "cells": [...]},
      {"row": 1, "expected_hp_change":  0.0, "worst_case_hp_change":  0.0, "cells": [...]},
      {"row": 2, "expected_hp_change": -0.25, "worst_case_hp_change": -1.0, "cells": [...]},
      {"row": 3, "expected_hp_change":  0.0, "worst_case_hp_change":  0.0, "cells": [...]}
    ]
  }
}
```

Las celdas se clasifican por el **badge** (el icono pequeño en la esquina), no por
el sprite del monstruo: `physical` (espada roja), `magic` (varita azul), `heal`
(corazón rojo), `treasure` (`?` dorado), `empty`. Esto es robusto a animaciones
y a cualquier monstruo nuevo que tenga uno de esos badges.

---

## 🎯 Por qué template matching y no redes neuronales

El arte de Sol Cesto es **pixel-perfect y consistente**: cada slime se renderiza igual,
cada `3` se ve idéntico. En este contexto:

| Enfoque | Por qué no |
|---------|-----------|
| YOLO / red neuronal | Necesita dataset etiquetado, entrenamiento, GPU; menos preciso aquí |
| Tesseract / EasyOCR | Frágil con fuentes estilizadas y números pequeños |
| **Template matching** | Cero entrenamiento, ~0 ms por celda, **100% fiable** ✓ |

Es la herramienta correcta para el problema, no la más impresionante. La complejidad
extra de un modelo entrenado no aporta nada cuando el dominio es pixel-determinista.

---

## 🚀 Quick start

```powershell
# 1. Instala Poetry si no lo tienes -> https://python-poetry.org/docs/#installation

# 2. Instala dependencias en un venv dentro del proyecto (.venv/)
poetry install

# 3. Extrae templates desde un screenshot del juego (una sola vez)
poetry run python scripts/extract_templates.py path/to/screenshot.png

# 4. Abre Sol Cesto y ejecuta
poetry run sol-cesto-solver
```

> El venv vive en `.venv/` dentro del proyecto gracias a `poetry.toml`
> (`virtualenvs.in-project = true`), así VS Code / PyCharm / etc. lo encuentran solos.

---

## 🖥️ CLI

```powershell
sol-cesto-solver                       # captura ventana -> JSON {state, recommendation}
sol-cesto-solver --watch 2             # re-captura cada 2 segundos
sol-cesto-solver --debug               # guarda debug-grid.png con grid superpuesto
sol-cesto-solver --window "Sol Cesto"  # cambia el titulo de ventana a buscar
sol-cesto-solver --from-file shot.png  # analiza un PNG en lugar de capturar
sol-cesto-solver --mimic-chance 0.2    # penaliza cofres (probabilidad de mimic)
```

---

## 🏗️ Arquitectura

```
src/sol_cesto_solver/
├── capture.py       Localiza la ventana de Sol Cesto y captura con mss
├── grid.py          Calibra el tablero 4x4 y recorta celdas
├── recognition.py   Template matching de badges (sword/magic/heart/?) y dígitos
├── state.py         Dataclasses pydantic: GameState, Player, Cell
├── decision.py      Algoritmo: evalúa cada fila y recomienda la mejor
└── cli.py           Pipeline: captura -> reconocimiento -> decisión -> JSON
```

Las templates (PNGs recortados del juego) viven en `templates/icons/` y `templates/digits/`.
El script `scripts/extract_templates.py` ayuda a generarlas la primera vez.

---

## 🧮 Algoritmo de decisión

Caer en una fila es un sorteo uniforme entre sus 4 celdas. Para cada fila
computamos el **valor esperado** del cambio de HP:

```
E[ΔHP | fila r] = (1/4) · Σ hp_change(cell_i)
```

donde `hp_change(cell)` depende del badge:

| Badge       | hp_change                                            |
|-------------|------------------------------------------------------|
| `physical`  | `-max(0, value − player.sword)`                      |
| `magic`     | `-max(0, value − player.magic)`                      |
| `heal`      | `+min(value, max_hp − hp)`  *(capado al hueco)*      |
| `treasure`  | `-mimic_chance · ASSUMED_MIMIC_LOSS`                 |
| `empty`     | `0`                                                  |

Recomendamos la fila con `E[ΔHP]` máximo. **Tiebreakers**: primero mejor
peor-caso (más defensivo), luego menor índice de fila (estabilidad).

`mimic_chance` es un hiperparámetro reservado para los niveles tardíos donde
algunos cofres son mimics — visualmente indistinguibles desde un frame único,
así que el algoritmo los descuenta probabilísticamente. Default: `0.0`.

---

## 🧪 Tests

```powershell
poetry run pytest
```

Los tests cubren:
- Geometría del grid (cell rects, crops, dimensiones)
- Pipeline de reconocimiento contra screenshots en `tests/fixtures/` (si existen)
- Algoritmo de decisión: cambio de HP por tipo de celda, valor esperado por fila,
  tiebreakers, hiperparámetro `mimic_chance`

---

## 🗺️ Roadmap

- [x] **Fase 1**: detección de pantalla → JSON del estado
- [x] **Fase 2**: algoritmo de decisión (valor esperado por fila + mimic risk)
- [ ] **Fase 3**: overlay en pantalla mostrando la fila recomendada en vivo
- [ ] **Fase 4**: lookahead multi-turno, gestión de pociones e inventario
- [ ] **Fase 5**: detección de mimics por diff entre frames consecutivos

---

## 🇪🇸 En español, en resumen

Un script Python que mira el juego **Sol Cesto** mientras juegas, identifica todo lo
que aparece en pantalla (monstruos, cofres, fresas, tu vida, tu daño) y te dice
qué fila tiene la menor pérdida esperada de corazones. Devuelve un JSON con el
estado del tablero **y** la recomendación con el desglose de cada fila — así puedes
ver no sólo qué jugar, sino por qué.

---

## 📄 License

[MIT](LICENSE)
