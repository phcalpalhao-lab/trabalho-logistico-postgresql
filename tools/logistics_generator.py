"""Offline synthetic data generator for the existing projeto_logistico schema.

This module deliberately has no PostgreSQL driver and cannot write to a database.
The column catalog was compared with A3 metadata on 2026-10-08; no differences
were found, and that confirmation is recorded in every manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


SEED = 20261008
GENERATOR_VERSION = "2.1.0"
POSTGRES_INTEGER_MAX = 2**31 - 1
INVENTORY_CLASSES = (
    "healthy",
    "near_minimum",
    "at_minimum",
    "below_minimum",
    "zero_available",
    "without_stock",
)
SCHEMA_STATUS = "CONFIRMED_A3_NO_DIVERGENCES"
SCHEMA_CONFIRMED_AT = "2026-10-08"
PERIOD_START = date(2025, 1, 1)
PERIOD_END = date(2026, 9, 30)


@dataclass(frozen=True)
class Column:
    name: str
    kind: str
    nullable: bool = True
    limit: int | None = None
    precision: int | None = None
    scale: int | None = None


@dataclass(frozen=True)
class InventoryScenarioConfig:
    class_weights: tuple[tuple[str, float], ...] = (
        ("healthy", 0.35),
        ("near_minimum", 0.15),
        ("at_minimum", 0.15),
        ("below_minimum", 0.15),
        ("zero_available", 0.10),
        ("without_stock", 0.10),
    )
    near_minimum_max_gap: int = 3
    healthy_surplus_range: tuple[int, int] = (20, 100)
    high_reservation_share: float = 0.15
    inactive_with_stock_share: float = 0.10
    multi_warehouse_share: float = 0.40

    def __post_init__(self) -> None:
        if not isinstance(self.class_weights, tuple):
            raise ValueError("class_weights must be a tuple of (class_name, weight) pairs")
        if any(
            not isinstance(item, tuple) or len(item) != 2
            for item in self.class_weights
        ):
            raise ValueError(
                "class_weights entries must be (class_name, weight) pairs"
            )
        class_names = [name for name, _ in self.class_weights]
        if any(not isinstance(name, str) for name in class_names):
            raise ValueError("class_weights class names must be strings")
        if len(class_names) != len(set(class_names)) or set(class_names) != set(INVENTORY_CLASSES):
            raise ValueError(f"class_weights must define each inventory class exactly once: {INVENTORY_CLASSES}")
        weights = [weight for _, weight in self.class_weights]
        if any(not isinstance(weight, (int, float)) or isinstance(weight, bool)
               or weight < 0 or weight > 1 or not math.isfinite(weight)
               for weight in weights):
            raise ValueError("class_weights must be finite non-negative numbers")
        if not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("class_weights must sum to 1")
        if (not isinstance(self.near_minimum_max_gap, int)
                or isinstance(self.near_minimum_max_gap, bool)
                or self.near_minimum_max_gap < 1):
            raise ValueError("near_minimum_max_gap must be a positive integer")
        if (not isinstance(self.healthy_surplus_range, tuple)
                or len(self.healthy_surplus_range) != 2
                or any(not isinstance(value, int) or isinstance(value, bool)
                       for value in self.healthy_surplus_range)
                or self.healthy_surplus_range[0] < 1
                or self.healthy_surplus_range[1] < self.healthy_surplus_range[0]):
            raise ValueError("healthy_surplus_range must be an ascending pair of positive integers")
        if self.healthy_surplus_range[0] <= self.near_minimum_max_gap:
            raise ValueError(
                "healthy_surplus_range must start above near_minimum_max_gap"
            )
        for name, value in (
            ("high_reservation_share", self.high_reservation_share),
            ("inactive_with_stock_share", self.inactive_with_stock_share),
            ("multi_warehouse_share", self.multi_warehouse_share),
        ):
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not 0 <= value <= 1 or not math.isfinite(value)):
                raise ValueError(f"{name} must be between 0 and 1")


def c(name: str, kind: str, *, nn: bool = False, limit: int | None = None,
      precision: int | None = None, scale: int | None = None) -> Column:
    return Column(name, kind, not nn, limit, precision, scale)


SCHEMA: dict[str, tuple[Column, ...]] = {
    "t_armazem": (
        c("id_armazem", "integer", nn=True), c("nome_armazem", "text", limit=100),
        c("endereÇo", "text", limit=200), c("cidade", "text", limit=100),
        c("estado", "char", limit=2), c("capacidade", "integer"),
        c("ativo", "char", limit=1),
    ),
    "t_avaria": (
        c("id_avaria", "integer", nn=True), c("data_avaria", "date"),
        c("quantidade", "integer"), c("tipo_avaria", "text", limit=30),
        c("descriÇÃo", "text", limit=200),
        c("custo_estimado", "decimal", precision=12, scale=2),
        c("status_avaria", "text", limit=20),
        c("t_estoque_id_estoque", "integer", nn=True),
    ),
    "t_categoria": (
        c("id_categoria", "integer", nn=True), c("nome_categoria", "text", limit=100),
        c("descriÇÃo", "text", limit=200), c("ativo", "char", limit=1),
    ),
    "t_clientes": (
        c("id_clientes", "integer", nn=True), c("nome", "text", nn=True, limit=200),
        c("cpf_cnpj", "text", nn=True, limit=20), c("email", "text", nn=True, limit=100),
        c("endereÇo", "text", nn=True, limit=20), c("data_cadastro", "date"),
        c("status", "text", limit=20),
    ),
    "t_compra": (
        c("id_compra", "integer", nn=True), c("data_compra", "date"),
        c("data_previsÃo", "date"), c("status_compra", "text", limit=20),
        c("valor_total", "decimal", precision=12, scale=2),
        c("numero_total", "text", limit=30),
        c("t_fornecedor_id_fornecedor", "integer", nn=True),
    ),
    "t_devolucao": (
        c("id_devoluÇÃo", "integer", nn=True), c("data_solicitaÇÃo", "date"),
        c("motivo", "text", limit=200), c("status_devoluÇÃo", "text", limit=30),
        c("data_conclusÃo", "date"),
        c("valor_reembolso", "decimal", precision=12, scale=2),
        c("t_pedidos_id_pedidos", "integer", nn=True),
    ),
    "t_entrega": (
        c("id_entrega", "integer", nn=True), c("codigo_rastreio", "text", limit=50),
        c("data_envio", "date"), c("data_prevista", "date"),
        c("data_entrega", "date"), c("status_entrega", "text", limit=30),
        c("valor_frete", "decimal", precision=10, scale=2),
        c("t_pedidos_id_pedidos", "integer", nn=True),
        c("id_transportadora", "integer", nn=True),
    ),
    "t_estoque": (
        c("id_estoque", "integer", nn=True), c("quantidade_atual", "integer"),
        c("quantidade_reservada", "integer"), c("localizaÇÃo", "text", limit=30),
        c("ultima_atualizaÇÃo", "date"),
        c("t_produto_id_produto", "integer", nn=True),
        c("t_armazem_id_armazem", "integer", nn=True),
    ),
    "t_fornecedor": (
        c("id_fornecedor", "integer", nn=True), c("razao_social", "text", limit=120),
        c("nome_fantasia", "text", limit=100), c("cnpj", "text", limit=20),
        c("email", "text", limit=100), c("telefone", "text", nn=True, limit=20),
        c("prazo_entrega_dias", "integer"), c("ativo", "char", limit=1),
    ),
    "t_historico_entrega": (
        c("id_historico", "integer", nn=True), c("data_evento", "date"),
        c("status_evento", "text", limit=30), c("local_evento", "text", limit=100),
        c("observaÇÃo", "text", limit=200),
        c("t_entrega_id_entrega", "integer", nn=True),
    ),
    "t_inventario": (
        c("id_inventario", "integer", nn=True), c("data_abertura", "date"),
        c("data_fechamento", "date"), c("status_inventario", "text", limit=20),
        c("observaÇÃo", "text", limit=200),
        c("t_armazem_id_armazem", "integer", nn=True),
    ),
    "t_item_compra": (
        c("id_item_compra", "integer", nn=True), c("quantidade", "integer"),
        c("preÇo_unitario", "decimal", precision=10, scale=2),
        c("subtotal", "decimal", precision=12, scale=2),
        c("t_compra_id_compra", "integer", nn=True),
        c("t_produto_id_produto", "integer", nn=True),
    ),
    "t_item_devolucao": (
        c("id_item_devoluÇÃo", "integer", nn=True), c("quantidade", "integer"),
        c("condiÇÃo_produto", "text", limit=30), c("motivo_item", "text", limit=200),
        c("t_devoluÇÃo_id_devoluÇÃo", "integer", nn=True),
        c("t_item_pedido_id_item_pedido", "integer", nn=True),
    ),
    "t_item_inventario": (
        c("id_item_inventario", "integer", nn=True),
        c("quantidade_sistema", "integer"), c("quantidade_contada", "integer"),
        c("diferenÇa", "integer"), c("observaÇÃo", "text", limit=200),
        c("t_inventario_id_inventario", "integer", nn=True),
        c("t_estoque_id_estoque", "integer", nn=True),
    ),
    "t_item_pedido": (
        c("id_item_pedido", "integer", nn=True), c("quantidade", "integer", nn=True),
        c("preco_unitario", "decimal", precision=10, scale=2),
        c("desconto", "decimal", precision=10, scale=2),
        c("subtotal", "decimal", precision=10, scale=2),
        c("t_pedidos_id_pedidos", "integer", nn=True),
        c("t_produto_id_produto", "integer", nn=True),
    ),
    "t_movimentaÇÃo_estoque": (
        c("id_movimentaÇÃo", "integer", nn=True),
        c("tipo_movimentação", "text", limit=20), c("quantidade", "integer"),
        c("data_movimentação", "date"), c("motivo", "text", limit=200),
        c("documento_referencia", "text", limit=50),
        c("t_estoque_id_estoque", "integer", nn=True),
    ),
    "t_pagamento": (
        c("id_pagamento", "integer", nn=True), c("data_pagamento", "date"),
        c("valor_pago", "decimal", precision=12, scale=2),
        c("forma_pagamento", "text", limit=30),
        c("status_pagamento", "text", limit=20),
        c("codigo_transaÇÃo", "text", limit=80),
        c("t_pedidos_id_pedidos", "integer", nn=True),
    ),
    "t_pedidos": (
        c("id_pedidos", "integer", nn=True),
        c("t_clientes_id_clientes", "integer", nn=True),
        c("data_pedido", "date"), c("status_pedidos", "text", limit=20),
        c("valor_total", "decimal", precision=10, scale=2),
    ),
    "t_produto": (
        c("id_produto", "integer", nn=True), c("sku", "text", limit=50),
        c("nome", "text", nn=True, limit=100), c("descriÇao", "text", limit=200),
        c("peso_kg", "decimal", precision=8, scale=2),
        c("dimensoes", "text", limit=50),
        c("preÇo_custo", "decimal", precision=10, scale=2),
        c("peÇo_venda", "decimal", precision=10, scale=2),
        c("estoque_minimo", "integer"), c("ativo", "char", limit=1),
        c("t_categoria_id_categoria", "integer", nn=True),
    ),
    "t_transportadora": (
        c("id_transpotadora", "integer", nn=True),
        c("razao_social", "text", limit=120), c("cnpj", "text", limit=20),
        c("telefone", "text", nn=True, limit=20), c("email", "text", limit=100),
        c("tipo_trasnporte", "text", limit=30),
        c("prazo_medio_dias", "integer"), c("ativo", "char", limit=1),
    ),
}

FULL_COUNTS = {
    "t_armazem": 4, "t_avaria": 40, "t_categoria": 19, "t_clientes": 999,
    "t_compra": 200, "t_devolucao": 60, "t_entrega": 800, "t_estoque": 400,
    "t_fornecedor": 29, "t_historico_entrega": 1700, "t_inventario": 60,
    "t_item_compra": 400, "t_item_devolucao": 90, "t_item_inventario": 400,
    "t_item_pedido": 1750, "t_movimentaÇÃo_estoque": 1000,
    "t_pagamento": 840, "t_pedidos": 900, "t_produto": 300,
    "t_transportadora": 9,
}

PILOT_COUNTS = {
    "t_armazem": 0, "t_avaria": 2, "t_categoria": 1, "t_clientes": 15,
    "t_compra": 3, "t_devolucao": 2, "t_entrega": 15, "t_estoque": 12,
    "t_fornecedor": 1, "t_historico_entrega": 17, "t_inventario": 2,
    "t_item_compra": 6, "t_item_devolucao": 3, "t_item_inventario": 6,
    "t_item_pedido": 30, "t_movimentaÇÃo_estoque": 14,
    "t_pagamento": 24, "t_pedidos": 20, "t_produto": 12,
    "t_transportadora": 2,
}
assert sum(PILOT_COUNTS.values()) == 187

BASE_IDS = {
    "t_armazem": {1}, "t_categoria": {1}, "t_clientes": {1}, "t_fornecedor": {1},
}
BASE_MAX = {table: max(ids, default=0) for table, ids in BASE_IDS.items()}
for _table in SCHEMA:
    BASE_IDS.setdefault(_table, set())
    BASE_MAX.setdefault(_table, 0)

FK = (
    ("t_avaria", "t_estoque_id_estoque", "t_estoque", "id_estoque"),
    ("t_compra", "t_fornecedor_id_fornecedor", "t_fornecedor", "id_fornecedor"),
    ("t_devolucao", "t_pedidos_id_pedidos", "t_pedidos", "id_pedidos"),
    ("t_entrega", "t_pedidos_id_pedidos", "t_pedidos", "id_pedidos"),
    ("t_entrega", "id_transportadora", "t_transportadora", "id_transpotadora"),
    ("t_estoque", "t_produto_id_produto", "t_produto", "id_produto"),
    ("t_estoque", "t_armazem_id_armazem", "t_armazem", "id_armazem"),
    ("t_historico_entrega", "t_entrega_id_entrega", "t_entrega", "id_entrega"),
    ("t_inventario", "t_armazem_id_armazem", "t_armazem", "id_armazem"),
    ("t_item_compra", "t_compra_id_compra", "t_compra", "id_compra"),
    ("t_item_compra", "t_produto_id_produto", "t_produto", "id_produto"),
    ("t_item_devolucao", "t_devoluÇÃo_id_devoluÇÃo", "t_devolucao", "id_devoluÇÃo"),
    ("t_item_devolucao", "t_item_pedido_id_item_pedido", "t_item_pedido", "id_item_pedido"),
    ("t_item_inventario", "t_inventario_id_inventario", "t_inventario", "id_inventario"),
    ("t_item_inventario", "t_estoque_id_estoque", "t_estoque", "id_estoque"),
    ("t_item_pedido", "t_pedidos_id_pedidos", "t_pedidos", "id_pedidos"),
    ("t_item_pedido", "t_produto_id_produto", "t_produto", "id_produto"),
    ("t_movimentaÇÃo_estoque", "t_estoque_id_estoque", "t_estoque", "id_estoque"),
    ("t_pagamento", "t_pedidos_id_pedidos", "t_pedidos", "id_pedidos"),
    ("t_pedidos", "t_clientes_id_clientes", "t_clientes", "id_clientes"),
    ("t_produto", "t_categoria_id_categoria", "t_categoria", "id_categoria"),
)


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def row(table: str, **values: Any) -> dict[str, Any]:
    expected = [column.name for column in SCHEMA[table]]
    missing = set(expected) - values.keys()
    extra = values.keys() - set(expected)
    if missing or extra:
        raise ValueError(f"{table}: missing={sorted(missing)}, extra={sorted(extra)}")
    return values


def ids_for(table: str, count: int) -> list[int]:
    return list(range(BASE_MAX[table] + 1, BASE_MAX[table] + count + 1))


def _weighted_class_counts(
    product_count: int,
    config: InventoryScenarioConfig,
) -> dict[str, int]:
    raw_counts = {
        name: product_count * weight for name, weight in config.class_weights
    }
    counts = {name: math.floor(value) for name, value in raw_counts.items()}
    remaining = product_count - sum(counts.values())
    by_remainder = sorted(
        config.class_weights,
        key=lambda item: (-(raw_counts[item[0]] - counts[item[0]]), item[0]),
    )
    for name, _ in by_remainder[:remaining]:
        counts[name] += 1
    return counts


def _split_quantity(total: int, part_count: int, rng: random.Random) -> list[int]:
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise ValueError("total quantity must be a non-negative integer")
    if not isinstance(part_count, int) or isinstance(part_count, bool) or part_count < 1:
        raise ValueError("part_count must be a positive integer")
    if total > POSTGRES_INTEGER_MAX:
        raise ValueError(
            f"total quantity {total} exceeds PostgreSQL integer maximum "
            f"{POSTGRES_INTEGER_MAX}"
        )
    if part_count == 1:
        return [total]
    if total == 0:
        return [0] * part_count

    cut_positions = sorted(
        rng.sample(range(total + part_count - 1), part_count - 1)
    )
    boundaries = [-1, *cut_positions, total + part_count - 1]
    return [
        boundaries[index + 1] - boundaries[index] - 1
        for index in range(part_count)
    ]


def _split_reservations(
    total: int,
    physical_parts: list[int],
    rng: random.Random,
) -> list[int]:
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise ValueError("reserved total must be a non-negative integer")
    if any(
        not isinstance(physical, int) or isinstance(physical, bool) or physical < 0
        for physical in physical_parts
    ):
        raise ValueError("physical parts must be non-negative integers")
    physical_total = sum(physical_parts)
    if total > physical_total:
        raise ValueError(
            f"reserved total {total} exceeds physical total {physical_total}"
        )
    if not physical_parts:
        if total:
            raise ValueError("cannot distribute reservations without physical parts")
        return []
    if total == 0:
        return [0] * len(physical_parts)

    reserved_parts = [
        total * physical // physical_total for physical in physical_parts
    ]
    remaining = total - sum(reserved_parts)
    eligible = [
        index for index, physical in enumerate(physical_parts)
        if physical > reserved_parts[index]
    ]
    rng.shuffle(eligible)
    if remaining > len(eligible):
        raise ValueError(
            "reservation allocation cannot satisfy per-location physical limits"
        )
    for index in eligible[:remaining]:
        reserved_parts[index] += 1
    return reserved_parts


def _validate_operational_inventory_plan(
    product_count: int,
    stock_count: int,
    warehouse_count: int,
    movement_count: int | None,
    config: InventoryScenarioConfig,
    minimum_values: Iterable[int] | None = None,
) -> None:
    counts = (product_count, stock_count, warehouse_count)
    if any(
        not isinstance(count, int) or isinstance(count, bool) or count < 0
        for count in counts
    ):
        raise ValueError(
            "product, stock, warehouse, and movement counts must be non-negative"
        )
    if movement_count is not None and (
        not isinstance(movement_count, int)
        or isinstance(movement_count, bool)
        or movement_count < 0
    ):
        raise ValueError(
            "product, stock, warehouse, and movement counts must be non-negative"
        )
    class_counts = _weighted_class_counts(product_count, config)
    stocked_count = product_count - class_counts["without_stock"]
    if stock_count < stocked_count:
        raise ValueError(
            f"stock row count {stock_count} is insufficient for "
            f"{stocked_count} products assigned stock"
        )
    if stock_count and not stocked_count:
        raise ValueError(
            "stock rows are configured but no products are assigned stock"
        )
    if stock_count and not warehouse_count:
        raise ValueError("stock rows require at least one warehouse")

    extra_rows = stock_count - stocked_count
    multi_count = math.floor(stocked_count * config.multi_warehouse_share + 0.5)
    if multi_count and warehouse_count < 2:
        raise ValueError(
            "multi_warehouse_share requires at least two warehouse IDs; "
            "set multi_warehouse_share=0 for a one-warehouse profile"
        )
    if multi_count > extra_rows:
        raise ValueError(
            f"stock row plan has {extra_rows} extra rows, fewer than the "
            f"{multi_count} required for distinct multi-warehouse locations"
        )
    if multi_count and extra_rows > multi_count * (warehouse_count - 1):
        raise ValueError(
            f"stock row plan needs {extra_rows} extra locations but the "
            f"{multi_count} multi-warehouse products can hold at most "
            f"{multi_count * (warehouse_count - 1)} without repeating locations"
        )

    positive_class_count = sum(
        class_counts[name]
        for name in ("healthy", "near_minimum", "at_minimum", "below_minimum")
    )
    high_reservation_count = math.floor(
        stocked_count * config.high_reservation_share + 0.5
    )
    if high_reservation_count > positive_class_count:
        raise ValueError(
            f"high_reservation_share requests {high_reservation_count} "
            f"high-reservation products but only {positive_class_count} "
            "products have positive availability"
        )

    if movement_count is not None and stock_count and movement_count < stock_count:
        raise ValueError(
            f"movement row count {movement_count} is insufficient for "
            f"{stock_count} stock rows; each stock row needs an opening movement"
        )
    if movement_count is not None and stock_count:
        zero_class_count = class_counts["zero_available"]
        zero_physical_count = (zero_class_count + 1) // 2
        extra_movements = movement_count % stock_count
        if zero_physical_count > extra_movements:
            raise ValueError(
                f"movement plan can reconcile only {extra_movements} "
                f"zero-physical stock rows, but the scenario requires "
                f"{zero_physical_count}"
            )

    if product_count:
        minima = (
            list(minimum_values)
            if minimum_values is not None
            else [5 + index % 15 for index in range(product_count)]
        )
        if len(minima) != product_count or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in minima
        ):
            raise ValueError(
                "minimum_values must provide one non-negative integer per product"
            )
        max_minimum = max(minima)
        positive_availability_max = 0
        if class_counts["healthy"]:
            positive_availability_max = max(
                positive_availability_max,
                max_minimum + config.healthy_surplus_range[1],
            )
        if class_counts["near_minimum"]:
            positive_availability_max = max(
                positive_availability_max,
                max_minimum + config.near_minimum_max_gap,
            )
        if class_counts["at_minimum"]:
            positive_availability_max = max(positive_availability_max, max_minimum)
        if class_counts["below_minimum"]:
            if sum(value >= 2 for value in minima) < class_counts["below_minimum"]:
                raise ValueError(
                    "below_minimum class requires enough products with "
                    "estoque_minimo >= 2"
                )
            positive_availability_max = max(
                positive_availability_max, max_minimum - 1
            )
        if high_reservation_count and positive_availability_max:
            max_physical = positive_availability_max * 3
        else:
            max_physical = max(
                positive_availability_max
                + min(5, positive_availability_max),
                8 if class_counts["zero_available"] else 0,
            )
        if max_physical > POSTGRES_INTEGER_MAX:
            raise ValueError(
                f"configured stock quantities may reach {max_physical}, "
                f"above PostgreSQL integer maximum {POSTGRES_INTEGER_MAX}; "
                "reduce the applicable availability range or reservation share"
            )


def _inventory_scenario_metrics(
    products: list[dict[str, Any]],
    stock_rows: list[dict[str, Any]],
) -> dict[str, int]:
    stock_by_product_warehouse: dict[int, dict[int, list[int]]] = defaultdict(dict)
    rows_per_pair: Counter[tuple[int, int]] = Counter()
    products_with_rows: set[int] = set()

    for stock in stock_rows:
        product_id = stock["t_produto_id_produto"]
        warehouse_id = stock["t_armazem_id_armazem"]
        pair = (product_id, warehouse_id)
        rows_per_pair[pair] += 1
        products_with_rows.add(product_id)
        totals = stock_by_product_warehouse[product_id].setdefault(
            warehouse_id, [0, 0]
        )
        totals[0] += stock["quantidade_atual"]
        totals[1] += stock["quantidade_reservada"]

    products_with_multiple_warehouses = 0
    products_with_physical_in_multiple_warehouses = 0
    products_with_available_in_multiple_warehouses = 0
    for product in products:
        locations = stock_by_product_warehouse.get(product["id_produto"], {})
        if len(locations) >= 2:
            products_with_multiple_warehouses += 1
        if sum(physical > 0 for physical, _ in locations.values()) >= 2:
            products_with_physical_in_multiple_warehouses += 1
        if sum(
            physical - reserved > 0
            for physical, reserved in locations.values()
        ) >= 2:
            products_with_available_in_multiple_warehouses += 1

    return {
        "products_with_stock_records": len(products_with_rows),
        "products_with_records_in_multiple_warehouses":
            products_with_multiple_warehouses,
        "products_with_physical_stock_positive_in_multiple_warehouses":
            products_with_physical_in_multiple_warehouses,
        "products_with_available_stock_positive_in_multiple_warehouses":
            products_with_available_in_multiple_warehouses,
        "distinct_product_warehouse_pairs": len(rows_per_pair),
        "duplicate_product_warehouse_rows": sum(
            row_count - 1 for row_count in rows_per_pair.values()
        ),
    }


def _generate_operational_inventory(
    products: list[dict[str, Any]],
    warehouses: list[int],
    stock_ids: list[int],
    config: InventoryScenarioConfig,
    rng: random.Random,
) -> list[dict[str, Any]]:
    _validate_operational_inventory_plan(
        len(products), len(stock_ids), len(warehouses), None, config,
        [product["estoque_minimo"] for product in products],
    )
    class_counts = _weighted_class_counts(len(products), config)
    product_ids = [product["id_produto"] for product in products]
    assigned_classes = [
        class_name
        for class_name, _ in config.class_weights
        for _ in range(class_counts[class_name])
    ]
    rng.shuffle(product_ids)
    rng.shuffle(assigned_classes)
    class_by_product = dict(zip(product_ids, assigned_classes))
    products_by_id = {product["id_produto"]: product for product in products}
    stocked_products = [
        product_id for product_id in product_ids
        if class_by_product[product_id] != "without_stock"
    ]
    if stock_ids and not stocked_products:
        raise ValueError(
            "operational inventory configuration produces no stocked products"
        )
    extra_rows = len(stock_ids) - len(stocked_products)
    if extra_rows < 0:
        raise ValueError(
            "operational inventory plan has fewer stock rows than products with stock"
        )
    multi_warehouse_count = math.floor(
        len(stocked_products) * config.multi_warehouse_share + 0.5
    )
    if multi_warehouse_count and len(warehouses) < 2:
        raise ValueError(
            "multi-warehouse inventory requires at least two warehouse IDs; "
            "use a full profile or set multi_warehouse_share=0"
        )
    if multi_warehouse_count > extra_rows:
        raise ValueError(
            "multi_warehouse_share requires more stock rows than the profile provides"
        )

    locations_by_product = {
        product_id: [rng.choice(warehouses)]
        for product_id in stocked_products
    }
    multi_warehouse_products = rng.sample(stocked_products, multi_warehouse_count)
    for product_id in multi_warehouse_products:
        alternatives = [
            warehouse_id for warehouse_id in warehouses
            if warehouse_id not in locations_by_product[product_id]
        ]
        locations_by_product[product_id].append(rng.choice(alternatives))

    remaining_rows = extra_rows - multi_warehouse_count
    while remaining_rows and multi_warehouse_products and len(warehouses) > 1:
        eligible_products = [
            product_id for product_id in multi_warehouse_products
            if len(locations_by_product[product_id]) < len(warehouses)
        ]
        if not eligible_products:
            break
        product_id = rng.choice(eligible_products)
        alternatives = [
            warehouse_id for warehouse_id in warehouses
            if warehouse_id not in locations_by_product[product_id]
        ]
        locations_by_product[product_id].append(rng.choice(alternatives))
        remaining_rows -= 1

    if remaining_rows:
        if len(warehouses) > 1 and multi_warehouse_count:
            raise ValueError(
                "configured inventory cannot distribute all stock rows across "
                "distinct product-warehouse pairs"
            )
        for _ in range(remaining_rows):
            product_id = rng.choice(stocked_products)
            locations_by_product[product_id].append(
                locations_by_product[product_id][0]
            )

    zero_products = [
        product_id for product_id in stocked_products
        if class_by_product[product_id] == "zero_available"
    ]
    fully_reserved_zero_products = set(
        rng.sample(zero_products, len(zero_products) // 2)
    )
    positive_available_products = [
        product_id for product_id in stocked_products
        if class_by_product[product_id] != "zero_available"
    ]
    high_reservation_count = math.floor(
        len(stocked_products) * config.high_reservation_share + 0.5
    )
    if high_reservation_count > len(positive_available_products):
        raise ValueError(
            "high_reservation_share exceeds products with positive availability"
        )
    high_reservation_products = set(
        rng.sample(positive_available_products, high_reservation_count)
    )
    inactive_count = math.floor(
        len(stocked_products) * config.inactive_with_stock_share + 0.5
    )
    inactive_products = set(rng.sample(stocked_products, inactive_count))
    for product in products:
        product["ativo"] = "N" if product["id_produto"] in inactive_products else "S"

    availability_by_product: dict[int, int] = {}
    reservation_by_product: dict[int, int] = {}
    for product_id in stocked_products:
        category = class_by_product[product_id]
        minimum = products_by_id[product_id]["estoque_minimo"]
        if category == "healthy":
            available = minimum + rng.randint(*config.healthy_surplus_range)
        elif category == "near_minimum":
            available = minimum + rng.randint(1, config.near_minimum_max_gap)
        elif category == "at_minimum":
            available = minimum
        elif category == "below_minimum":
            available = rng.randint(1, minimum - 1)
        elif category == "zero_available":
            available = 0
        else:
            raise AssertionError(f"unexpected stocked inventory class: {category}")

        if category == "zero_available":
            physical = rng.randint(1, 8) if product_id in fully_reserved_zero_products else 0
            reserved = physical
        else:
            reserved = (
                max(1, available * 2)
                if product_id in high_reservation_products
                else rng.randint(0, min(5, available))
            )
            physical = available + reserved
        availability_by_product[product_id] = available
        reservation_by_product[product_id] = reserved

    if len(stock_ids) != sum(map(len, locations_by_product.values())):
        raise ValueError("operational inventory allocation does not match stock row count")

    rows: list[dict[str, Any]] = []
    stock_cursor = 0
    for product_id in product_ids:
        if product_id not in locations_by_product:
            continue
        location_ids = locations_by_product[product_id]
        category = class_by_product[product_id]
        if category == "zero_available" and product_id not in fully_reserved_zero_products:
            physical_total = 0
        else:
            physical_total = (
                availability_by_product[product_id]
                + reservation_by_product[product_id]
            )
        physical_parts = _split_quantity(physical_total, len(location_ids), rng)
        reserved_parts = _split_reservations(
            reservation_by_product[product_id], physical_parts, rng
        )
        for warehouse_id, physical, reserved in zip(
            location_ids, physical_parts, reserved_parts
        ):
            rows.append(row(
                "t_estoque",
                id_estoque=stock_ids[stock_cursor],
                quantidade_atual=physical,
                quantidade_reservada=reserved,
                localizaÇÃo=f"R{stock_cursor % 20:02d}-P{stock_cursor % 50:02d}",
                ultima_atualizaÇÃo=PERIOD_END,
                t_produto_id_produto=product_id,
                t_armazem_id_armazem=warehouse_id,
            ))
            stock_cursor += 1
    return rows


def generate_dataset(
    profile: str = "full",
    seed: int = SEED,
    inventory_scenario: str = "baseline",
    inventory_config: InventoryScenarioConfig | None = None,
) -> dict[str, list[dict[str, Any]]]:
    counts = FULL_COUNTS if profile == "full" else PILOT_COUNTS if profile == "pilot" else None
    if counts is None:
        raise ValueError("profile must be 'full' or 'pilot'")
    if set(counts) != set(SCHEMA):
        raise ValueError("count plan does not cover the exact schema table set")
    if inventory_scenario not in {"baseline", "operational_diversity"}:
        raise ValueError(
            "inventory_scenario must be 'baseline' or 'operational_diversity'"
        )
    if inventory_scenario == "baseline" and inventory_config is not None:
        raise ValueError("inventory_config is only valid for operational_diversity")
    if inventory_scenario == "operational_diversity" and inventory_config is None:
        inventory_config = InventoryScenarioConfig()
    if inventory_scenario == "operational_diversity":
        assert inventory_config is not None
        _validate_operational_inventory_plan(
            counts["t_produto"],
            counts["t_estoque"],
            len(BASE_IDS["t_armazem"]) + counts["t_armazem"],
            counts["t_movimentaÇÃo_estoque"],
            inventory_config,
        )

    rng = random.Random(seed)
    data: dict[str, list[dict[str, Any]]] = {table: [] for table in SCHEMA}
    new_ids = {table: ids_for(table, counts[table]) for table in SCHEMA}
    id_sets = {table: set(BASE_IDS[table]) | set(new_ids[table]) for table in SCHEMA}

    def add(table: str, **values: Any) -> None:
        data[table].append(row(table, **values))

    def date_at(offset: int) -> date:
        return PERIOD_START + timedelta(days=offset % 580)

    # Independent and parent entities. Existing ID=1 records are referenced,
    # never re-emitted to CSV.
    for i, key in enumerate(new_ids["t_armazem"]):
        add("t_armazem", id_armazem=key, nome_armazem=f"Centro Logistico {i+2}",
            endereÇo=f"Av. Operacional {i+2}", cidade=("Sao Paulo", "Curitiba", "Recife", "Goiania")[i % 4],
            estado=("SP", "PR", "PE", "GO")[i % 4], capacidade=5000 + i * 750, ativo="S")
    for i, key in enumerate(new_ids["t_categoria"]):
        add("t_categoria", id_categoria=key, nome_categoria=f"Categoria Sintetica {i+1}",
            descriÇÃo=f"Grupo de catalogo de teste {i+1}", ativo="S")
    for i, key in enumerate(new_ids["t_clientes"]):
        add("t_clientes", id_clientes=key, nome=f"Cliente Sintetico {i+1:04d}",
            cpf_cnpj=f"TESTE-C-{i+1:010d}", email=f"cliente{i+1:04d}@exemplo.invalid",
            endereÇo=f"Rua Teste {i+1}", data_cadastro=date_at(i % 580), status="ATIVO")
    for i, key in enumerate(new_ids["t_fornecedor"]):
        add("t_fornecedor", id_fornecedor=key, razao_social=f"Fornecedor Sintetico {i+1:03d} Ltda",
            nome_fantasia=f"Forn Sintetico {i+1:03d}", cnpj=f"TESTE-F-{i+1:010d}",
            email=f"fornecedor{i+1:03d}@exemplo.invalid", telefone=f"(11) 5000-{i+1:04d}",
            prazo_entrega_dias=3 + i % 12, ativo="S")
    for i, key in enumerate(new_ids["t_transportadora"]):
        modes = ("RODOVIARIO ", "AEREO", "MARITIMO")
        add("t_transportadora", id_transpotadora=key,
            razao_social=f"Transportadora Sintetica {i+1:02d}",
            cnpj=f"TESTE-T-{i+1:010d}", telefone=f"(21) 6000-{i+1:04d}",
            email=f"transp{i+1:02d}@exemplo.invalid", tipo_trasnporte=rng.choice(modes),
            prazo_medio_dias=2 + i % 10, ativo="S")

    categories = sorted(id_sets["t_categoria"])
    suppliers = sorted(id_sets["t_fornecedor"])
    warehouses = sorted(id_sets["t_armazem"])
    customers = sorted(id_sets["t_clientes"])
    carriers = sorted(id_sets["t_transportadora"])
    product_prices: dict[int, Decimal] = {}
    product_costs: dict[int, Decimal] = {}
    for i, key in enumerate(new_ids["t_produto"]):
        cost = money(Decimal(8 + (i % 80)) + Decimal("0.25") * rng.randrange(4))
        price = money(cost * Decimal("1.35"))
        product_costs[key], product_prices[key] = cost, price
        add("t_produto", id_produto=key, sku=f"SKU-SYN-{key:06d}",
            nome=f"Produto Sintetico {key:04d}", descriÇao=f"Item ficticio de catalogo {key}",
            peso_kg=money(Decimal("0.25") + Decimal(i % 25) / 10),
            dimensoes=f"{10+i%20}x{8+i%15}x{4+i%10} cm",
            preÇo_custo=cost, peÇo_venda=price, estoque_minimo=5 + i % 15,
            ativo="S", t_categoria_id_categoria=categories[i % len(categories)])

    products = new_ids["t_produto"]
    purchases = new_ids["t_compra"]
    purchase_line_ids = new_ids["t_item_compra"]
    purchase_lines_by_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    line_cursor = 0
    for i, purchase_id in enumerate(purchases):
        purchase_date = date_at(i * 2)
        total = Decimal("0.00")
        for line_no in range(2):
            product = products[(i * 2 + line_no) % len(products)]
            quantity = 10 + (i + line_no) % 25
            unit = product_costs[product]
            subtotal = money(unit * quantity)
            total += subtotal
            item = row("t_item_compra", id_item_compra=purchase_line_ids[line_cursor],
                       quantidade=quantity, preÇo_unitario=unit, subtotal=subtotal,
                       t_compra_id_compra=purchase_id, t_produto_id_produto=product)
            data["t_item_compra"].append(item)
            purchase_lines_by_id[purchase_id].append(item)
            line_cursor += 1
        add("t_compra", id_compra=purchase_id, data_compra=purchase_date,
            data_previsÃo=purchase_date + timedelta(days=7 + i % 8),
            status_compra="REGISTRADA", valor_total=money(total),
            numero_total=f"OC-SYN-{purchase_id:06d}",
            t_fornecedor_id_fornecedor=suppliers[i % len(suppliers)])

    # Orders use the approved payment-case allocation for both profiles.
    order_ids = new_ids["t_pedidos"]
    order_line_ids = new_ids["t_item_pedido"]
    order_lines: dict[int, list[dict[str, Any]]] = defaultdict(list)
    order_totals: dict[int, Decimal] = {}
    order_dates: dict[int, date] = {}
    order_line_cursor = 0
    for i, order_id in enumerate(order_ids):
        order_dates[order_id] = date_at(i % 560)
        order_lines_count = 1 + (1 if i < counts["t_item_pedido"] - len(order_ids) else 0)
        total = Decimal("0.00")
        for line_no in range(order_lines_count):
            product = products[(i * 7 + line_no * 13) % len(products)]
            quantity = 1 + (i + line_no) % 3
            unit = product_prices[product]
            gross = money(unit * quantity)
            discount = money(min(Decimal("2.00"), gross / Decimal("10")))
            subtotal = money(gross - discount)
            item = row("t_item_pedido", id_item_pedido=order_line_ids[order_line_cursor],
                       quantidade=quantity, preco_unitario=unit, desconto=discount,
                       subtotal=subtotal, t_pedidos_id_pedidos=order_id,
                       t_produto_id_produto=product)
            data["t_item_pedido"].append(item)
            order_lines[order_id].append(item)
            order_line_cursor += 1
            total += subtotal
        order_totals[order_id] = money(total)

    if order_line_cursor != counts["t_item_pedido"]:
        raise ValueError("pilot/full order-item plan is incompatible with order count")

    # Fixed scenario allocation: full has 500 single-paid, 100 split-paid,
    # 60 partial, 40 failed (two attempts), 200 without attempts.
    # Pilot has 10 single-paid, 4 split-paid, 2 partial, 2 failed, 2 no attempt.
    is_full = profile == "full"
    single_paid = 500 if is_full else 10
    split_paid = 100 if is_full else 4
    partial_paid = 60 if is_full else 2
    failed = 40 if is_full else 2
    paid_ids = order_ids[:single_paid + split_paid + partial_paid + failed]
    fully_paid_ids = order_ids[:single_paid + split_paid]
    completed_count = 350 if is_full else 8
    delivered_order_ids = fully_paid_ids[:(600 if is_full else 14)]
    completed_ids = set(fully_paid_ids[:completed_count])
    open_paid_delivery_ids = [x for x in delivered_order_ids if x not in completed_ids]
    no_delivery_paid_ids = [x for x in fully_paid_ids if x not in delivered_order_ids]

    # Payment rows: rejected/pending attempts never count as received.
    payment_ids = new_ids["t_pagamento"]
    payment_cursor = 0
    payment_dates: dict[int, list[date]] = defaultdict(list)
    for index, order_id in enumerate(order_ids):
        total = order_totals[order_id]
        if index < single_paid:
            entries = [("APROVADO", total)]
        elif index < single_paid + split_paid:
            cents = int(total * 100)
            first = max(1, cents // 2)
            entries = [("APROVADO", money(Decimal(first) / 100)),
                       ("APROVADO", money(Decimal(cents - first) / 100))]
        elif index < single_paid + split_paid + partial_paid:
            entries = [("APROVADO", money(total / 2))]
        elif index < single_paid + split_paid + partial_paid + failed:
            entries = [("RECUSADO", total), ("PENDENTE", total)]
        else:
            entries = []
        for attempt, (status, amount) in enumerate(entries):
            pay_date = order_dates[order_id] + timedelta(days=attempt + 1)
            payment_dates[order_id].append(pay_date)
            add("t_pagamento", id_pagamento=payment_ids[payment_cursor],
                data_pagamento=pay_date, valor_pago=money(amount),
                forma_pagamento=("PIX", "CARTAO", "BOLETO")[payment_cursor % 3],
                status_pagamento=status, codigo_transaÇÃo=f"TX-SYN-{payment_ids[payment_cursor]:08d}",
                t_pedidos_id_pedidos=order_id)
            payment_cursor += 1
    if payment_cursor != counts["t_pagamento"]:
        raise ValueError("payment allocation does not match profile count")

    # Transport flow. All full-paid orders in this set get deliveries.
    delivery_ids = new_ids["t_entrega"]
    delivered_groups: dict[int, list[int]] = defaultdict(list)
    delivery_cursor = 0
    if is_full:
        group_sizes = {oid: (1 if i < 250 else 2) for i, oid in enumerate(order_ids[:350])}
        remaining = order_ids[350:600]
        group_sizes.update({oid: (1 if i < 150 else 2) for i, oid in enumerate(remaining)})
    else:
        group_sizes = {oid: (1 if i < 5 else 2) for i, oid in enumerate(order_ids[:8])}
        group_sizes.update({oid: 1 for oid in order_ids[8:12]})

    delivery_data_by_id: dict[int, dict[str, Any]] = {}
    delivered_num = 0
    for order_id, group_size in group_sizes.items():
        for remittance_no in range(group_size):
            latest_approval = max(
                (r["data_pagamento"] for r in data["t_pagamento"]
                 if r["t_pedidos_id_pedidos"] == order_id
                 and r["status_pagamento"] == "APROVADO"),
                default=order_dates[order_id],
            )
            send_date = max(order_dates[order_id] + timedelta(days=1), latest_approval + timedelta(days=1))
            due = send_date + timedelta(days=3 + (delivery_cursor % 7))
            if order_id in completed_ids:
                status = "ENTREGUE"
                actual = due - timedelta(days=1) if delivered_num % 5 == 0 else due + timedelta(days=delivered_num % 4)
                delivered_num += 1
            else:
                status = ("EM_TRANSITO", "ATRASADA", "EXTRAVIADA", "DEVOLVIDA_A_ORIGEM")[
                    delivery_cursor % 4
                ]
                actual = None
            # An open order must retain at least one non-delivered associated shipment.
            if order_id not in completed_ids and remittance_no == group_size - 1 and status == "ENTREGUE":
                status, actual = "EM_TRANSITO", None
            delivery_id = delivery_ids[delivery_cursor]
            delivery_cursor += 1
            delivery = {
                "id_entrega": delivery_id, "codigo_rastreio": f"TRK-SYN-{delivery_id:010d}",
                "data_envio": send_date, "data_prevista": due, "data_entrega": actual,
                "status_entrega": status, "valor_frete": money(Decimal("12.00") + delivery_cursor % 20),
                "t_pedidos_id_pedidos": order_id,
                "id_transportadora": carriers[delivery_cursor % len(carriers)],
            }
            data["t_entrega"].append(row("t_entrega", **delivery))
            delivery_data_by_id[delivery_id] = delivery
            delivered_groups[order_id].append(delivery_id)
    if delivery_cursor != counts["t_entrega"]:
        raise ValueError("delivery allocation does not match profile count")

    # Order current states are derived from payment and remittance scenarios.
    delivered_orders = set(delivered_groups)
    for i, order_id in enumerate(order_ids):
        if order_id in completed_ids:
            status = "CONCLUIDO"
        elif order_id in delivered_orders:
            status = "ENVIO_PARCIAL" if i % 2 == 0 else "EM_PROCESSAMENTO"
        elif i < single_paid + split_paid:
            status = "EM_PROCESSAMENTO"
        elif i < single_paid + split_paid + partial_paid:
            status = "AGUARDANDO_PAGAMENTO"
        elif i < single_paid + split_paid + partial_paid + failed:
            status = "AGUARDANDO_PAGAMENTO"
        elif i % 10 == 0:
            status = "CANCELADO"
        else:
            status = "PENDENTE"
        add("t_pedidos", id_pedidos=order_id,
            t_clientes_id_clientes=customers[(i + 1) % len(customers)],
            data_pedido=order_dates[order_id], status_pedidos=status,
            valor_total=order_totals[order_id])

    # Inventory structure is partitioned by warehouse so item rows cannot cross warehouses.
    stock_ids = new_ids["t_estoque"]
    stock_rows: dict[int, dict[str, Any]] = {}
    stock_by_warehouse: dict[int, list[int]] = defaultdict(list)
    if inventory_scenario == "baseline":
        inventory_rows = []
        for i, stock_id in enumerate(stock_ids):
            warehouse_id = warehouses[i % len(warehouses)]
            product_id = products[i % len(products)]
            quantity = 40 + i % 61
            reserved = i % min(8, quantity)
            stock = row("t_estoque", id_estoque=stock_id, quantidade_atual=quantity,
                        quantidade_reservada=reserved, localizaÇÃo=f"R{i%20:02d}-P{i%50:02d}",
                        ultima_atualizaÇÃo=PERIOD_END, t_produto_id_produto=product_id,
                        t_armazem_id_armazem=warehouse_id)
            inventory_rows.append(stock)
    else:
        assert inventory_config is not None
        inventory_rows = _generate_operational_inventory(
            data["t_produto"], warehouses, stock_ids, inventory_config, rng
        )
        zero_physical_rows = sum(
            stock["quantidade_atual"] == 0 for stock in inventory_rows
        )
        _, additional_stock_movements = divmod(
            counts["t_movimentaÇÃo_estoque"], len(stock_ids)
        )
        if zero_physical_rows > additional_stock_movements:
            raise ValueError(
                "movement plan cannot reconcile all zero-physical stock rows "
                "with positive movement quantities"
            )
        inventory_rows.sort(
            key=lambda stock: stock["quantidade_atual"] != 0
        )
        for stock_id, stock in zip(stock_ids, inventory_rows):
            stock["id_estoque"] = stock_id
    for stock in inventory_rows:
        data["t_estoque"].append(stock)
        stock_rows[stock["id_estoque"]] = stock
        stock_by_warehouse[stock["t_armazem_id_armazem"]].append(
            stock["id_estoque"]
        )

    inventory_ids = new_ids["t_inventario"]
    inventories_by_warehouse: dict[int, list[int]] = defaultdict(list)
    for i, inv_id in enumerate(inventory_ids):
        warehouse_id = warehouses[i % len(warehouses)]
        inventories_by_warehouse[warehouse_id].append(inv_id)
        opened = date(2026, 9, 1) + timedelta(days=i % 20)
        add("t_inventario", id_inventario=inv_id, data_abertura=opened,
            data_fechamento=opened + timedelta(days=1), status_inventario="FECHADO",
            observaÇÃo="Contagem sintetica de fechamento", t_armazem_id_armazem=warehouse_id)

    # Assign exactly the requested inventory-item rows within matching warehouses.
    inv_item_ids = new_ids["t_item_inventario"]
    candidate_pairs: list[tuple[int, int]] = []
    for warehouse_id, invs in inventories_by_warehouse.items():
        stocks = stock_by_warehouse.get(warehouse_id, [])
        if not invs or not stocks:
            continue
        for j, stock_id in enumerate(stocks):
            candidate_pairs.append((invs[j % len(invs)], stock_id))
    for i, inv_item_id in enumerate(inv_item_ids):
        inv_id, stock_id = candidate_pairs[i % len(candidate_pairs)]
        system = stock_rows[stock_id]["quantidade_atual"]
        delta = (-1, 0, 1)[i % 3]
        if system + delta < 0:
            delta = 0
        counted = system + delta
        add("t_item_inventario", id_item_inventario=inv_item_id,
            quantidade_sistema=system, quantidade_contada=counted, diferenÇa=delta,
            observaÇÃo="Contagem sintetica", t_inventario_id_inventario=inv_id,
            t_estoque_id_estoque=stock_id)

    # Avarias are represented by one-unit outbound events later, preventing double counting.
    damage_ids = new_ids["t_avaria"]
    damage_stock_ids = [stock_ids[i % len(stock_ids)] for i in range(len(damage_ids))]
    movements_per_stock, additional_stock_movements = divmod(
        counts["t_movimentaÇÃo_estoque"], len(stock_ids))
    for i, damage_id in enumerate(damage_ids):
        stock_movement_index = (
            i * (movements_per_stock + 1) if i < additional_stock_movements
            else additional_stock_movements * (movements_per_stock + 1)
            + (i - additional_stock_movements) * movements_per_stock
        )
        add("t_avaria", id_avaria=damage_id,
            data_avaria=date_at(51 + stock_movement_index),
            quantidade=1, tipo_avaria=("MANUSEIO", "ARMAZENAGEM")[i % 2],
            descriÇÃo="Avaria sintetica; saida correspondente identificada no movimento",
            custo_estimado=product_costs[stock_rows[damage_stock_ids[i]]["t_produto_id_produto"]],
            status_avaria="REGISTRADA", t_estoque_id_estoque=damage_stock_ids[i])

    # Exactly the configured movement count; for each stock, one inbound balance
    # and zero or more outbound events net to quantity_atual.
    movement_ids = new_ids["t_movimentaÇÃo_estoque"]
    movement_count_by_stock = Counter()
    for i in range(len(movement_ids)):
        movement_count_by_stock[stock_ids[i % len(stock_ids)]] += 1
    damage_by_stock: dict[int, list[int]] = defaultdict(list)
    for damage_id, stock_id in zip(damage_ids, damage_stock_ids):
        damage_by_stock[stock_id].append(damage_id)
    movement_cursor = 0
    for stock_id in stock_ids:
        count = movement_count_by_stock[stock_id]
        if count < 1:
            raise ValueError("each stock row requires a movement for reconciliation")
        outbound_count = count - 1
        outbound_quantities = [1] * outbound_count
        damaged = damage_by_stock.get(stock_id, [])
        if len(damaged) > outbound_count:
            raise ValueError("movement plan cannot represent all stock damage events")
        total_out = sum(outbound_quantities)
        opening = stock_rows[stock_id]["quantidade_atual"] + total_out
        add_movement = data["t_movimentaÇÃo_estoque"].append
        add_movement(row("t_movimentaÇÃo_estoque",
            id_movimentaÇÃo=movement_ids[movement_cursor], tipo_movimentação="ENTRADA",
            quantidade=opening, data_movimentação=PERIOD_START,
            motivo="Saldo inicial sintetico do horizonte", documento_referencia=f"ABERTURA:{stock_id}",
            t_estoque_id_estoque=stock_id))
        movement_cursor += 1
        for out_no, quantity in enumerate(outbound_quantities):
            if out_no < len(damaged):
                damage_id = damaged[out_no]
                kind, reason, reference = "SAIDA", "Baixa por avaria", f"AVARIA:{damage_id}"
            else:
                kind, reason, reference = "SAIDA", "Consumo operacional sintetico", f"OPERACAO:{stock_id}:{out_no}"
            data["t_movimentaÇÃo_estoque"].append(row("t_movimentaÇÃo_estoque",
                id_movimentaÇÃo=movement_ids[movement_cursor], tipo_movimentação=kind,
                quantidade=quantity, data_movimentação=date_at(50 + movement_cursor),
                motivo=reason, documento_referencia=reference, t_estoque_id_estoque=stock_id))
            movement_cursor += 1
    if movement_cursor != counts["t_movimentaÇÃo_estoque"]:
        raise ValueError("movement allocation does not match profile count")

    # Delivery event rows: two per shipment where possible; full plan has +100
    # third events, pilot keeps one or two events and avoids invented timestamps.
    history_ids = new_ids["t_historico_entrega"]
    histories_per_delivery = [1] * len(delivery_ids)
    remaining = len(history_ids) - len(delivery_ids)
    if remaining < 0:
        # The pilot profile contains more deliveries than history rows; coverage
        # is partial by design, but every delivery must have at least one event
        # for the pilot workflow, so this is rejected rather than silently weakened.
        raise ValueError("history rows must cover each delivery at least once")
    for i in range(remaining):
        histories_per_delivery[i % len(histories_per_delivery)] += 1
    event_cursor = 0
    for delivery_id, event_count in zip(delivery_ids, histories_per_delivery):
        delivery = delivery_data_by_id[delivery_id]
        normal = ["COLETADA", "EM_TRANSITO", "SAIU_PARA_ENTREGA"]
        terminal = {
            "ENTREGUE": "ENTREGUE", "EXTRAVIADA": "EXTRAVIO_CONFIRMADO",
            "DEVOLVIDA_A_ORIGEM": "RETORNO_A_ORIGEM", "ATRASADA": "ATRASO_IDENTIFICADO",
            "EM_TRANSITO": "EM_TRANSITO",
        }[delivery["status_entrega"]]
        sequence = normal[:max(0, event_count - 1)] + [terminal]
        if event_count == 1:
            sequence = [terminal]
        event_date = delivery["data_envio"]
        for j, event in enumerate(sequence):
            add("t_historico_entrega", id_historico=history_ids[event_cursor],
                data_evento=event_date + timedelta(days=j),
                status_evento=event, local_evento=("Centro de distribuicao", "Em rota")[j % 2],
                observaÇÃo="Evento sintetico; granularidade diaria",
                t_entrega_id_entrega=delivery_id)
            event_cursor += 1
    if event_cursor != len(history_ids):
        raise ValueError("history allocation does not match requested count")

    # Returns: only completed orders, item lines belonging to that same order,
    # and quantities capped to the purchased quantity.
    eligible_items = [item for order_id in sorted(completed_ids) for item in order_lines[order_id]]
    if len(eligible_items) < counts["t_item_devolucao"]:
        raise ValueError("not enough distinct eligible delivered order lines for returns")
    return_ids = new_ids["t_devolucao"]
    return_item_ids = new_ids["t_item_devolucao"]
    groups: list[list[dict[str, Any]]] = []
    cursor = 0
    for i in range(len(return_ids)):
        group_size = 2 if i < (len(return_ids) // 2) else 1
        groups.append(eligible_items[cursor:cursor + group_size])
        cursor += group_size
    if cursor != len(return_item_ids):
        raise ValueError("return item profile must group exactly into return headers")
    # For each completed order, find its latest delivered date for safe return chronology.
    order_delivery_dates: dict[int, date] = {}
    for order_id in completed_ids:
        dates = [delivery_data_by_id[d]["data_entrega"] for d in delivered_groups[order_id]]
        if any(d is None for d in dates):
            raise ValueError("completed orders must have all deliveries dated delivered")
        order_delivery_dates[order_id] = max(dates)
    return_item_cursor = 0
    for i, (return_id, items) in enumerate(zip(return_ids, groups)):
        if not items:
            raise ValueError("return header without return items")
        order_id = items[0]["t_pedidos_id_pedidos"]
        if any(item["t_pedidos_id_pedidos"] != order_id for item in items):
            raise ValueError("return group contains order lines from different orders")
        request_date = order_delivery_dates[order_id] + timedelta(days=1 + i % 20)
        refund = Decimal("0.00")
        for item in items:
            quantity = 1
            unit_net = (item["subtotal"] / item["quantidade"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)
            item_refund = min(unit_net * quantity, item["subtotal"])
            refund += item_refund
            add("t_item_devolucao", id_item_devoluÇÃo=return_item_ids[return_item_cursor],
                quantidade=quantity, condiÇÃo_produto=("LACRADO", "DANIFICADO")[i % 2],
                motivo_item="Devolucao sintetica", t_devoluÇÃo_id_devoluÇÃo=return_id,
                t_item_pedido_id_item_pedido=item["id_item_pedido"])
            return_item_cursor += 1
        add("t_devolucao", id_devoluÇÃo=return_id,
            data_solicitaÇÃo=request_date, motivo="Solicitacao sintetica",
            status_devoluÇÃo="CONCLUIDA", data_conclusÃo=request_date + timedelta(days=3),
            valor_reembolso=money(refund), t_pedidos_id_pedidos=order_id)

    # Assert the emitted table counts before returning.
    for table, expected in counts.items():
        if len(data[table]) != expected:
            raise ValueError(f"{table}: generated {len(data[table])}, expected {expected}")
    return data


def _inventory_class_for_product(
    product: dict[str, Any],
    stock_rows: list[dict[str, Any]],
    near_minimum_max_gap: int,
) -> str:
    if not stock_rows:
        return "without_stock"
    available = sum(
        stock["quantidade_atual"] - stock["quantidade_reservada"]
        for stock in stock_rows
    )
    if available == 0:
        return "zero_available"
    gap = available - product["estoque_minimo"]
    if gap < 0:
        return "below_minimum"
    if gap == 0:
        return "at_minimum"
    if gap <= near_minimum_max_gap:
        return "near_minimum"
    return "healthy"


def _validate_inventory_scenario(
    data: dict[str, list[dict[str, Any]]],
    config: InventoryScenarioConfig,
) -> list[str]:
    errors: list[str] = []
    products = data["t_produto"]
    stock_by_product: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for stock in data["t_estoque"]:
        product_id = stock["t_produto_id_produto"]
        stock_by_product[product_id].append(stock)

    diagnostics = _inventory_scenario_metrics(products, data["t_estoque"])

    classes = Counter(
        _inventory_class_for_product(
            product,
            stock_by_product.get(product["id_produto"], []),
            config.near_minimum_max_gap,
        )
        for product in products
    )
    expected_classes = _weighted_class_counts(len(products), config)
    if classes != Counter(expected_classes):
        errors.append(
            f"inventory scenario class coverage mismatch: "
            f"expected {expected_classes}, got {dict(classes)}"
        )

    stocked_count = len(products) - expected_classes["without_stock"]
    expected_multi_warehouse = math.floor(
        stocked_count * config.multi_warehouse_share + 0.5
    )
    actual_multi_warehouse = diagnostics[
        "products_with_records_in_multiple_warehouses"
    ]
    if actual_multi_warehouse != expected_multi_warehouse:
        errors.append(
            f"inventory scenario multi-warehouse coverage mismatch: "
            f"expected {expected_multi_warehouse}, got {actual_multi_warehouse}"
        )

    actual_inactive_with_stock = sum(
        product["ativo"] == "N" and bool(stock_by_product.get(product["id_produto"]))
        for product in products
    )
    expected_inactive_with_stock = math.floor(
        stocked_count * config.inactive_with_stock_share + 0.5
    )
    if actual_inactive_with_stock != expected_inactive_with_stock:
        errors.append(
            f"inventory scenario inactive-with-stock coverage mismatch: "
            f"expected {expected_inactive_with_stock}, got {actual_inactive_with_stock}"
        )

    high_reservation_count = math.floor(
        stocked_count * config.high_reservation_share + 0.5
    )
    actual_high_reservation = 0
    for product in products:
        rows = stock_by_product.get(product["id_produto"], [])
        available = sum(
            stock["quantidade_atual"] - stock["quantidade_reservada"]
            for stock in rows
        )
        reserved = sum(stock["quantidade_reservada"] for stock in rows)
        if available > 0 and reserved >= 2 * available:
            actual_high_reservation += 1
    if actual_high_reservation != high_reservation_count:
        errors.append(
            f"inventory scenario high-reservation coverage mismatch: "
            f"expected {high_reservation_count}, got {actual_high_reservation}"
        )

    zero_products = [
        product["id_produto"] for product in products
        if _inventory_class_for_product(
            product,
            stock_by_product.get(product["id_produto"], []),
            config.near_minimum_max_gap,
        ) == "zero_available"
    ]
    zero_rows = [
        stock for product_id in zero_products
        for stock in stock_by_product[product_id]
    ]
    if len(zero_products) >= 2:
        has_physical_zero = any(
            stock["quantidade_atual"] == 0 and stock["quantidade_reservada"] == 0
            for stock in zero_rows
        )
        has_fully_reserved = any(
            stock["quantidade_atual"] > 0
            and stock["quantidade_reservada"] == stock["quantidade_atual"]
            for stock in zero_rows
        )
        if not has_physical_zero or not has_fully_reserved:
            errors.append(
                "inventory scenario must represent both physical-zero and "
                "fully-reserved zero availability"
            )
    return errors


def validate_dataset(
    data: dict[str, list[dict[str, Any]]],
    counts: dict[str, int],
    inventory_config: InventoryScenarioConfig | None = None,
) -> list[str]:
    errors: list[str] = []
    if set(data) != set(SCHEMA):
        return ["dataset table names differ from schema"]
    if set(counts) != set(SCHEMA):
        return ["count plan table names differ from schema"]

    valid_ids: dict[str, set[int]] = {
        table: set(BASE_IDS[table]) for table in SCHEMA
    }
    for table, expected in counts.items():
        rows = data[table]
        if len(rows) != expected:
            errors.append(f"{table}: expected {expected} rows, got {len(rows)}")
        columns = SCHEMA[table]
        pk = columns[0].name
        if any(list(item) != [col.name for col in columns] for item in rows):
            errors.append(f"{table}: row field order/schema mismatch")
        seen: set[Any] = set()
        for index, record in enumerate(rows):
            for col in columns:
                value = record.get(col.name)
                loc = f"{table}[{index}].{col.name}"
                if value is None:
                    if not col.nullable:
                        errors.append(f"{loc}: NULL in NOT NULL column")
                    continue
                if col.kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                    errors.append(f"{loc}: expected integer")
                elif col.kind == "integer" and not -(2**31) <= value < 2**31:
                    errors.append(f"{loc}: outside PostgreSQL integer range")
                elif col.kind == "text":
                    if not isinstance(value, str):
                        errors.append(f"{loc}: expected text")
                    elif col.limit is not None and len(value) > col.limit:
                        errors.append(f"{loc}: exceeds length {col.limit}")
                elif col.kind == "char":
                    if not isinstance(value, str):
                        errors.append(f"{loc}: expected char text")
                    elif len(value) > (col.limit or 1):
                        errors.append(f"{loc}: exceeds char length {col.limit}")
                elif col.kind == "date" and not isinstance(value, date):
                    errors.append(f"{loc}: expected date")
                elif col.kind == "date" and not PERIOD_START <= value <= PERIOD_END:
                    errors.append(f"{loc}: outside generated date period")
                elif col.kind == "decimal":
                    if not isinstance(value, Decimal):
                        errors.append(f"{loc}: expected Decimal")
                    else:
                        assert col.precision is not None and col.scale is not None
                        quantized = value.quantize(Decimal(1).scaleb(-col.scale))
                        integer_capacity = col.precision - col.scale
                        if value != quantized or len(str(abs(int(value))) if value else "0") > integer_capacity:
                            errors.append(f"{loc}: exceeds NUMERIC({col.precision},{col.scale})")
            pk_value = record.get(pk)
            if not isinstance(pk_value, int) or isinstance(pk_value, bool):
                errors.append(f"{table}[{index}].{pk}: invalid primary key")
            else:
                if pk_value in seen or pk_value in BASE_IDS[table]:
                    errors.append(f"{table}: primary-key collision {pk_value}")
                seen.add(pk_value)
        valid_ids[table].update(seen)

    for child, child_col, parent, parent_col in FK:
        for index, record in enumerate(data[child]):
            if record.get(child_col) not in valid_ids[parent]:
                errors.append(f"{child}[{index}].{child_col}: orphan reference")

    total_rows = sum(map(len, data.values()))
    if total_rows != sum(counts.values()) or total_rows not in (187, 10_000):
        errors.append("overall row total is not the configured full/pilot total")

    by_id = {
        table: {r[SCHEMA[table][0].name]: r for r in rows
                if isinstance(r.get(SCHEMA[table][0].name), int)}
        for table, rows in data.items()
    }
    lines_by_order: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for line in data["t_item_pedido"]:
        order_id = line["t_pedidos_id_pedidos"]
        lines_by_order[order_id].append(line)
        quantity = line["quantidade"]
        gross = money(quantity * line["preco_unitario"])
        if quantity <= 0 or line["preco_unitario"] <= 0 or line["desconto"] < 0 or line["desconto"] > gross:
            errors.append(f"order line {line['id_item_pedido']}: invalid quantity/price/discount")
        if line["subtotal"] != money(gross - line["desconto"]):
            errors.append(f"order line {line['id_item_pedido']}: subtotal mismatch")

    purchase_lines: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for line in data["t_item_compra"]:
        purchase_lines[line["t_compra_id_compra"]].append(line)
        if line["quantidade"] <= 0 or line["preÇo_unitario"] <= 0:
            errors.append(f"purchase line {line['id_item_compra']}: invalid quantity/price")
        if line["subtotal"] != money(line["quantidade"] * line["preÇo_unitario"]):
            errors.append(f"purchase line {line['id_item_compra']}: subtotal mismatch")
    for purchase in data["t_compra"]:
        lines = purchase_lines.get(purchase["id_compra"], [])
        if not lines or money(sum((line["subtotal"] for line in lines), Decimal("0.00"))) != purchase["valor_total"]:
            errors.append(f"purchase {purchase['id_compra']}: missing lines or total mismatch")
        if purchase["data_previsÃo"] < purchase["data_compra"]:
            errors.append(f"purchase {purchase['id_compra']}: expected date precedes purchase")

    for product in data["t_produto"]:
        if product["preÇo_custo"] <= 0 or product["peÇo_venda"] <= product["preÇo_custo"]:
            errors.append(f"product {product['id_produto']}: invalid cost/sale price")

    payments_by_order: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for payment in data["t_pagamento"]:
        if payment["valor_pago"] <= 0:
            errors.append(f"payment {payment['id_pagamento']}: amount must be positive")
        if payment["status_pagamento"] not in {"APROVADO", "RECUSADO", "PENDENTE"}:
            errors.append(f"payment {payment['id_pagamento']}: unknown status")
        if payment["status_pagamento"] == "APROVADO":
            payments_by_order[payment["t_pedidos_id_pedidos"]] += payment["valor_pago"]

    order_by_id = by_id["t_pedidos"]
    for payment in data["t_pagamento"]:
        order = order_by_id.get(payment["t_pedidos_id_pedidos"])
        if order and payment["data_pagamento"] < order["data_pedido"]:
            errors.append(f"payment {payment['id_pagamento']}: precedes order date")

    deliveries_by_order: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for delivery in data["t_entrega"]:
        deliveries_by_order[delivery["t_pedidos_id_pedidos"]].append(delivery)
        if delivery["data_envio"] is not None and delivery["data_prevista"] is not None and delivery["data_envio"] > delivery["data_prevista"]:
            errors.append(f"delivery {delivery['id_entrega']}: due date precedes shipping")
        if delivery["data_entrega"] is not None and delivery["data_entrega"] < delivery["data_envio"]:
            errors.append(f"delivery {delivery['id_entrega']}: actual date precedes shipping")
        if delivery["status_entrega"] == "ENTREGUE" and delivery["data_entrega"] is None:
            errors.append(f"delivery {delivery['id_entrega']}: delivered without date")
        if delivery["status_entrega"] != "ENTREGUE" and delivery["data_entrega"] is not None:
            errors.append(f"delivery {delivery['id_entrega']}: open state has actual date")
        order = order_by_id.get(delivery["t_pedidos_id_pedidos"])
        approved_dates = [
            payment["data_pagamento"] for payment in data["t_pagamento"]
            if payment["t_pedidos_id_pedidos"] == delivery["t_pedidos_id_pedidos"]
            and payment["status_pagamento"] == "APROVADO"
        ]
        if order and delivery["data_envio"] < order["data_pedido"]:
            errors.append(f"delivery {delivery['id_entrega']}: precedes order date")
        if approved_dates and delivery["data_envio"] <= max(approved_dates):
            errors.append(f"RN-012: delivery {delivery['id_entrega']} shipped before payment date")

    for order in data["t_pedidos"]:
        oid = order["id_pedidos"]
        lines = lines_by_order.get(oid, [])
        if not lines or money(sum((x["subtotal"] for x in lines), Decimal("0.00"))) != order["valor_total"]:
            errors.append(f"order {oid}: missing lines or total mismatch")
        approved = money(payments_by_order[oid])
        if approved > order["valor_total"]:
            errors.append(f"order {oid}: approved payments exceed order total")
        if deliveries_by_order.get(oid) and approved < order["valor_total"]:
            errors.append(f"RN-012: order {oid} shipped before full payment")
        if order["status_pedidos"] == "CONCLUIDO":
            shipments = deliveries_by_order.get(oid, [])
            if not lines or approved < order["valor_total"] or not shipments:
                errors.append(f"RN-014: order {oid} lacks item/payment/delivery")
            elif any(d["status_entrega"] != "ENTREGUE" for d in shipments):
                errors.append(f"RN-014: order {oid} has unfinished shipment")

    return_headers = by_id["t_devolucao"]
    order_lines_by_id = by_id["t_item_pedido"]
    returned_quantity: Counter[int] = Counter()
    returned_value_by_header: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    items_by_return: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for return_item in data["t_item_devolucao"]:
        return_id = return_item["t_devoluÇÃo_id_devoluÇÃo"]
        order_line_id = return_item["t_item_pedido_id_item_pedido"]
        return_header = return_headers.get(return_id)
        order_line = order_lines_by_id.get(order_line_id)
        items_by_return[return_id].append(return_item)
        if return_header is None or order_line is None:
            continue
        if order_line["t_pedidos_id_pedidos"] != return_header["t_pedidos_id_pedidos"]:
            errors.append(f"RN-028: return item {return_item['id_item_devoluÇÃo']} belongs to another order")
        returned_quantity[order_line_id] += return_item["quantidade"]
        item_value = (order_line["subtotal"] / order_line["quantidade"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        returned_value_by_header[return_id] += min(
            item_value * return_item["quantidade"], order_line["subtotal"])
        if return_item["quantidade"] <= 0:
            errors.append(f"return item {return_item['id_item_devoluÇÃo']}: quantity must be positive")
    for order_line_id, quantity in returned_quantity.items():
        order_line = order_lines_by_id[order_line_id]
        if quantity > order_line["quantidade"]:
            errors.append(f"RN-029: item {order_line_id} returned quantity exceeds purchased quantity")
    for return_header in data["t_devolucao"]:
        return_id = return_header["id_devoluÇÃo"]
        return_date = return_header["data_solicitaÇÃo"]
        if not items_by_return.get(return_id):
            errors.append(f"return {return_id}: no return items")
        if return_header["data_conclusÃo"] is not None and return_date is not None:
            if return_header["data_conclusÃo"] < return_date:
                errors.append(f"return {return_id}: completion precedes request")
        if return_header["valor_reembolso"] < 0 or return_header["valor_reembolso"] > returned_value_by_header[return_id]:
            errors.append(f"return {return_id}: refund exceeds returned-item net value")
        associated_deliveries = deliveries_by_order.get(return_header["t_pedidos_id_pedidos"], [])
        delivered_dates = [item["data_entrega"] for item in associated_deliveries
                           if item["status_entrega"] == "ENTREGUE" and item["data_entrega"] is not None]
        if (return_date is not None and delivered_dates
                and return_date <= max(delivered_dates)):
            errors.append(f"return {return_id}: request precedes final delivery")

    inventory_by_id = by_id["t_inventario"]
    stock_by_id = by_id["t_estoque"]
    for inventory in data["t_inventario"]:
        if (inventory["data_abertura"] is not None and inventory["data_fechamento"] is not None
                and inventory["data_fechamento"] < inventory["data_abertura"]):
            errors.append(f"inventory {inventory['id_inventario']}: closes before opening")
    for item in data["t_item_inventario"]:
        inventory = inventory_by_id.get(item["t_inventario_id_inventario"])
        stock = stock_by_id.get(item["t_estoque_id_estoque"])
        if item["quantidade_sistema"] < 0 or item["quantidade_contada"] < 0:
            errors.append(f"inventory item {item['id_item_inventario']}: negative quantity")
        if item["quantidade_contada"] - item["quantidade_sistema"] != item["diferenÇa"]:
            errors.append(f"inventory item {item['id_item_inventario']}: difference mismatch")
        if inventory and stock and inventory["t_armazem_id_armazem"] != stock["t_armazem_id_armazem"]:
            errors.append(f"inventory item {item['id_item_inventario']}: warehouse mismatch")
        if stock and item["quantidade_sistema"] != stock["quantidade_atual"]:
            errors.append(f"inventory item {item['id_item_inventario']}: system quantity mismatch")

    movements_by_stock: dict[int, list[dict[str, Any]]] = defaultdict(list)
    movement_by_damage_ref: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for movement in data["t_movimentaÇÃo_estoque"]:
        movements_by_stock[movement["t_estoque_id_estoque"]].append(movement)
        if movement["quantidade"] <= 0:
            errors.append(f"movement {movement['id_movimentaÇÃo']}: quantity must be positive")
        if movement["tipo_movimentação"] not in {"ENTRADA", "SAIDA"}:
            errors.append(f"movement {movement['id_movimentaÇÃo']}: unknown movement type")
        if movement["documento_referencia"].startswith("AVARIA:"):
            movement_by_damage_ref[movement["documento_referencia"]].append(movement)
    for stock in data["t_estoque"]:
        stock_id = stock["id_estoque"]
        if stock["quantidade_atual"] < 0 or not 0 <= stock["quantidade_reservada"] <= stock["quantidade_atual"]:
            errors.append(f"stock {stock_id}: invalid on-hand/reserved quantity")
        balance = sum(
            movement["quantidade"] if movement["tipo_movimentação"] == "ENTRADA"
            else -movement["quantidade"]
            for movement in movements_by_stock.get(stock_id, [])
        )
        if balance != stock["quantidade_atual"]:
            errors.append(f"stock {stock_id}: movement balance does not match current quantity")
    for inventory_item in data["t_item_inventario"]:
        inventory = inventory_by_id.get(inventory_item["t_inventario_id_inventario"])
        stock_movements = movements_by_stock.get(inventory_item["t_estoque_id_estoque"], [])
        if inventory and any(movement["data_movimentação"] > inventory["data_abertura"]
                             for movement in stock_movements):
            errors.append(
                f"inventory item {inventory_item['id_item_inventario']}: stock movement occurs after inventory"
            )
    for damage in data["t_avaria"]:
        reference = f"AVARIA:{damage['id_avaria']}"
        matches = movement_by_damage_ref.get(reference, [])
        if len(matches) != 1:
            errors.append(f"damage {damage['id_avaria']}: expected exactly one paired stock movement")
        elif (matches[0]["tipo_movimentação"] != "SAIDA"
              or matches[0]["quantidade"] != damage["quantidade"]
              or matches[0]["t_estoque_id_estoque"] != damage["t_estoque_id_estoque"]):
            errors.append(f"damage {damage['id_avaria']}: paired movement mismatch")
        elif matches[0]["data_movimentação"] != damage["data_avaria"]:
            errors.append(f"damage {damage['id_avaria']}: paired movement date mismatch")

    history_by_delivery: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in data["t_historico_entrega"]:
        history_by_delivery[event["t_entrega_id_entrega"]].append(event)
    for delivery in data["t_entrega"]:
        events = sorted(history_by_delivery.get(delivery["id_entrega"], []),
                        key=lambda event: event["data_evento"])
        if not events:
            errors.append(f"delivery {delivery['id_entrega']}: missing history events")
            continue
        if any(event["data_evento"] < delivery["data_envio"] for event in events):
            errors.append(f"delivery {delivery['id_entrega']}: history precedes shipment")
        expected_terminal = {
            "ENTREGUE": "ENTREGUE",
            "EXTRAVIADA": "EXTRAVIO_CONFIRMADO",
            "DEVOLVIDA_A_ORIGEM": "RETORNO_A_ORIGEM",
            "ATRASADA": "ATRASO_IDENTIFICADO",
            "EM_TRANSITO": "EM_TRANSITO",
        }.get(delivery["status_entrega"])
        if expected_terminal and events[-1]["status_evento"] != expected_terminal:
            errors.append(f"delivery {delivery['id_entrega']}: terminal history state mismatch")
        if (delivery["data_entrega"] is not None
                and events[-1]["data_evento"] > delivery["data_entrega"]):
            errors.append(f"delivery {delivery['id_entrega']}: history follows delivery date")

    for carrier in data["t_transportadora"]:
        if carrier["tipo_trasnporte"] not in {"RODOVIARIO ", "AEREO", "MARITIMO"}:
            errors.append(f"carrier {carrier['id_transpotadora']}: violates transport-type CHECK")

    if inventory_config is not None:
        errors.extend(_validate_inventory_scenario(data, inventory_config))

    return errors


def write_artifacts(
    data: dict[str, list[dict[str, Any]]],
    output: Path,
    profile: str,
    seed: int,
    inventory_scenario: str = "baseline",
    inventory_config: InventoryScenarioConfig | None = None,
) -> None:
    if profile not in {"pilot", "full"}:
        raise ValueError("profile must be 'pilot' or 'full'")
    if inventory_scenario not in {"baseline", "operational_diversity"}:
        raise ValueError(
            "inventory_scenario must be 'baseline' or 'operational_diversity'"
        )
    if inventory_scenario == "baseline" and inventory_config is not None:
        raise ValueError("inventory_config is only valid for operational_diversity")
    if inventory_scenario == "operational_diversity" and inventory_config is None:
        inventory_config = InventoryScenarioConfig()
    counts = FULL_COUNTS if profile == "full" else PILOT_COUNTS
    errors = validate_dataset(
        data,
        counts,
        inventory_config if inventory_scenario == "operational_diversity" else None,
    )
    if errors:
        raise ValueError("refusing to export invalid dataset: " + "; ".join(errors))
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing output path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{output.name}.", suffix=".incomplete", dir=output.parent
    ))
    try:
        hashes: dict[str, str] = {}
        for table, rows in data.items():
            path = staging / f"{table}.csv"
            fields = [column.name for column in SCHEMA[table]]
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=fields, lineterminator="\n"
                )
                writer.writeheader()
                for record in rows:
                    writer.writerow({
                        key: value.isoformat() if isinstance(value, date)
                        else format(value, "f") if isinstance(value, Decimal)
                        else "" if value is None else value
                        for key, value in record.items()
                    })
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        effective_config = (
            asdict(inventory_config)
            if inventory_scenario == "operational_diversity"
            and inventory_config is not None
            else None
        )
        identity_payload = json.dumps(
            {
                "generator_version": GENERATOR_VERSION,
                "profile": profile,
                "inventory_scenario": inventory_scenario,
                "inventory_config": effective_config,
                "seed": seed,
                "csv_sha256": hashes,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        dataset_id = (
            f"logistics-{profile}-{inventory_scenario}-{seed}-"
            f"{hashlib.sha256(identity_payload.encode('utf-8')).hexdigest()[:16]}"
        )
        manifest = {
            "project": "projeto_logistico",
            "schema": "public",
            "generator_version": GENERATOR_VERSION,
            "dataset_id": dataset_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            "profile": profile,
            "inventory_scenario": inventory_scenario,
            "inventory_config": effective_config,
            "seed": seed,
            "period_start": PERIOD_START.isoformat(),
            "period_end": PERIOD_END.isoformat(),
            "row_counts": {table: len(rows) for table, rows in data.items()},
            "total_new_rows": sum(map(len, data.values())),
            "existing_ids_snapshot": {
                table: sorted(ids) for table, ids in BASE_IDS.items() if ids
            },
            "planned_id_ranges": {
                table: {
                    "first": BASE_MAX[table] + 1 if rows else None,
                    "last": BASE_MAX[table] + len(rows) if rows else None,
                    "count": len(rows),
                }
                for table, rows in data.items()
            },
            "id_ranges_are_reserved": False,
            "schema_metadata_status": SCHEMA_STATUS,
            "schema_metadata_confirmed_at": SCHEMA_CONFIRMED_AT,
            "schema_metadata_note": (
                "A3 returned 140 columns across 20 tables; names, types, limits, "
                "precision/scale, nullability, defaults, identity and generated "
                "properties matched the generator catalog."
            ),
            "offline_validation_passed": True,
            "validation_results": {
                "schema_and_exact_table_counts": "PASS",
                "primary_keys_and_existing_id_collisions": "PASS",
                "foreign_keys": "PASS",
                "data_types_nullability_and_limits": "PASS",
                "financial_totals_and_purchase_order_lines": "PASS",
                "payments_and_logistics_release_RN_012": "PASS",
                "order_completion_RN_014": "PASS",
                "delivery_dates_and_history": "PASS",
                "returns_order_ownership_RN_028": "PASS",
                "cumulative_return_quantities_RN_029": "PASS",
                "inventory_counts_and_warehouse_consistency": "PASS",
                "stock_movement_reconciliation_and_damage_pairing": "PASS",
                "transport_type_check_constraint": "PASS",
                "inventory_multilocation_diagnostics": "PASS",
            },
            "validation_errors": [],
            "csv_sha256": hashes,
            "database_written": False,
            "inventory_diagnostics": _inventory_scenario_metrics(
                data["t_produto"], data["t_estoque"]
            ),
        }
        if inventory_scenario == "operational_diversity":
            manifest["validation_results"][
                "inventory_scenario_coverage"
            ] = "PASS"
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        saved_manifest = json.loads(
            (staging / "manifest.json").read_text(encoding="utf-8")
        )
        for table, columns in SCHEMA.items():
            csv_path = staging / f"{table}.csv"
            if hashlib.sha256(csv_path.read_bytes()).hexdigest() != (
                saved_manifest["csv_sha256"].get(csv_path.name)
            ):
                raise ValueError(f"staged CSV hash mismatch: {csv_path.name}")
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                expected_header = [column.name for column in columns]
                if reader.fieldnames != expected_header:
                    raise ValueError(f"staged CSV header mismatch: {csv_path.name}")
                row_count = 0
                for row_index, record in enumerate(reader, start=1):
                    if (None in record
                            or len(record) != len(expected_header)
                            or any(value is None for value in record.values())):
                        raise ValueError(
                            f"staged CSV row has an invalid field count: "
                            f"{csv_path.name}:{row_index + 1}"
                        )
                    row_count += 1
                if row_count != len(data[table]):
                    raise ValueError(
                        f"staged CSV row count mismatch: {csv_path.name}; "
                        f"expected {len(data[table])}, got {row_count}"
                    )

        if output.exists() or output.is_symlink():
            raise FileExistsError(
                f"refusing to overwrite output path created during export: {output}"
            )
        os.rename(staging, output)
    except Exception as error:
        raise RuntimeError(
            f"artifact export failed; incomplete staging retained at "
            f"{staging}: {error}"
        ) from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("pilot", "full"), default="pilot")
    parser.add_argument(
        "--inventory-scenario",
        choices=("baseline", "operational_diversity"),
        default="baseline",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", type=Path, default=Path("generated_data"))
    args = parser.parse_args()

    counts = FULL_COUNTS if args.profile == "full" else PILOT_COUNTS
    inventory_config = (
        InventoryScenarioConfig()
        if args.inventory_scenario == "operational_diversity"
        else None
    )
    dataset = generate_dataset(
        args.profile,
        args.seed,
        args.inventory_scenario,
        inventory_config,
    )
    errors = validate_dataset(dataset, counts, inventory_config)
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    write_artifacts(
        dataset,
        args.output,
        args.profile,
        args.seed,
        args.inventory_scenario,
        inventory_config,
    )
    print(f"Generated {sum(map(len, dataset.values()))} offline rows at {args.output}")
    print(f"Schema status: {SCHEMA_STATUS}; no database connection or writes performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
