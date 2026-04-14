# Troubleshooting & Decisiones Técnicas

Registro de problemas encontrados durante el setup y desarrollo de school-guardian + OpenClaw.

---

## 1. Browser tool — "No supported browser found"

**Problema:** OpenClaw no encontraba ningún navegador al intentar usar la tool `browser`.

**Causa:** La imagen base de OpenClaw (`ghcr.io/openclaw/openclaw:latest`) no incluye Chromium ni ningún browser instalado.

**Solución:** En `Dockerfile.openclaw`, instalar Chromium con Playwright y crear symlinks a las rutas que OpenClaw busca:

```dockerfile
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN npx --yes playwright install --with-deps chromium \
    && chmod -R a+rx /opt/ms-playwright \
    && CHROME=/opt/ms-playwright/chromium-1217/chrome-linux64/chrome \
    && ln -s $CHROME /usr/bin/google-chrome \
    && ln -s $CHROME /usr/bin/chromium \
    && ln -s $CHROME /usr/bin/chromium-browser
```

Los paths de búsqueda de OpenClaw están en `/app/extensions/browser/src/browser/chrome.executables.ts` dentro del contenedor.

**Nota:** `PLAYWRIGHT_BROWSERS_PATH` debe setearse *antes* del `RUN` para que Playwright instale en `/opt/ms-playwright` y no en `/root/.cache` (inaccesible para el usuario `node`).

---

## 2. `_snapshotForAI` no existe en playwright-core@1.59.1

**Problema:** Al usar la tool `browser`, OpenClaw fallaba con:
```
refs=aria requires Playwright _snapshotForAI support.
```

**Causa:** OpenClaw llama `page._snapshotForAI()` internamente (en `/app/dist/pw-ai-*.js`), pero ese método privado no existe en `playwright-core@1.59.1`. El equivalente público es `ariaSnapshot()` que devuelve un string, mientras que `_snapshotForAI` debe devolver `{ full: string }`.

**Solución:** Parchear `playwright-core/lib/client/page.js` en el build de la imagen para inyectar el método faltante:

```dockerfile
RUN node -e " \
    const fs = require('fs'); \
    const f = '/app/node_modules/playwright-core/lib/client/page.js'; \
    let s = fs.readFileSync(f, 'utf8'); \
    const patch = 'async _snapshotForAI(options = {}) { const snapshot = await this.ariaSnapshot({ timeout: options.timeout, depth: options.depth }); return { full: snapshot || \"\" }; }\n  '; \
    s = s.replace('async ariaSnapshot(options = {}) {', patch + 'async ariaSnapshot(options = {}) {'); \
    fs.writeFileSync(f, s); \
    console.log('patched _snapshotForAI'); \
"
```

Si el build imprime `patched _snapshotForAI`, el patch se aplicó correctamente.

---

## 3. DNS no resuelve dentro del contenedor (rootless Podman)

**Problema:** El contenedor OpenClaw no podía resolver nombres de dominio. El nameserver del sistema (`127.0.0.53`, systemd-resolved) no es accesible desde contenedores rootless de Podman.

**Solución:** Montar un `resolv.conf` personalizado con DNS públicos:

`docker/resolv.conf`:
```
nameserver 8.8.8.8
nameserver 8.8.4.4
```

`compose.openclaw.yaml`:
```yaml
volumes:
  - ./docker/resolv.conf:/etc/resolv.conf:ro
```

**Nota:** Esto solo aplica a Podman en modo rootless con `network_mode: host`. Con redes bridge de Podman el DNS funciona diferente.

---

## 4. OpenClaw intenta conectarse a browser del host (`target: host`)

**Problema:** OpenClaw intentaba conectarse a un browser real corriendo en el host vía CDP en lugar de lanzar uno headless.

**Causa:** Sin configuración explícita, OpenClaw asume modo `target: host`.

**Solución:** Configurar explícitamente el modo headless en `openclaw/openclaw.json.example`:

```json
"browser": {
  "headless": true,
  "noSandbox": true,
  "executablePath": "/opt/ms-playwright/chromium-1217/chrome-linux64/chrome",
  "extraArgs": ["--disable-gpu", "--disable-dev-shm-usage"]
}
```

---

## 5. Pairing de Telegram se resetea al recrear el contenedor

**Problema:** Cada vez que se recrea `openclaw-gateway`, el pairing con Telegram se pierde y hay que volver a aprobar.

**Causa:** El estado de pairing se guarda en el filesystem del contenedor (`/home/node/.openclaw/`), que se destruye al recrear.

**Workaround actual:** Re-aprobar manualmente después de cada recreación:
```bash
podman exec openclaw-gateway node /app/dist/index.js pairing approve telegram <CÓDIGO>
```

**Mejora pendiente:** Persistir `/home/node/.openclaw/` en un volumen para que el pairing sobreviva recreaciones.

---

## 6. `user: root` en compose rompía auth de OpenClaw

**Problema:** Al agregar `user: root` al servicio `openclaw-gateway` en compose para resolver permisos de Playwright, OpenClaw no encontraba sus archivos de configuración de auth.

**Causa:** OpenClaw busca sus archivos en `/home/node/.openclaw/` asumiendo que corre como usuario `node`. Correr como root cambia el home esperado.

**Solución:** No usar `user: root` en compose. Todos los archivos que necesita `node` instalarlos con los permisos correctos desde el `Dockerfile` (como root durante el build, luego `USER node`).

---

## 7. Agente resumía el contenido de las tareas

**Problema:** El agente con `gpt-4o-mini` ignoraba las instrucciones de mostrar el enunciado completo y resumía o cortaba el contenido, especialmente en tareas largas.

**Causa:** `gpt-4o-mini` no sigue instrucciones estrictas de forma confiable con contenido largo. Tiende a resumir incluso cuando se le indica explícitamente que no lo haga.

**Solución:** Mantener `gpt-4o` como modelo principal. Si aparece un error genérico del provider, revisar primero que el entorno de Azure esté alineado con la config actual:

- `AZURE_OPENAI_BASE_URL`
- deployment/model configurado en OpenClaw

```json
"model": {
  "primary": "azure-openai-responses/gpt-4o"
}
```

---

## 8. Texto extraído de PDFs incompleto (imágenes y tablas)

**Problema:** Algunos documentos (PDFs con contenido escaneado o DOCX con tablas/imágenes) tienen secciones en blanco en `extracted_text`. El extractor actual (`pypdf` + `python-docx`) solo lee la capa de texto, no el contenido embebido como imágenes.

**Estado:** Identificado, pendiente de resolución.

**Solución propuesta:** Reemplazar `_extract_pdf` en `materials.py` con Azure Document Intelligence (`prebuilt-layout`), que extrae texto de PDFs escaneados, tablas y contenido mixto. El resultado se guarda en la base durante el `sync`, sin costo extra en consultas posteriores.

---

## Arquitectura de red (Podman rootless)

```
host
└── openclaw-gateway     → network_mode: host
    ├── resolv.conf montado desde ./docker/resolv.conf
    └── ejecuta la CLI local de school-guardian dentro del mismo contenedor
```

Con `network_mode: host`, OpenClaw sigue exponiendo el gateway directamente al host, pero las tools del agente ya no dependen de una API HTTP aparte.
