# Setup — C.F. España post automático

## Cómo funciona

| Cuándo | Qué pasa |
|---|---|
| **Lunes 09:00** (Zúrich) | Genera imagen + texto con los **partidos de la semana** → te llega por email |
| **Domingo 21:00** (Zúrich) | Genera imagen + texto con los **resultados de la semana** → te llega por email |

Recibes el email → guardas la imagen → la subes a Instagram con el texto.

---

## Paso 1 — Subir el código a GitHub

1. Ve a **github.com** e inicia sesión
2. Haz clic en **"+"** (arriba a la derecha) → **New repository**
3. Nombre: `cfespana-posts` | Visibilidad: **Private** | haz clic en **Create repository**
4. En tu ordenador, abre la carpeta `cfespana_generator` en el terminal y ejecuta:

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/cfespana-posts.git
git push -u origin main
```

Sustituye `TU-USUARIO` por tu nombre de usuario de GitHub.

---

## Paso 2 — Crear una App Password de Gmail

GitHub necesita enviar emails en tu nombre. Gmail no permite usar tu contraseña normal — hay que crear una "App Password" (contraseña de aplicación):

1. Ve a **myaccount.google.com**
2. Seguridad → **Verificación en dos pasos** (actívala si no está activa)
3. Seguridad → busca **"Contraseñas de aplicaciones"** (App passwords)
4. Selecciona: App = "Correo", Dispositivo = "Otro" → escribe "GitHub Actions" → **Generar**
5. Copia la contraseña de 16 caracteres que aparece (tipo `abcd efgh ijkl mnop`)

---

## Paso 3 — Añadir los secrets en GitHub

Ve a tu repositorio en GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Añade estos 3 secrets:

| Nombre | Valor |
|---|---|
| `EMAIL_FROM` | tu email de Gmail (p.ej. `c.f.espana1994@gmail.com`) |
| `EMAIL_PASSWORD` | la App Password de 16 caracteres del paso anterior |
| `EMAIL_TO` | el email donde quieres recibir los posts (puede ser el mismo) |

---

## Paso 4 — Activar las GitHub Actions

1. En tu repositorio → pestaña **Actions**
2. Si aparece un aviso "Workflows aren't run on this repository" → haz clic en **"I understand my workflows, go ahead and enable them"**

---

## Paso 5 — Probar que funciona

1. Actions → **C.F. España Instagram post** → **Run workflow** → selecciona `preview` → **Run workflow**
2. Espera ~2 minutos
3. Comprueba tu email — debería llegar la imagen con los partidos de la semana

Si no llega, ve a Actions → haz clic en el último run → mira los logs del paso "Enviar por email".

---

## Paso 6 (opcional) — Publicar automáticamente en Instagram

Requiere convertir la cuenta @cfespanadeberna a **Business o Creator**:

1. Instagram → Configuración → Cuenta → **Cambiar tipo de cuenta** → Cuenta de creador (gratis, sin efectos visibles)
2. Vincula la cuenta a una **Facebook Page** (crea una vacía si no hay)
3. Ve a **developers.facebook.com** → My Apps → Create App → Business
4. Añade el producto "Instagram Graph API" → conecta la página
5. Graph API Explorer → permisos `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` → Generate token
6. Intercambia por long-lived token (~60 días):
   ```
   GET https://graph.facebook.com/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id=APP_ID
     &client_secret=APP_SECRET
     &fb_exchange_token=TOKEN_CORTO
   ```
7. Encuentra el IG User ID: `GET /me/accounts` → page id → `GET /<page-id>?fields=instagram_business_account`
8. Añade en GitHub Secrets: `IG_USER_ID` e `IG_TOKEN`
9. El repositorio tiene que ser **público** (o usar Cloudflare Pages / Netlify para servir las imágenes)

⚠️ El token expira cada ~60 días — renuévalo o el post del domingo fallará (el email seguirá funcionando).

---

## Actualizar el calendario de partidos

El calendario viene del fichero `Verein-v1368.ics`. Para renovarlo:

1. Ve a https://matchcenter.fvbj-afbj.ch/default.aspx?v=1368&oid=6&lng=1&a=vs
2. Menú → **Verein → Spielplan download**
3. Descarga el `.ics` y reemplaza `Verein-v1368.ics` en el repositorio

O añade este paso al workflow para que se descargue solo (requiere que la URL sea pública y estable).
