from typing import Any, Dict, Optional


STAR_LABELS = {
    "alp": "α",
    "bet": "β",
    "gam": "γ",
    "del": "δ",
    "eps": "ε",
    "zet": "ζ",
    "eta": "η",
    "the": "θ",
    "iot": "ι",
    "kap": "κ",
    "lam": "λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "omi": "ο",
    "pi": "π",
    "rho": "ρ",
    "sig": "σ/ς",
    "tau": "τ",
    "ups": "υ",
    "phi": "φ",
    "chi": "χ",
    "psi": "ψ",
    "ome": "ω",
}


def resolve_star_label_metadata(
    bsc_star_or_string: Any
) -> Optional[Dict[str, Any]]:
    if bsc_star_or_string is None:
        return None

    if isinstance(bsc_star_or_string, str):
        label = bsc_star_or_string.strip()
        if not label:
            return None
        return {
            "text": label,
            "full_text": label,
        }

    greek = getattr(bsc_star_or_string, "greek", "") or ""
    greek_no = getattr(bsc_star_or_string, "greek_no", "") or ""
    constellation = (getattr(bsc_star_or_string, "constellation", "") or "").strip()

    if greek:
        greek_text = STAR_LABELS.get(greek)
        if greek_text:
            label = greek_text + greek_no
            return {
                "text": label,
                "full_text": label + (" " + constellation.capitalize() if constellation else ""),
            }

    flamsteed = (getattr(bsc_star_or_string, "flamsteed", "") or "").strip()
    if flamsteed:
        return {
            "text": flamsteed,
            "full_text": flamsteed,
        }

    hd = getattr(bsc_star_or_string, "HD", None)
    if hd is not None:
        return {
            "text": "",
            "full_text": "HD" + str(hd),
        }

    return None
