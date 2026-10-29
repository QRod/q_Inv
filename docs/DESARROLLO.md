# Desarrollo

## Ejecución desde código

Requiere Python 3.11 o posterior y soporte para venv.

```sh
git clone https://github.com/QRod/q_Inv.git
cd q_Inv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py --create-user admin
.venv/bin/python server.py
```

Abrir http://127.0.0.1:8080. No hay credenciales predeterminadas. La primera cuenta es administradora; las cuentas posteriores son lectoras por defecto y necesitan grupos autorizados. Se puede indicar `--role admin`, `--role operator` o `--role reader` al crearlas.

Los datos se guardan en `data/inventory.sqlite3`; `QINV_DATA` permite seleccionar otro directorio. La clave de credenciales se crea en `secrets/credentials.key`, configurable con `QINV_KEY_FILE`. Ambos directorios están excluidos de Git. El backend utiliza SQLite y módulos Python; la interfaz utiliza HTML, CSS y JavaScript.

Esta ejecución escucha en loopback. Para una instalación accesible por red, utilizar el [instalador y HTTPS](INSTALACION.md). En un despliegue manual, ejecutar sin privilegios, configurar `QINV_SECURE_COOKIE=1` detrás de HTTPS y administrar límites de autenticación y solicitudes en el proxy, respaldos y supervisión del servicio.

## Datos de ejemplo

```sh
.venv/bin/python tools/create_sample.py
```

Importar `examples/RVTools-demo.xlsx` desde la interfaz. El libro es completamente sintético y contiene tres VMs con dos tarjetas por VM; repetir la carga actualiza los mismos servidores.

## Verificación

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
bash -n install.sh
```

Las pruebas utilizan datos sintéticos y bases temporales. Los recorridos de navegador requieren Chrome y Playwright:

```sh
QINV_PLAYWRIGHT=/ruta/a/playwright-core node tests/browser-smoke.cjs
QINV_PLAYWRIGHT=/ruta/a/playwright-core node tests/browser-ui.cjs
QINV_PLAYWRIGHT=/ruta/a/playwright-core node tests/browser-compact.cjs
QINV_PLAYWRIGHT=/ruta/a/playwright-core node tests/browser-enterprise.cjs
QINV_PLAYWRIGHT=/ruta/a/playwright-core node tests/browser-network.cjs
```

`QINV_CHROME` permite seleccionar el ejecutable de Chrome. GitHub Actions ejecuta las pruebas de Python, verifica la sintaxis JavaScript y shell y comprueba el empaquetado. Los resultados no sustituyen la validación de conexiones con cada sistema operativo remoto.

## Empaquetado

Desde un checkout limpio y con la versión correspondiente en `VERSION`:

```sh
python3 scripts/package_release.py v0.6.0
```

El artefacto y `SHA256SUMS` se generan en `dist/`. El paquete incluye únicamente archivos versionados y excluye datos, claves, entornos virtuales y resultados locales. La autenticidad de la descarga depende del repositorio oficial y de HTTPS; la suma comprueba su integridad.

El contrato de interfaces y direcciones se documenta en [Datos de red en la API](API-RED.md).
