"""Sincronización Offline-First con Firebase Auth y Cloud Firestore (API REST)."""
import os
import requests

FIREBASE_PROJECT_ID = "cpicking-9c14b"
FIREBASE_API_KEY = "AIzaSyC1xhpT_0uJ9DPti2_GFIaFnFxVECLhCiQ"

AUTH_SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
AUTH_SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
AUTH_REFRESH_URL = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"


def _rut_a_email(rut: str) -> str:
    """Convierte el RUT normalizado en un correo técnico para Firebase Auth."""
    return f"{rut.lower()}@cpicking.cl"


def _clave_firebase(id_boosmap_o_clave: str) -> str:
    """Garantiza al menos 8 caracteres para cumplir la política mínima de Firebase Auth."""
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

    def autenticar_o_registrar(self, rut: str, clave: str) -> bool:
        """Inicia sesión en Firebase; si el usuario aún no existe en la nube, lo crea automáticamente."""
        if not self.configurado:
            print("[FIREBASE] Falta configurar FIREBASE_API_KEY.")
            return False
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
                return True

            err_msg = resp.json().get("error", {}).get("message", "")
            print(f"[FIREBASE AUTH SIGNIN] {resp.status_code}: {err_msg}")
            if err_msg in ("EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS"):
                resp_reg = requests.post(AUTH_SIGNUP_URL, json=payload, timeout=self.timeout)
                if resp_reg.status_code == 200:
                    data = resp_reg.json()
                    self.id_token = data["idToken"]
                    self.refresh_token = data["refreshToken"]
                    self.local_id = data["localId"]
                    return True
                print(f"[FIREBASE AUTH SIGNUP] {resp_reg.status_code}: {resp_reg.text}")
        except Exception as ex:
            print(f"[FIREBASE AUTH ERROR] {ex}")
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
        except Exception as ex:
            print(f"[FIREBASE TOKEN ERROR] {ex}")
        return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.id_token}", "Content-Type": "application/json"}

    def subir_pedido(self, rut: str, pedido: dict) -> bool:
        """Guarda o actualiza un pedido en Firestore: usuarios/{rut}/pedidos/{sg}."""
        if not self.id_token:
            return False
        sg_doc = str(pedido["sg"]).replace("/", "_")
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut}/pedidos/{sg_doc}"
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
            if resp.status_code != 200:
                print(f"[FIREBASE FIRESTORE SUBIDA] {resp.status_code}: {resp.text}")
            return resp.status_code == 200
        except Exception as ex:
            print(f"[FIREBASE FIRESTORE ERROR] {ex}")
            return False

    def eliminar_pedido_nube(self, rut: str, sg: str) -> bool:
        """Elimina el documento en Firestore si el usuario borra el pedido en la app."""
        if not self.id_token:
            return False
        sg_doc = str(sg).replace("/", "_")
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut}/pedidos/{sg_doc}"
        try:
            resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
            return resp.status_code in (200, 404)
        except Exception as ex:
            print(f"[FIREBASE DELETE ERROR] {ex}")
            return False

    def descargar_pedidos(self, rut: str) -> list[dict]:
        """Recupera todos los pedidos respaldados de este RUT (útil al cambiar o reinstalar el móvil)."""
        if not self.id_token:
            return []
        url = f"{FIRESTORE_BASE_URL}/usuarios/{rut}/pedidos?pageSize=1000"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if resp.status_code != 200:
                print(f"[FIREBASE DESCARGA] {resp.status_code}: {resp.text}")
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
        except Exception as ex:
            print(f"[FIREBASE DESCARGA ERROR] {ex}")
            return []