"""Cálculo de distância geográfica sem depender de nenhuma API paga de
mapas/rotas — usa a fórmula de Haversine (distância em linha reta entre
coordenadas), que é o suficiente para estimar a distância percorrida a
partir do rastro de pontos de GPS."""

import math

RAIO_TERRA_KM = 6371.0


def distancia_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, (lat1, lon1, lat2, lon2))
    delta_lat = lat2_r - lat1_r
    delta_lon = lon2_r - lon1_r

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return RAIO_TERRA_KM * c


def distancia_percorrida_km(pontos: list[tuple[float, float]]) -> float:
    """Soma a distância entre cada par de pontos consecutivos do rastro."""
    if len(pontos) < 2:
        return 0.0
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(pontos, pontos[1:]):
        total += distancia_haversine_km(lat1, lon1, lat2, lon2)
    return round(total, 2)
