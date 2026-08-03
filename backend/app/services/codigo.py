import random
import string


def gerar_localizador(tamanho: int = 6) -> str:
    alfabeto = string.ascii_uppercase + string.digits
    return "".join(random.choices(alfabeto, k=tamanho))
