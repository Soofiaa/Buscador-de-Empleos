# Reversión de la ayuda por pantalla

Despliegue del 22-10-2026, commit 200e021 (main). Solo cambia la página: el botón de ayuda y sus textos.

| Pieza | Valor |
|---|---|
| Imagen desplegada | job-tracker-jobtracker:latest, sha256:4ad9e68fd0797a80cd02390cec8dd197bc4af0831c0d15a6ba9e0c475b0d0e7d |
| Imagen anterior | job-tracker:pre-ayuda-20261022, sha256:e0069601e6486041b1974cea62acfb1241a1becdaa80ab8a6a46a6e688c501b4 |
| Base de referencia | ofertas_pre_ayuda_20261022.db (C:\Users\sofia\Respaldos\job-tracker-referencias\), integrity_check ok |

Para volver a la imagen anterior:

```powershell
docker compose stop jobtracker
docker tag job-tracker:pre-ayuda-20261022 job-tracker-jobtracker:latest
docker compose up -d --no-build
```n
Los datos no cambian. Solo desaparecen el botón de ayuda y sus textos.

