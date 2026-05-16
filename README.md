<div align="center">

# Sol Cesto Solver

### *Lee el tablero. Decide la mejor fila. Sobrevive.*

Asistente por visión por computador para [**Sol Cesto**](https://store.steampowered.com/app/2738490/Sol_Cesto/),
el roguelite táctico de Goblinz Studio. Captura la ventana del juego y produce un
**JSON estructurado del estado** del tablero y del jugador. Construido sobre OpenCV
y `mss` — sin redes neuronales, sin entrenamiento, 100% determinista.

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
pierdes corazones.

Este proyecto es la **fase 1** de un asistente que minimiza la pérdida esperada de HP:

```
Sol Cesto (en ejecución)  →  captura ventana  →  reconocimiento  →  GameState JSON
                                                                          ↓
                                                          (fase 2: algoritmo de decisión)
```

Salida ejemplo:

```json
{
  "board": [
    [{"content": "monster", "sword_strength": 3}, {"content": "slime", "magic_strength": 1}, ...],
    ...
  ],
  "player": {"hp": 5, "max_hp": 5, "sword": 2, "magic": 1, "inventory": [], "modifiers": {}}
}
```

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
sol-cesto-solver                       # captura ventana -> imprime JSON
sol-cesto-solver --watch 2             # re-captura cada 2 segundos
sol-cesto-solver --debug               # guarda debug-grid.png con grid superpuesto
sol-cesto-solver --window "Sol Cesto"  # cambia el titulo de ventana a buscar
sol-cesto-solver --from-file shot.png  # analiza un PNG en lugar de capturar
```

---

## 🏗️ Arquitectura

```
src/sol_cesto_solver/
├── capture.py       Localiza ventana de Sol Cesto y captura con mss
├── grid.py          Calibra el tablero 4x4 y recorta celdas
├── recognition.py   Template matching de iconos y digitos
├── state.py         Dataclasses pydantic: GameState, Player, Cell
└── cli.py           Pipeline: captura -> reconocimiento -> JSON
```

Las templates (PNGs recortados del juego) viven en `templates/icons/` y `templates/digits/`.
El script `scripts/extract_templates.py` ayuda a generarlas la primera vez.

Pipeline:

```
captura BGR (mss) ──► detect_board (heurística) ──► 16 celdas
                                                       │
                                                       ▼
                                          ┌────────────────────────┐
                                          │  matchTemplate por     │
                                          │  cada icono y digito   │
                                          └────────────────────────┘
                                                       │
                                                       ▼
                                              GameState (pydantic)
                                                       │
                                                       ▼
                                              JSON a stdout
```

---

## 🧪 Tests

```powershell
poetry run pytest
```

Los tests cubren:
- Geometría del grid (cell rects, crops, dimensiones)
- Pipeline completo contra screenshots en `tests/fixtures/` (si existen)

---

## 🗺️ Roadmap

- [x] **Fase 1**: detección de pantalla → JSON
- [ ] **Fase 2**: algoritmo de decisión (valor esperado por fila)
- [ ] **Fase 3**: overlay en pantalla mostrando la fila recomendada
- [ ] **Fase 4**: lookahead multi-turno, gestión de pociones e inventario

---

## 🇪🇸 En español, en resumen

Un script Python que mira el juego **Sol Cesto** mientras juegas, identifica todo lo
que aparece en pantalla (monstruos, cofres, fresas, tu vida, tu daño) y produce un
JSON con el estado. Es la base para que en la siguiente fase un algoritmo te diga
qué fila elegir para perder los menos corazones posibles.

---

## 📄 License

[MIT](LICENSE)
