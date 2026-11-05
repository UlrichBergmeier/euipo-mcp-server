"""Deterministic trademark candidate generation. Legal ratings must be supplied separately."""
from __future__ import annotations
from datetime import date

VALID = {"kennzeichnungskraeftig","beschreibend","zweifelhaft","unbekannt"}

def create_variants(mark, goods_services, territory="DE", word_assessments=None,
                    logo_present=False, logo_distinctive="unbekannt",
                    one_filing_only=False, always_used_together=False, compounds=None):
    if not isinstance(mark,str) or not mark.strip(): raise ValueError("Zeichen fehlt")
    if not isinstance(goods_services,str) or not goods_services.strip(): raise ValueError("Waren/Dienstleistungen fehlen")
    if territory not in {"DE","EU"}: raise ValueError("Schutzgebiet muss DE oder EU sein")
    if logo_distinctive not in VALID: raise ValueError("Ungültige Logoeinschätzung")
    words=mark.split()
    if len(words)>30: raise ValueError("Zu viele getrennte Bestandteile")
    assessments=word_assessments or {}
    compounds=compounds or {}
    if any(w not in words or rating not in VALID for w,rating in assessments.items()):
        raise ValueError("Bewertungen müssen vollständige Wörter betreffen")
    if any(w not in words or not isinstance(parts,list) or not all(isinstance(p,str) and p.strip() for p in parts) for w,parts in compounds.items()):
        raise ValueError("Zusammensetzung ungültig")
    distinctive=list(dict.fromkeys(w for w in words if assessments.get(w)=="kennzeichnungskraeftig"))
    variants=[]
    seen=set()
    def add(kind,sign,priority,recommendation,benefit,drawback):
        if (kind,sign) in seen:return
        seen.add((kind,sign))
        variants.append({"markenart":kind,"zeichen":sign,"prioritaet":priority,"empfehlung":recommendation,
                         "vorteil":benefit,"nachteil":drawback,"eintragungsprognose":"separat rechtlich prüfen"})
    for w in distinctive:
        add("Wortmarke",w,1,"vorrangig prüfen","Von Schrift und Farbe unabhängig","Logo separat prüfen")
    if len(words)>1 or not distinctive:
        add("Wortmarke",mark.strip(),None,"Gesamtzeichen prüfen","Wortfolge ohne besondere Grafik","Beschreibende Anteile und Unterscheidungskraft gesondert beurteilen")
    if logo_present:
        add("Bildmarke","Logo allein",2 if logo_distinctive=="kennzeichnungskraeftig" else None,
            "eigenständige Anmeldung prüfen","Eigenständiger Schutz der Grafik","Farbneutralität ist kein Schutz für sämtliche Farbvarianten")
        core=" ".join(distinctive) if distinctive else mark.strip()
        add("Wort-/Bildmarke",f"Logo + {core}",1 if one_filing_only and always_used_together else 3,
            "Ein-Marken-Alternative" if one_filing_only and always_used_together else "nachrangige Option",
            "Konkrete Kombination","Keine gleichwertige Trennung von Wort- und Bildschutz")
        if core!=mark.strip():
            add("Wort-/Bildmarke",f"Logo + {mark.strip()}",None,"optional","Gesamtgestaltung","Beschreibende Zusätze können Mehrwert begrenzen")
    return {"zeichen":mark.strip(),"waren_dienstleistungen":goods_services.strip(),"schutzgebiet":territory,
            "bestandteile":[{"wort":w,"interne_wortbestandteile":compounds.get(w,[]),
              "einschaetzung":assessments.get(w,"unbekannt"),"wegpraegung_interner_bestandteile":False} for w in words],
            "varianten":sorted(variants,key=lambda x:(x["prioritaet"] is None,x["prioritaet"] or 99)),
            "recherchestand":{"register":"nicht durchgeführt","internet":"nicht durchgeführt","kollision":"nicht durchgeführt"},
            "hinweise":["Interne Wortbestandteile dürfen nicht weggeprägt werden.",
                        "Das Gesamtzeichen muss stets geprüft werden.",
                        "Keine Eintragungsgarantie."]}

def comparative_age(application_date, reference_date=None):
    d=date.fromisoformat(application_date)
    today=reference_date or date.today()
    if d>today: raise ValueError("Anmeldedatum liegt in der Zukunft")
    return {"jahre_seit_anmeldung":round((today-d).days/365.2425,1),
            "bewertung":"Historischen Kontext und aktuellen Sprachgebrauch prüfen",
            "hinweis":"Voreintragungen begründen keinen Eintragungsanspruch"}
