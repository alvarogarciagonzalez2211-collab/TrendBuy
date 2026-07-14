import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Producto


VARIANT_WHITELIST = {"pro", "max", "plus", "mini", "ultra", "se", "fe", "lite"}

# Colors/finishes are real distinguishing SKUs with their own price, not cosmetic
# listing noise: live testing turned up "families" spanning a ~1400-2980EUR range
# because e.g. every color of iPhone 17 Pro Max was being merged into one entry
# purely because color words were stripped before matching. Treated the same way
# as VARIANT_WHITELIST below - an exact-match set, not fuzzy/dropped - so
# different colors of the same model stay separate families, while re-wordings of
# the SAME color across stores ("Negro" / "Negro" / "Negro espacial"... same set)
# still merge normally. Not exhaustive - an unrecognized color name just falls
# through to the fuzzy `base` comparison, which degrades gracefully rather than
# hard-failing.
COLOR_WHITELIST = {
    "negro", "blanco", "azul", "rosa", "gris", "plata", "plateado", "dorado",
    "dorada", "oro", "grafito", "verde", "morado", "purpura", "amarillo",
    "rojo", "naranja", "lila", "lavanda", "turquesa", "beige", "marron",
    "oscuro", "claro", "espacial", "cosmico", "medianoche", "natural",
    "salvia", "neblina", "coral", "menta", "malva", "crema", "titanio",
}

NOISE_TOKENS = {
    "libre", "reacondicionado", "seminuevo", "nuevo", "smartphone", "movil",
    "telefono", "5g", "4g", "dual", "sim", "esim", "de",
    "apple", "samsung", "xiaomi", "huawei", "sony", "google", "motorola",
    "oppo", "oneplus", "honor", "realme", "nokia",
}

# Captures storage capacity ("128gb", "128 gb", "1tb") and joins it into a single
# token (no internal space) instead of deleting it - storage is a real price-
# differentiating SKU attribute (256GB vs 512GB can be a EUR200+ gap), not
# cosmetic noise, so it becomes its own exact-match signature component below,
# the same way colors and variant qualifiers already do.
STORAGE_RE = re.compile(r"\b(\d+)\s?(gb|tb|mb)\b")
# Must run BEFORE punctuation is stripped to plain spaces, since it needs the
# quote-mark/word unit markers intact to recognize a screen-size measurement
# ("6.1''", "6,1 pulgadas") and drop it as a whole - otherwise a screen size
# like "6.1''" degrades to two bare digit tokens ("6", "1") that pollute the
# `numbers` signature (see same_family) and wrongly split one real model into
# two families whenever only one store's listing happens to mention it.
SCREEN_SIZE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:''|\"|pulgadas)", re.IGNORECASE)

DEFAULT_THRESHOLD = 80.0


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_name(name: str) -> str:
    text = strip_accents(name.lower())
    text = SCREEN_SIZE_RE.sub(" ", text)
    text = STORAGE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [token for token in text.split() if token and token not in NOISE_TOKENS]
    return " ".join(tokens)


STORAGE_TOKEN_RE = re.compile(r"^\d+(?:gb|tb|mb)$")


@dataclass(frozen=True)
class FamilySignature:
    base: str
    variants: frozenset[str] = field(default_factory=frozenset)
    numbers: frozenset[str] = field(default_factory=frozenset)
    colors: frozenset[str] = field(default_factory=frozenset)
    storage: frozenset[str] = field(default_factory=frozenset)


def family_signature(name: str) -> FamilySignature:
    tokens = normalize_name(name).split()
    variants = frozenset(token for token in tokens if token in VARIANT_WHITELIST)
    colors = frozenset(token for token in tokens if token in COLOR_WHITELIST)
    storage = frozenset(token for token in tokens if STORAGE_TOKEN_RE.match(token))
    # Standalone digit tokens carry the model generation (iPhone 13/14/15/16/17...).
    # These must be an exact-match component too, same as variants: on a short base
    # string like "iphone", a 1-character difference ("14" vs "15") barely moves
    # token_sort_ratio, while unrelated noise (an extra brand word) moves it more -
    # so generation numbers can't be left inside the fuzzy-compared base.
    numbers = frozenset(token for token in tokens if token.isdigit())
    excluded = variants | colors | storage | numbers
    base = " ".join(token for token in tokens if token not in excluded)
    return FamilySignature(base=base, variants=variants, numbers=numbers, colors=colors, storage=storage)


def same_family(a: FamilySignature, b: FamilySignature, threshold: float = DEFAULT_THRESHOLD) -> bool:
    # Variant qualifiers (Pro/Pro Max/Plus/...), color/finish, storage capacity, and
    # generation number must all match exactly as sets: a pure fuzzy ratio on the
    # full string scores "iphone 15 pro" vs "iphone 15 pro max" around 84, above
    # most reasonable thresholds, which would wrongly merge two different SKUs at
    # different price points - the same failure mode showed up for colors (a
    # "family" spanning a ~1400-2980EUR range because every color got merged) and
    # generation numbers.
    if a.variants != b.variants:
        return False

    if a.numbers != b.numbers:
        return False

    if a.colors != b.colors:
        return False

    if a.storage != b.storage:
        return False

    if not a.base or not b.base:
        return False

    return fuzz.token_sort_ratio(a.base, b.base) >= threshold


def group_by_family(items: list[dict], threshold: float = DEFAULT_THRESHOLD) -> list[list[dict]]:
    clusters: list[tuple[FamilySignature, list[dict]]] = []

    for item in items:
        name = item.get("name")
        if not name:
            continue

        signature = family_signature(name)
        for cluster_signature, cluster_items in clusters:
            if same_family(cluster_signature, signature, threshold):
                cluster_items.append(item)
                break
        else:
            clusters.append((signature, [item]))

    return [members for _, members in clusters]


async def find_matching_producto(
    session: AsyncSession,
    candidate_name: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> Producto | None:
    candidate_signature = family_signature(candidate_name)
    result = await session.execute(select(Producto))

    for producto in result.scalars():
        if same_family(candidate_signature, family_signature(producto.nombre), threshold):
            return producto

    return None
