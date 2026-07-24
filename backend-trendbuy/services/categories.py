from services.matching import strip_accents


# Static taxonomy, same spirit as matching.py's VARIANT_WHITELIST/COLOR_WHITELIST:
# a small hand-curated keyword list per category, matched as a substring
# against the normalized product name. Not exhaustive - an unmatched product
# just belongs to no category, which only means it can't be favorited "by
# theme" (a specific-product favorite still works for anything).
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Moviles": [
        "iphone", "smartphone", "galaxy", "xiaomi", "redmi", "poco", "pixel",
        "moto g", "oneplus", "honor", "realme", "nokia", "movil",
    ],
    "Televisores": [
        "tv", "televisor", "qled", "oled", "smart tv", "uhd", "4k",
    ],
    "Portatiles": [
        "portatil", "laptop", "notebook", "macbook", "chromebook", "ultrabook",
    ],
    "Tablets": [
        "tablet", "ipad",
    ],
    "Auriculares": [
        "auriculares", "cascos", "airpods", "earbuds", "auricular",
    ],
    "Videojuegos": [
        "playstation", "xbox", "nintendo switch", "ps5", "ps4", "videojuego",
    ],
    "Electrodomesticos": [
        "frigorifico", "lavadora", "aspiradora", "microondas", "air fryer",
        "friggitrice", "lavavajillas", "secadora",
    ],
    "Informatica": [
        "monitor", "teclado", "raton inalambrico", "impresora", "disco duro",
        "ssd", "tarjeta grafica", "procesador",
    ],
    "Ropa": [
        "camiseta", "pantalon", "vaquero", "jean", "sudadera", "chaqueta", "vestido",
        "falda", "jersey", "abrigo", "camisa", "zapatilla", "calzado", "zapato",
        "polo", "bermuda", "chandal", "bufanda", "gorro", "bolso",
    ],
    "Hogar": [
        "silla", "sofa", "mesa", "estanteria", "armario", "colchon", "lampara",
        "mueble", "cortina", "alfombra", "cojin", "espejo", "escritorio", "cama",
    ],
    "Belleza": [
        "crema", "perfume", "maquillaje", "champu", "cosmetica", "serum",
        "protector solar", "colonia", "mascarilla facial", "labial", "gel de ducha",
    ],
    "Deportes": [
        "bicicleta", "mancuerna", "cinta de correr", "raqueta", "balon", "futbol",
        "padel", "esqui", "patinete", "fitness", "yoga", "running", "senderismo",
        "camiseta tecnica", "esterilla", "surf", "natacion", "gimnasio",
    ],
    "Libros": [
        "libro", "novela", "comic", "manga", "cuento", "trilogia", "tapa blanda",
        "tapa dura", "edicion de bolsillo",
    ],
    "Juguetes": [
        "juguete", "lego", "playmobil", "muneca", "peluche", "puzzle",
        "juego de mesa", "funko",
    ],
}


def match_categories(product_name: str) -> list[str]:
    normalized = strip_accents(product_name.lower())
    return [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
