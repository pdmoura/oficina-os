"""XML of the Sistema Nacional NFS-e, layout 1.01: build, validate, sign and pack.

Plain functions over lxml and cryptography, with no Odoo import, so they are easy to test.
Codes such as E0625 are the rejection rules of Annex I of the national layout; they explain
why an element is sent, left out or cleaned the way it is.
"""
import base64
import gzip
import hashlib
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
VERSION = "1.01"
# The schema allows 2000 characters, the layout annex still says 1000: stay within both.
MAX_DESCRIPTION = 1000
XSD_DIR = Path(__file__).resolve().parent.parent / "data" / "xsd"
EVENT_CANCEL = "101101"

_PUNCTUATION = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "−": "-", "•": "-", "…": "...", " ": " ", "\t": " ",
})
_SAFE_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)


class NfseXmlError(ValueError):
    """The XML would be rejected by the national schema; the message says where."""


# ----------------------------------------------------------------------
# Values
# ----------------------------------------------------------------------

def is_ibge_code(code):
    return bool(code) and len(code) == 7 and code.isdigit()


def clean_document(value):
    """CNPJ/CPF without punctuation. The CNPJ may be alphanumeric, so letters are kept."""
    return re.sub(r"[^0-9A-Z]", "", (value or "").upper())


def clean_text(value, max_length=None, multiline=False):
    """Text the schema accepts: characters U+0021-U+00FF, single spaces, no leading or trailing space (E1235)."""
    text = unicodedata.normalize("NFC", (value or "").replace("\r\n", "\n").translate(_PUNCTUATION))
    text = "".join(ch for ch in text if (ch == "\n" and multiline) or (" " <= ch <= "~") or ("¡" <= ch <= "ÿ"))
    lines = [re.sub(r" {2,}", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line) if multiline else " ".join(line for line in lines if line)
    if max_length and len(text) > max_length:
        text = text[:max_length].rstrip()
    return text


def money(value):
    return str(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def dps_id(city_ibge, document, series, number):
    """45 characters: DPS + city (7) + 1 CPF / 2 CNPJ + document (14) + series (5) + number (15). E0004 on mismatch."""
    kind = "1" if len(document) == 11 else "2"
    return f"DPS{city_ibge}{kind}{document.rjust(14, '0')}{int(series):05d}{int(number):015d}"


def number_from_access_key(key):
    """The note number sits at positions 24-36 of the 50-digit access key."""
    return key[23:36].lstrip("0") or "0"


def iss_rate_required(simples, simples_regime, withheld):
    """pAliq goes only for ME/EPP taxed through the Simples when the customer withholds the ISS (E0621).

    In every other case accepted by the national system the rate comes from the municipality's parameters
    and sending it is a rejection (E0600, E0604, E0617, E0625, E0635).
    """
    return simples == "3" and (simples_regime or "1") == "1" and withheld


def special_regime(simples, simples_regime, value):
    """MEI and ME/EPP taxed through the Simples must report no special regime (E0174, E0175)."""
    if simples == "2" or (simples == "3" and (simples_regime or "1") == "1"):
        return "0"
    return value or "0"


# ----------------------------------------------------------------------
# Building
# ----------------------------------------------------------------------

def _sub(parent, tag, text=None):
    node = etree.SubElement(parent, f"{{{NS}}}{tag}")
    if text is not None:
        node.text = str(text)
    return node


def _person_id(parent, document):
    _sub(parent, "CPF" if len(document) == 11 else "CNPJ", document)


def _address(parent, address):
    end = _sub(parent, "end")
    national = _sub(end, "endNac")
    _sub(national, "cMun", address["city_ibge"])
    _sub(national, "CEP", address["zip"])
    _sub(end, "xLgr", clean_text(address["street"], 255))
    _sub(end, "nro", clean_text(address.get("number") or "S/N", 60))
    if clean_text(address.get("complement")):
        _sub(end, "xCpl", clean_text(address["complement"], 156))
    _sub(end, "xBairro", clean_text(address["district"], 60))


def build_dps(data):
    """DPS (Declaração de Prestação de Serviço) for a note issued by the provider itself (tpEmit 1)."""
    provider, customer, service = data["provider"], data["customer"], data["service"]
    simples, simples_regime = provider["simples"], provider.get("simples_regime")

    root = etree.Element(f"{{{NS}}}DPS", nsmap={None: NS}, versao=VERSION)
    inf = _sub(root, "infDPS")
    inf.set("Id", data["id"])
    _sub(inf, "tpAmb", data["environment"])
    _sub(inf, "dhEmi", data["issued_at"].replace(microsecond=0).isoformat())
    _sub(inf, "verAplic", clean_text(data["app_version"], 20))
    _sub(inf, "serie", int(data["series"]))
    _sub(inf, "nDPS", int(data["number"]))
    _sub(inf, "dCompet", data["competence"].isoformat())
    _sub(inf, "tpEmit", 1)
    _sub(inf, "cLocEmi", data["city_ibge"])

    # The provider emits: no name nor address (E0121, E0128); the registry fills them in.
    prest = _sub(inf, "prest")
    _person_id(prest, provider["document"])
    if provider.get("municipal_registration"):
        _sub(prest, "IM", provider["municipal_registration"])
    regime = _sub(prest, "regTrib")
    _sub(regime, "opSimpNac", simples)
    if simples == "3":
        _sub(regime, "regApTribSN", simples_regime or "1")
    _sub(regime, "regEspTrib", special_regime(simples, simples_regime, provider.get("special_regime")))

    toma = _sub(inf, "toma")
    _person_id(toma, customer["document"])
    if customer.get("municipal_registration"):
        _sub(toma, "IM", customer["municipal_registration"])
    _sub(toma, "xNome", clean_text(customer["name"], 300))
    if customer.get("address"):
        _address(toma, customer["address"])
    phone = re.sub(r"\D", "", customer.get("phone") or "")
    if 6 <= len(phone) <= 20:
        _sub(toma, "fone", phone)
    email = clean_text(customer.get("email"), 80)
    if email and "@" in email:
        _sub(toma, "email", email)

    serv = _sub(inf, "serv")
    _sub(_sub(serv, "locPrest"), "cLocPrestacao", service["city_ibge"])
    code = _sub(serv, "cServ")
    _sub(code, "cTribNac", service["code"])
    if service.get("municipal_code"):
        _sub(code, "cTribMun", service["municipal_code"])
    _sub(code, "xDescServ", clean_text(service["description"], MAX_DESCRIPTION, multiline=True))
    if service.get("nbs"):
        _sub(code, "cNBS", service["nbs"])

    values = _sub(inf, "valores")
    _sub(_sub(values, "vServPrest"), "vServ", money(data["amount"]))
    trib = _sub(values, "trib")
    municipal = _sub(trib, "tribMun")
    _sub(municipal, "tribISSQN", 1)
    _sub(municipal, "tpRetISSQN", 2 if data["iss_withheld"] else 1)
    if iss_rate_required(simples, simples_regime, data["iss_withheld"]):
        _sub(municipal, "pAliq", money(data["iss_rate"]))
    total = _sub(trib, "totTrib")
    # Law 12.741 estimate: ME/EPP by its Simples rate, MEI may opt out, others by percentages (E0710-E0713).
    if simples == "3":
        _sub(total, "pTotTribSN", money(provider.get("simples_total_rate")))
    elif simples == "2":
        _sub(total, "indTotTrib", 0)
    else:
        shares = _sub(total, "pTotTrib")
        for tag, key in (("pTotTribFed", "tax_federal"), ("pTotTribEst", "tax_state"), ("pTotTribMun", "tax_municipal")):
            _sub(shares, tag, money(provider.get(key)))
    return root


def build_cancel_event(data):
    """Cancellation request (event 101101) of an issued note."""
    root = etree.Element(f"{{{NS}}}pedRegEvento", nsmap={None: NS}, versao=VERSION)
    inf = _sub(root, "infPedReg")
    inf.set("Id", f"PRE{data['access_key']}{EVENT_CANCEL}")
    _sub(inf, "tpAmb", data["environment"])
    _sub(inf, "verAplic", clean_text(data["app_version"], 20))
    _sub(inf, "dhEvento", data["issued_at"].replace(microsecond=0).isoformat())
    _sub(inf, "CPFAutor" if len(data["author_document"]) == 11 else "CNPJAutor", data["author_document"])
    _sub(inf, "chNFSe", data["access_key"])
    event = _sub(inf, f"e{EVENT_CANCEL}")
    _sub(event, "xDesc", "Cancelamento de NFS-e")
    _sub(event, "cMotivo", data["reason_code"])
    _sub(event, "xMotivo", clean_text(data["reason"], 255))
    return root


# ----------------------------------------------------------------------
# Validation, signature, transport
# ----------------------------------------------------------------------

def validate(root, schema="DPS_v1.01.xsd"):
    """Check against the official XSD before sending, with readable messages instead of an E1235."""
    xsd = etree.XMLSchema(etree.parse(str(XSD_DIR / schema), _SAFE_PARSER))
    if not xsd.validate(root):
        problems = []
        for error in xsd.error_log:
            message = re.sub(r"\{[^}]*\}", "", error.message)
            problems.append(message)
        raise NfseXmlError("\n".join(dict.fromkeys(problems)))


def _c14n(node):
    return etree.tostring(node, method="c14n", exclusive=False, with_comments=False)


def sign(root, key_pem, cert_pem):
    """Enveloped XMLDSig over the first child (infDPS / infPedReg), as the national manual specifies:
    inclusive C14N 1.0, RSA-SHA1, SHA-1 digest, the end certificate only in KeyInfo.
    Returns the final bytes: nothing may be re-serialised after signing (E0714)."""
    key = serialization.load_pem_private_key(key_pem, password=None)
    cert = x509.load_pem_x509_certificate(cert_pem)
    target = root[0]
    digest = base64.b64encode(hashlib.sha1(_c14n(target)).digest()).decode()

    signature = etree.SubElement(root, f"{{{DS}}}Signature", nsmap={None: DS})
    info = etree.SubElement(signature, f"{{{DS}}}SignedInfo")
    etree.SubElement(info, f"{{{DS}}}CanonicalizationMethod", Algorithm=C14N)
    etree.SubElement(info, f"{{{DS}}}SignatureMethod", Algorithm=DS + "rsa-sha1")
    reference = etree.SubElement(info, f"{{{DS}}}Reference", URI="#" + target.get("Id"))
    transforms = etree.SubElement(reference, f"{{{DS}}}Transforms")
    etree.SubElement(transforms, f"{{{DS}}}Transform", Algorithm=DS + "enveloped-signature")
    etree.SubElement(transforms, f"{{{DS}}}Transform", Algorithm=C14N)
    etree.SubElement(reference, f"{{{DS}}}DigestMethod", Algorithm=DS + "sha1")
    etree.SubElement(reference, f"{{{DS}}}DigestValue").text = digest
    value = key.sign(_c14n(info), padding.PKCS1v15(), hashes.SHA1())
    etree.SubElement(signature, f"{{{DS}}}SignatureValue").text = base64.b64encode(value).decode()
    x509_data = etree.SubElement(etree.SubElement(signature, f"{{{DS}}}KeyInfo"), f"{{{DS}}}X509Data")
    der = cert.public_bytes(serialization.Encoding.DER)
    etree.SubElement(x509_data, f"{{{DS}}}X509Certificate").text = base64.b64encode(der).decode()
    return b'<?xml version="1.0" encoding="UTF-8"?>' + etree.tostring(root, encoding="UTF-8", xml_declaration=False)


def verify(xml_bytes):
    """Recompute digest and signature with the embedded certificate (used by the tests)."""
    root = etree.fromstring(xml_bytes, _SAFE_PARSER)
    signature = root.find(f"{{{DS}}}Signature")
    target = root[0]
    expected = base64.b64encode(hashlib.sha1(_c14n(target)).digest()).decode()
    if signature.findtext(f".//{{{DS}}}DigestValue") != expected:
        return False
    der = base64.b64decode(signature.findtext(f".//{{{DS}}}X509Certificate"))
    public_key = x509.load_der_x509_certificate(der).public_key()
    try:
        public_key.verify(base64.b64decode(signature.findtext(f"{{{DS}}}SignatureValue")),
                          _c14n(signature.find(f"{{{DS}}}SignedInfo")), padding.PKCS1v15(), hashes.SHA1())
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def pack(xml_bytes):
    return base64.b64encode(gzip.compress(xml_bytes)).decode()


def unpack(value):
    return gzip.decompress(base64.b64decode(value))


def get_ci(payload, key, default=None):
    """The API has answered in camelCase and in PascalCase: read keys case-insensitively."""
    if not isinstance(payload, dict):
        return default
    wanted = key.lower()
    return next((value for name, value in payload.items() if name.lower() == wanted), default)


def format_messages(items):
    """`erros` (list), `erro` (object) or `alertas`, as readable lines: code - description - detail."""
    if not items:
        return ""
    if isinstance(items, dict):
        items = [items]
    lines = []
    for item in items:
        if not isinstance(item, dict):
            lines.append(str(item))
            continue
        parts = [str(get_ci(item, key)) for key in ("codigo", "descricao", "complemento") if get_ci(item, key)]
        lines.append(" - ".join(parts) or str(get_ci(item, "mensagem") or item))
    return "\n".join(lines)


def response_errors(payload):
    return format_messages(get_ci(payload, "erros") or get_ci(payload, "erro"))


# ----------------------------------------------------------------------
# Reading the authorised note
# ----------------------------------------------------------------------

def _text(node, path):
    if node is None:
        return ""
    found = node.find(path, {"n": NS})
    return (found.text or "").strip() if found is not None else ""


def parse_nfse(xml_bytes):
    root = etree.fromstring(xml_bytes, _SAFE_PARSER)
    inf = root.find("n:infNFSe", {"n": NS})
    return {
        "access_key": (inf.get("Id") or "")[3:] if inf is not None else "",
        "number": _text(inf, "n:nNFSe"),
        "processed_at": _text(inf, "n:dhProc"),
        "iss": _text(inf, "n:valores/n:vISSQN"),
        "net": _text(inf, "n:valores/n:vLiq"),
    }


TRIB_ISSQN = {"1": "Operação tributável", "2": "Imunidade", "3": "Exportação de serviço", "4": "Não incidência"}
RET_ISSQN = {"1": "Não retido", "2": "Retido pelo tomador", "3": "Retido pelo intermediário"}
SIMPLES = {"1": "Não optante", "2": "Optante - Microempreendedor Individual (MEI)",
           "3": "Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)"}
SIMPLES_REGIME = {"1": "Tributos federais e municipal pelo Simples Nacional",
                  "2": "Tributos federais pelo Simples Nacional e ISSQN por fora",
                  "3": "Tributos federais e municipal por fora do Simples Nacional"}
SPECIAL = {"0": "Nenhum", "1": "Ato cooperado", "2": "Estimativa", "3": "Microempresa municipal",
           "4": "Notário ou registrador", "5": "Profissional autônomo", "6": "Sociedade de profissionais",
           "9": "Outros"}


def br_money(value):
    if not value or value == "-":
        return "-"
    amount = f"{Decimal(value):,.2f}"
    return "R$ " + amount.replace(",", "X").replace(".", ",").replace("X", ".")


def br_percent(value):
    return f"{Decimal(value):.2f}".replace(".", ",") + "%" if value and value != "-" else "-"


def br_date(value):
    return f"{value[8:10]}/{value[5:7]}/{value[:4]}" if len(value or "") >= 10 else "-"


def br_datetime(value):
    return f"{br_date(value)} {value[11:19]}" if len(value or "") >= 19 else br_date(value)


def br_document(value):
    if len(value) == 14:
        return f"{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}"
    if len(value) == 11 and value.isdigit():
        return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"
    return value or "-"


def br_zip(value):
    return f"{value[:5]}-{value[5:]}" if len(value or "") == 8 else (value or "-")


def _party(node, name_path="n:xNome", address_path="n:end", national="n:endNac"):
    """Identification block of a person in the note, with "-" for what the XML does not carry (NT 008)."""
    address = node.find(address_path, {"n": NS}) if node is not None else None
    city = _text(address, f"{national}/n:cMun") if address is not None else ""
    return {
        "document": br_document(_text(node, "n:CNPJ") or _text(node, "n:CPF")),
        "municipal_registration": _text(node, "n:IM") or "-",
        "name": _text(node, name_path) or "-",
        "phone": _text(node, "n:fone") or "-",
        "email": _text(node, "n:email") or "-",
        "city_ibge": city or "-",
        "state": _text(address, f"{national}/n:UF") if address is not None else "",
        "zip": br_zip(_text(address, f"{national}/n:CEP")) if address is not None else "-",
        "street": ", ".join(filter(None, [_text(address, "n:xLgr"), _text(address, "n:nro"),
                                         _text(address, "n:xCpl"), _text(address, "n:xBairro")])) or "-",
    }


def danfse_data(xml_bytes):
    """Everything the DANFSe prints, read only from the authorised NFS-e XML, as NT 008 requires."""
    root = etree.fromstring(xml_bytes, _SAFE_PARSER)
    ns = {"n": NS}
    inf = root.find("n:infNFSe", ns)
    dps = inf.find("n:DPS/n:infDPS", ns)
    emit = inf.find("n:emit", ns)
    toma = dps.find("n:toma", ns)
    serv = dps.find("n:serv", ns)
    municipal = dps.find("n:valores/n:trib/n:tribMun", ns)
    regime = dps.find("n:prest/n:regTrib", ns)
    provider = _party(emit, address_path=".", national="n:enderNac")
    provider["street"] = ", ".join(filter(None, [_text(emit, "n:enderNac/n:xLgr"), _text(emit, "n:enderNac/n:nro"),
                                                 _text(emit, "n:enderNac/n:xCpl"), _text(emit, "n:enderNac/n:xBairro")])) or "-"
    total_share = _text(dps, "n:valores/n:trib/n:totTrib/n:pTotTribSN")
    shares = [_text(dps, f"n:valores/n:trib/n:totTrib/n:pTotTrib/n:{tag}") for tag in ("pTotTribFed", "pTotTribEst", "pTotTribMun")]
    if total_share:
        estimate = f"Tributos aproximados (Simples Nacional): {br_percent(total_share)}"
    elif any(shares):
        estimate = "Tributos aproximados: federais {}, estaduais {}, municipais {}".format(*[br_percent(s or "0") for s in shares])
    else:
        estimate = "Tributos aproximados: não informados (Lei 12.741/2012)"
    return {
        "environment": _text(dps, "n:tpAmb"),
        "access_key": (inf.get("Id") or "")[3:],
        "number": _text(inf, "n:nNFSe"),
        "competence": br_date(_text(dps, "n:dCompet")),
        "processed_at": br_datetime(_text(inf, "n:dhProc")),
        "dps_number": _text(dps, "n:nDPS"),
        "dps_series": _text(dps, "n:serie"),
        "dps_issued_at": br_datetime(_text(dps, "n:dhEmi")),
        "issuer": {"1": "Prestador", "2": "Tomador", "3": "Intermediário"}.get(_text(dps, "n:tpEmit"), "-"),
        "provider": provider,
        "provider_simples": SIMPLES.get(_text(regime, "n:opSimpNac"), "-"),
        "provider_simples_regime": SIMPLES_REGIME.get(_text(regime, "n:regApTribSN"), "-"),
        "customer": _party(toma) if toma is not None else None,
        "service": {
            "code": _text(serv, "n:cServ/n:cTribNac"),
            "code_name": _text(inf, "n:xTribNac") or "-",
            "municipal_code": _text(serv, "n:cServ/n:cTribMun") or "-",
            "municipal_code_name": _text(inf, "n:xTribMun") or "-",
            "nbs": _text(serv, "n:cServ/n:cNBS") or "-",
            "place": _text(inf, "n:xLocPrestacao") or "-",
            "description": _text(serv, "n:cServ/n:xDescServ"),
        },
        "iss": {
            "taxation": TRIB_ISSQN.get(_text(municipal, "n:tribISSQN"), "-"),
            "place": _text(inf, "n:xLocIncid") or "-",
            "special_regime": SPECIAL.get(_text(regime, "n:regEspTrib"), "-"),
            "base": br_money(_text(inf, "n:valores/n:vBC")),
            "rate": br_percent(_text(inf, "n:valores/n:pAliqAplic")),
            "withholding": RET_ISSQN.get(_text(municipal, "n:tpRetISSQN"), "-"),
            "amount": br_money(_text(inf, "n:valores/n:vISSQN")),
        },
        "federal": {
            "irrf": br_money(_text(dps, "n:valores/n:trib/n:tribFed/n:vRetIRRF")),
            "cp": br_money(_text(dps, "n:valores/n:trib/n:tribFed/n:vRetCP")),
            "csll": br_money(_text(dps, "n:valores/n:trib/n:tribFed/n:vRetCSLL")),
        },
        "totals": {
            "service": br_money(_text(dps, "n:valores/n:vServPrest/n:vServ")),
            "discount": br_money(_text(dps, "n:valores/n:vDescCondIncond/n:vDescIncond")),
            "conditional_discount": br_money(_text(dps, "n:valores/n:vDescCondIncond/n:vDescCond")),
            "withheld": br_money(_text(inf, "n:valores/n:vTotalRet")),
            "net": br_money(_text(inf, "n:valores/n:vLiq")),
        },
        "estimate": estimate,
        "extra": _text(inf, "n:xOutInf"),
    }
