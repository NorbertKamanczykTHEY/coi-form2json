from .env import env


def load() -> dict:
    return {
        # dictionaryName alias -> canonical name; templates, match() and the REST API all resolve through this (Q22)
        "aliases": {"TERYT_DOWODOWY": "TERYT_4G_DOWODOWY"},
        "match_threshold": float(env().get("DICT_MATCH_THRESHOLD", "0.8")),  # label/coverage score for an existing dictionary
    }
