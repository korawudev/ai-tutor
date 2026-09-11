#!/usr/bin/env python3
"""将 shared/models 的 Pydantic 模型导出为 OpenAPI components/schemas JSON。

用法:  .venv/bin/python scripts/export_openapi.py > /tmp/schemas.json
下游:  datamodel-codegen --input /tmp/schemas.json --input-file-type openapi \\
                          --output-model-type ts --output web-app/src/types/generated.ts
"""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shared.models as m  # noqa: E402

TOP_LEVEL = ("Base",)  # SQLAlchemy DeclarativeBase, not a Pydantic schema

schemas: dict[str, dict] = {}
defs: dict[str, dict] = {}

for name in m.__all__:
    if name in TOP_LEVEL:
        continue
    obj = getattr(m, name, None)
    if isinstance(obj, type) and issubclass(obj, BaseModel):
        try:
            schema = obj.model_json_schema(ref_template="#/components/schemas/{model}")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        # 嵌套模型（$defs）展开到 components；ref_template 已指向 components
        for key, value in schema.pop("$defs", {}).items():
            defs.setdefault(key, value)
        schemas[name] = schema

# $defs 里的模型名与顶层模型名冲突时，以顶层 schema 为准
components = {**defs, **schemas}

doc = {
    "openapi": "3.0.0",
    "info": {"title": "ai-tutor shared models", "version": "0.1.0"},
    "paths": {},
    "components": {"schemas": components},
}
json.dump(doc, sys.stdout, ensure_ascii=False, indent=2)
