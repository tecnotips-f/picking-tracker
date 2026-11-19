"""Sincronización Offline-First con Firebase Auth y Cloud Firestore (API REST)."""
import requests

FIREBASE_PROJECT_ID = "cpicking-9c14b"
FIREBASE_API_KEY = "AIzaSyC1xhpT_0uJ9DPti2_GFIaFnFxVECLhCiQ"

AUTH_SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
AUTH_SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
AUTH_REFRESH_URL = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"


def _rut_a_email(rut: str) -> str:
    return f"{rut.lower()}@cpicking.cl"


def _clave_firebase(id_boosmap_o_clave: str) -> str:
    return f"cpk_{id_boosmap_o_clave}"


class FirebaseCloudSync:
    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.id_token: str | None = None
        self.refresh_token: str | None = None
        self.local_id: str | None = None

    @property
    def configurado(self) -> bool:
        clave = (FIREBASE_API_KEY or "").strip()
        return len(clave) > 20 and not clave.startswith("PEGA_")

    def autenticar_solo_login(self, rut: str, clave: str) -> str:
        """Verifica credenciales en Firebase Auth sin registrar usuarios nuevos.
        Devuelve: 'ok' | 'credenciales' | 'error_red'."""
        if not self.configurado:
            return "error_red"
        payload = {
            "email": _rut_a_email(rut),
            "password": _clave_firebase(clave),
            "returnSecureToken": True,
        }
        try:
            resp = requests.post(AUTH_SIGNIN_URL, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                self.id_token = data["idToken"]
                self.refresh_token = data["refreshToken"]
                self.local_id = data["localId"]
                return "ok"
            err = resp.json().get("error", {}).get("message", "")
            if err in ("EMAIL_NOT_FOUND", "INVALID_PASSWORD", "INVALID_LOGIN_CREDENTIALS"):
                return "credenciales"
            return "error_red"
        except Exception as ex:
            print(f"[FIREBASE LOGIN ERROR] {ex}")
            return "error_red"

    def autenticar_o_registrar(self, rut: str, clave: str) -> bool:
        """Inicia sesión en Firebase; si la cuenta Auth aún no existe, la crea."""
        if not self.configurado:
            return False
        estado = self.autenticar_solo_login(rut, clave)
        if estado == "ok":
            return True
        if estado == "credenciales":
            payload = {
                "email": _rut_a_email(rut),
                "password": _clave_firebase(clave),
                "returnSecureToken": True,
            }
            try:
                resp = requests.post(AUTH_SIGNUP_URL, json=payload, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    self.id_token = data["idToken"]
                    self.refresh_token = data["refreshToken"]
                    self.local_id = data["localId"]
                    return True
            except Exception as ex:
                print(f"[FIREBASE SIGNUP ERROR] {ex}")
        return False

    def renovar_token(self) -> bool:
        if not self.configurado or not self.refresh_token:
            return False
        try:
            resp = requests.post(
                AUTH_REFRESH_URL,
                data={"grant_type": "refresh_token", "refresh_token": self.refresh_token},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.id_token = data["id_token"]
                self.refresh_token = data["refresh_token"]
                return True
        except Exception:
            pass
        return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.id_token}", "Content-Type": "application/json"}

    # -------------------- USUARIOS Y SOLICITUDES --------------------
    def guardar_perfil_usuario(self, rut: str, nombre: str, correo: str | None, rol: str, activo: bool) -> bool:
        """Crea o actualiza el perfil del usuario en Firestore: usuarios/{rut}."""
        if not self.id_token:
            return False
        rut_norm = rut.lower()
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut_norm}"
        doc = {
            "fields": {
                "rut": {"stringValue": rut.upper()},
                "nombre": {"stringValue": str(nombre)},
                "correo": {"stringValue": str(correo or "")},
                "rol": {"stringValue": str(rol)},
                "activo": {"booleanValue": bool(activo)},
            }
        }
        try:
            resp = requests.patch(url, json=doc, headers=self._headers(), timeout=self.timeout)
            return resp.status_code == 200
        except Exception as ex:
            print(f"[FIREBASE PERFIL GUARDAR ERROR] {ex}")
            return False

    def obtener_perfil_usuario(self, rut: str) -> dict | None:
        """Lee el perfil usuarios/{rut} desde Firestore."""
        if not self.id_token:
            return None
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut.lower()}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if resp.status_code != 200:
                return None
            f = resp.json().get("fields", {})
            return {
                "rut": f.get("rut", {}).get("stringValue", rut.upper()),
                "nombre": f.get("nombre", {}).get("stringValue", "Usuario"),
                "correo": f.get("correo", {}).get("stringValue", "") or None,
                "rol": f.get("rol", {}).get("stringValue", "usuario"),
                "activo": bool(f.get("activo", {}).get("booleanValue", False)),
            }
        except Exception as ex:
            print(f"[FIREBASE PERFIL LEER ERROR] {ex}")
            return None

    def listar_todos_usuarios(self) -> list[dict]:
        """Solo el administrador puede listar todos los documentos en /usuarios."""
        if not self.id_token:
            return []
        url = f"{FIRESTORE_BASE_URL}/usuarios?pageSize=500"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if resp.status_code != 200:
                return []
            resultado = []
            for d in resp.json().get("documents", []):
                f = d.get("fields", {})
                rut_val = f.get("rut", {}).get("stringValue", "")
                if rut_val:
                    resultado.append({
                        "rut": rut_val.upper(),
                        "nombre": f.get("nombre", {}).get("stringValue", "Usuario"),
                        "correo": f.get("correo", {}).get("stringValue", "") or None,
                        "rol": f.get("rol", {}).get("stringValue", "usuario"),
                        "activo": bool(f.get("activo", {}).get("booleanValue", False)),
                    })
            return resultado
        except Exception as ex:
            print(f"[FIREBASE LISTAR USUARIOS ERROR] {ex}")
            return []

    def eliminar_usuario_nube(self, rut: str) -> bool:
        if not self.id_token:
            return False
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut.lower()}"
        try:
            resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
            return resp.status_code in (200, 404)
        except Exception:
            return False

    # -------------------- TARIFAS GLOBALES --------------------
    def subir_tarifas(self, tarifas: dict) -> bool:
        if not self.id_token:
            return False
        url = f"{FIRESTORE_BASE_URL}/config/tarifas"
        fields = {}
        for tipo, vals in tarifas.items():
            fields[f"{tipo}_base"] = {"doubleValue": float(vals["base"])}
            fields[f"{tipo}_unidad"] = {"doubleValue": float(vals["unidad"])}
        try:
            resp = requests.patch(url, json={"fields": fields}, headers=self._headers(), timeout=self.timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def descargar_tarifas(self) -> dict | None:
        if not self.id_token:
            return None
        url = f"{FIRESTORE_BASE_URL}/config/tarifas"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if resp.status_code != 200:
                return None
            f = resp.json().get("fields", {})
            resultado = {}
            for tipo in ("Picking", "Driver", "Shopper"):
                if f"{tipo}_base" in f and f"{tipo}_unidad" in f:
                    resultado[tipo] = {
                        "base": float(f[f"{tipo}_base"].get("doubleValue", 0)),
                        "unidad": float(f[f"{tipo}_unidad"].get("doubleValue", 0)),
                    }
            return resultado if len(resultado) == 3 else None
        except Exception:
            return None

    # -------------------- PEDIDOS --------------------
    def subir_pedido(self, rut: str, pedido: dict) -> bool:
        if not self.id_token:
            return False
        sg_doc = str(pedido["sg"]).replace("/", "_")
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut.lower()}/pedidos/{sg_doc}"
        doc = {
            "fields": {
                "fecha": {"stringValue": str(pedido["fecha"])},
                "sg": {"stringValue": str(pedido["sg"])},
                "tipo": {"stringValue": str(pedido["tipo"])},
                "skus": {"integerValue": str(int(pedido["skus"]))},
                "articulos": {"integerValue": str(int(pedido["articulos"]))},
                "ingreso": {"doubleValue": float(pedido["ingreso"])},
            }
        }
        try:
            resp = requests.patch(url, json=doc, headers=self._headers(), timeout=self.timeout)
            if resp.status_code == 401 and self.renovar_token():
                resp = requests.patch(url, json=doc, headers=self._headers(), timeout=self.timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def eliminar_pedido_nube(self, rut: str, sg: str) -> bool:
        if not self.id_token:
            return False
        sg_doc = str(sg).replace("/", "_")
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut.lower()}/pedidos/{sg_doc}"
        try:
            resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
            return resp.status_code in (200, 404)
        except Exception:
            return False

    def descargar_pedidos(self, rut: str) -> list[dict]:
        if not self.id_token:
            return []
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut.lower()}/pedidos?pageSize=1000"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if resp.status_code != 200:
                return []
            documentos = resp.json().get("documents", [])
            resultado = []
            for d in documentos:
                f = d.get("fields", {})
                resultado.append({
                    "fecha": f.get("fecha", {}).get("stringValue", ""),
                    "sg": f.get("sg", {}).get("stringValue", ""),
                    "tipo": f.get("tipo", {}).get("stringValue", "Picking"),
                    "skus": int(f.get("skus", {}).get("integerValue", 0)),
                    "articulos": int(f.get("articulos", {}).get("integerValue", 0)),
                    "ingreso": float(f.get("ingreso", {}).get("doubleValue", 0.0)),
                })
            return resultado
        except Exception:
            return []