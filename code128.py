"""Decodificador de Code 128 en Python puro (solo NumPy).

Sirve cuando zxing-cpp no esta disponible (por ejemplo en el APK de Android).
Solo devuelve texto si el digito de control (checksum) es valido, asi que
nunca entrega un numero "aproximado": o lee bien, o no lee nada.
"""
import numpy as np

# Anchos barra/espacio de los 106 simbolos (0-102 datos, 103-105 inicio A/B/C)
_PATRONES = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232",
]
_STOP = "2331112"
_INICIO = {103: "A", 104: "B", 105: "C"}
_TOL_SIMBOLO = 0.35      # error medio permitido por elemento (en modulos)

_P = np.array([[int(c) for c in p] for p in _PATRONES], dtype=float)      # 106 x 6
_P_DATOS = _P[:103]
_P_INICIO = _P[103:106]
_P_STOP = np.array([int(c) for c in _STOP], dtype=float)                  # 7


def _igualar(v, patrones, modulos):
    """Error medio de la ventana v frente a cada patron (v en unidades de modulo)."""
    tot = v.sum()
    if tot <= 0:
        return None
    return np.abs(v * (modulos / tot) - patrones).sum(axis=1) / len(v)


def _decodificar_runs(runs, espacio_previo=0.0):
    """runs: anchos alternados barra, espacio, barra... empezando en barra.

    espacio_previo: ancho del espacio blanco anterior al primer run (zona de silencio).
    """
    n = len(runs)
    if n < 20:
        return None
    # Busqueda vectorizada de todos los posibles simbolos de inicio
    ventanas = np.lib.stride_tricks.sliding_window_view(runs, 6)[0::2]
    tot = ventanas.sum(axis=1, keepdims=True)
    norm = ventanas * (11.0 / np.maximum(tot, 1e-9))
    errs = np.abs(norm[:, None, :] - _P_INICIO[None, :, :]).sum(axis=2) / 6.0
    candidatos = np.flatnonzero(errs.min(axis=1) <= _TOL_SIMBOLO)
    for c in candidatos:
        i = int(c) * 2
        ini = 103 + int(errs[c].argmin())
        modulo = float(runs[i:i + 6].sum()) / 11.0
        previo = float(runs[i - 1]) if i > 0 else float(espacio_previo)
        if previo < 2.5 * modulo:                 # exige zona de silencio antes del inicio
            continue
        j = i + 6
        simbolos = []
        terminado = False
        while j + 6 <= n:
            e_d = _igualar(runs[j:j + 6], _P_DATOS, 11.0)
            if e_d is None:
                break
            s = int(e_d.argmin())
            e = float(e_d[s])
            e_st = 99.0
            if j + 7 <= n:
                tot7 = runs[j:j + 7].sum()
                if tot7 > 0:
                    e_st = float(np.abs(runs[j:j + 7] * (13.0 / tot7) - _P_STOP).sum() / 7.0)
            # Es el final solo si encaja mejor como STOP que como simbolo de datos
            if e_st <= _TOL_SIMBOLO and (e > _TOL_SIMBOLO or e_st < e):
                terminado = True
                break
            if e > _TOL_SIMBOLO:
                break
            simbolos.append(s)
            j += 6
            if len(simbolos) > 80:
                break
        if not terminado or len(simbolos) < 3:    # 2 datos + checksum como minimo
            continue
        posterior = float(runs[j + 7]) if j + 7 < n else None
        if posterior is not None and posterior < 2.5 * modulo:
            continue                              # exige zona de silencio despues del STOP
        texto = _interpretar(ini, simbolos)
        if texto:
            return texto
    return None


def _interpretar(inicio, simbolos):
    """Valida checksum y devuelve el texto, o None si no cuadra."""
    *datos, check = simbolos
    suma = inicio
    for pos, v in enumerate(datos, start=1):
        suma += pos * v
    if suma % 103 != check:
        return None
    juego = _INICIO[inicio]
    salida = []
    desplazado = False
    for v in datos:
        if juego == "C":
            if v < 100:
                salida.append("%02d" % v)
            elif v == 100:
                juego = "B"
            elif v == 101:
                juego = "A"
            # 102 = FNC1: se ignora
            continue
        if v == 99:
            juego = "C"
        elif v == 100 and juego != "B":
            juego = "B"
        elif v == 101 and juego != "A":
            juego = "A"
        elif v == 98:
            desplazado = True
            continue
        elif v >= 96:
            pass                                  # FNC / codigos de control: se ignoran
        else:
            usar = juego
            if desplazado:
                usar = "A" if juego == "B" else "B"
                desplazado = False
            if usar == "B":
                salida.append(chr(32 + v))
            else:
                salida.append(chr(32 + v) if v < 64 else chr(v - 64))
    return "".join(salida) if salida else None


def _runs_de_fila(fila, umbral):
    binaria = fila < umbral                       # True = barra (oscuro)
    cambios = np.flatnonzero(binaria[1:] != binaria[:-1]) + 1
    bordes = np.concatenate(([0], cambios, [len(binaria)]))
    longitudes = np.diff(bordes).astype(float)
    if len(longitudes) < 20:
        return None
    previo = 0.0
    if not binaria[0]:                            # empezar siempre en una barra
        previo = float(longitudes[0])
        longitudes = longitudes[1:]
    return longitudes, previo


def _suavizar(fila, k=3):
    if k <= 1:
        return fila
    ker = np.ones(k) / k
    return np.convolve(fila, ker, mode="same")


def _leer_gris(gris, filas=21):
    """Devuelve el texto solo si lo leen al menos 2 filas distintas (evita lecturas falsas)."""
    h, w = gris.shape
    if w < 60:
        return None
    ys = np.linspace(h * 0.1, h * 0.9, filas).astype(int) if h > 10 else [h // 2]
    votos = {}
    for y in ys:
        y0, y1 = max(0, y - 1), min(h, y + 2)
        fila = gris[y0:y1].mean(axis=0)
        bajo, alto = np.percentile(fila, 5), np.percentile(fila, 95)
        if alto - bajo < 40:                      # sin contraste suficiente
            continue
        texto_fila = None
        for k in (1, 3):
            f = _suavizar(fila, k)
            for frac in (0.5, 0.4):
                umbral = bajo + (alto - bajo) * frac
                for sentido in (f, f[::-1]):      # normal y codigo al reves
                    res = _runs_de_fila(sentido, umbral)
                    if res is None:
                        continue
                    texto_fila = _decodificar_runs(res[0], res[1])
                    if texto_fila:
                        break
                if texto_fila:
                    break
            if texto_fila:
                break
        if texto_fila:
            votos[texto_fila] = votos.get(texto_fila, 0) + 1
            if votos[texto_fila] >= 2:
                return texto_fila
    return None


def _girar(gris, angulo):
    """Gira la imagen en gris 'angulo' grados. Usa OpenCV si existe; si no, Pillow."""
    borde = float(np.percentile(gris, 95))
    try:
        import cv2
        h, w = gris.shape
        m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angulo, 1.0)
        return cv2.warpAffine(gris.astype(np.float32), m, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=borde)
    except ImportError:
        pass
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.fromarray(gris.astype(np.float32), mode="F")
    im = im.rotate(angulo, resample=Image.BILINEAR, fillcolor=borde)
    return np.asarray(im, dtype=np.float32)


def decodificar_code128(imagen):
    """Lee un Code 128 de una imagen (BGR, RGB o gris) como array NumPy.

    Prueba la imagen en horizontal con pequenos giros (por si el codigo esta inclinado)
    y despues girada 90 grados. Devuelve el texto exacto o None.
    """
    img = np.asarray(imagen)
    if img.ndim == 3:
        gris = img[:, :, :3].astype(np.float32).mean(axis=2)
    else:
        gris = img.astype(np.float32)
    for angulo in (0, 5, -5, 10, -10):
        g = gris if angulo == 0 else _girar(gris, angulo)
        if g is None:
            continue
        texto = _leer_gris(g)
        if texto:
            return texto
    return _leer_gris(np.rot90(gris))
