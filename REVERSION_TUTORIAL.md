# Reversión del tutorial

Despliegue del 22-10-2026, commit b5d4f98 (main). Solo cambia documentación y un botón de la página.

| Pieza | Valor |
|---|---|
| Imagen desplegada | job-tracker-jobtracker:latest, sha256:e0069601e6486041b1974cea62acfb1241a1becdaa80ab8a6a46a6e688c501b4 |
| Imagen anterior | job-tracker:pre-tutorial-20261022, sha256:7edd2576c6894c2c3f30cfe873eec019b26ebf2e4af57ab8c44187412f8aa40a |
| Base de referencia | ofertas_pre_tutorial_20261022.db (C:\Users\sofia\Respaldos\job-tracker-referencias\), integrity_check ok |

Para volver a la imagen anterior:

```powershell
docker compose stop jobtracker
docker tag job-tracker:pre-tutorial-20261022 job-tracker-jobtracker:latest
docker compose up -d --no-build
```n
Los datos no cambian. Solo desaparecen el botón y la guía; TUTORIAL.md sigue en el repositorio.

