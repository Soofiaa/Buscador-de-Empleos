# Notas del proyecto: decisiones y hallazgos

## Graphify (probado el 13-10-2026 en una copia; NO se usa en job-tracker)

Probado con graphifyy 0.9.53 (`graphify update`, solo AST, sin LLM ni red), sobre una copia fuera de OneDrive. Decisión: no activarlo aquí.

- No ve el SQL embebido en los textos ni las clases definidas dentro de funciones (el `Handler` de `servidor.py`). Por eso omitió 3 de los 4 escritores de estado, fase y fecha, y casi todas las rutas que llegan a `conectar()`.
- De sus 21 aristas inferidas, 8 eran falsas: confundió el módulo `buscar` con la función `getonboard.buscar`.
- El hook post-commit suma unos 1,4 s a cada commit. Si una reconstrucción falla, el grafo queda desactualizado sin avisar hasta un `graphify update .` manual.
- `hook install` escribe en `.gitattributes`, que está versionado.
- grep resultó más rápido y más completo para este proyecto (33 archivos).
