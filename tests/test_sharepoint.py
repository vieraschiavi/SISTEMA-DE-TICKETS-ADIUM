import json

from tickets_ec import exportar, sharepoint


class _Resp:
    def __init__(self, cuerpo):
        self.cuerpo = cuerpo

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _items_de(db):
    """Las filas de la mesa con la forma en que Graph las devuelve."""
    listas = {"Tickets": [], "Eventos": [], "Encuestas": [], "Personas": []}
    inv = {lista: {col: interno for interno, _t, _o, col in sharepoint.LISTAS[lista] if col}
           for lista in listas}

    def campos(lista, fila):
        out = {}
        for col, interno in inv[lista].items():
            v = fila.get(col)
            out[interno] = v.isoformat() if hasattr(v, "isoformat") else v
        return out

    numero = {t["id"]: t["numero"] for t in db.tickets()}
    listas["Tickets"] = [campos("Tickets", t) for t in db.tickets()]
    listas["Eventos"] = [{**campos("Eventos", e), "TicketNumero": numero[e["ticket_id"]]} for e in db.eventos()]
    listas["Encuestas"] = [{**campos("Encuestas", e), "Title": numero[e["ticket_id"]]} for e in db.encuestas()]
    listas["Personas"] = [campos("Personas", p) for p in db.consulta("SELECT * FROM personas")]
    return listas


def test_desde_sharepoint_da_el_mismo_modelo_que_la_base(demo_corta):
    listas = _items_de(demo_corta.db)

    def abrir(req, timeout=30):
        if "oauth2" in req.full_url:
            return _Resp(b'{"access_token": "t"}')
        lista = req.full_url.split("/lists/")[1].split("/")[0]
        # Dos páginas, para probar @odata.nextLink.
        filas = listas[lista]
        if "pagina2" in req.full_url:
            return _Resp(json.dumps({"value": [{"fields": f} for f in filas[len(filas) // 2:]]}).encode())
        return _Resp(json.dumps({"value": [{"fields": f} for f in filas[:len(filas) // 2]],
                                 "@odata.nextLink": req.full_url + "&pagina2"}).encode())

    cliente = sharepoint.ClienteGraph("t", "c", "s", abrir=abrir)
    db = sharepoint.cargar(cliente, "sitio")
    ahora = demo_corta.ahora()
    a = exportar.tablas(demo_corta.db, demo_corta.cfg, ahora)
    b = exportar.tablas(db, demo_corta.cfg, ahora)
    assert a["Tickets"] == b["Tickets"]
    assert a["Estados"] == b["Estados"]
    assert [(e["Número"], e["Resultado"], e["CSAT"]) for e in a["Encuestas"]] == [
        (e["Número"], e["Resultado"], e["CSAT"]) for e in b["Encuestas"]]


def test_desde_los_csv_del_flujo_6(demo_corta, tmp_path):
    import csv
    for lista, filas in _items_de(demo_corta.db).items():
        with open(tmp_path / f"{lista}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows({k: ("" if v is None else v) for k, v in fila.items()} for fila in filas)
    db = sharepoint.cargar(sharepoint.ClienteCarpeta(tmp_path))
    ahora = demo_corta.ahora()
    assert exportar.tablas(db, demo_corta.cfg, ahora)["Tickets"] == exportar.tablas(
        demo_corta.db, demo_corta.cfg, ahora)["Tickets"]
