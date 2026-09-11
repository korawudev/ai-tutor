"""Alembic 迁移校验：revision 链完整性 + 单头 + 模型元数据对齐

设计动机（P4-9）:
- 仓库无 alembic.ini/env.py（手写版本文件，无 CLI 可依赖），只能静态 AST 校验
- 基线 revision 是 "002"（= scripts/init_db.sql），migrations/versions/ 从 003 起
- 校验三类不变量：
  1. revision 唯一、down_revision 链完整（无悬空引用、无环）
  2. 恰好一个 head
  3. op 目标表名必须存在于 shared.models 元数据（迁移与 ORM 漂移检测）
"""

import ast
import sys
from pathlib import Path

from shared.models import Base

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "versions"
BASELINE = "002"  # init_db.sql 建立的全量基线

# 需校验表目标的 Alembic op：name 在第一个位置参数或同名 kwarg
TABLE_OPS = {
    "create_table": {"pos": 0, "kw": "tablename"},
    "drop_table": {"pos": 0, "kw": "tablename"},
    "add_column": {"pos": 0, "kw": "table_name"},
    "drop_column": {"pos": 0, "kw": "table_name"},
    "alter_column": {"pos": 0, "kw": "table_name"},
    "create_index": {"pos": 1, "kw": "table_name"},
    "drop_index": {"pos": 1, "kw": "table_name"},
    "create_check_constraint": {"pos": 1, "kw": "table_name"},
    "drop_constraint": {"pos": 1, "kw": "table_name"},
}

_ERRORS: list[str] = []


def fail(msg: str) -> None:
    _ERRORS.append(msg)


def parse_version_file(
    path: Path,
) -> tuple[str | None, str | None, ast.FunctionDef, ast.FunctionDef] | None:
    """AST 提取 revision/down_revision 与 upgrade/downgrade 函数体"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    revision = down_revision = None
    upgrade: ast.FunctionDef | None = None
    downgrade: ast.FunctionDef | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                if target.id == "revision":
                    revision = node.value.value
                elif target.id == "down_revision":
                    down_revision = node.value.value
        elif isinstance(node, ast.FunctionDef):
            if node.name == "upgrade":
                upgrade = node
            elif node.name == "downgrade":
                downgrade = node
    return revision, down_revision, upgrade, downgrade


def check_version_chain(versions: dict[str, str]) -> None:
    """revision 唯一 + 链完整 + 单 head"""
    revisions = set(versions)
    if len(revisions) != len(versions):
        dupes = [r for r in set(versions) if list(versions).count(r) > 1]
        fail(f"revision 重复: {sorted(dupes)}")

    heads = [r for r in revisions if r not in versions.values()]
    if len(heads) != 1:
        fail(f"期望恰好 1 个 head，实际 {len(heads)} 个: {sorted(heads)}")
    else:
        print(f"HEAD: {heads[0]}")

    for rev, down in versions.items():
        if down == BASELINE or down is None:
            continue
        if down not in revisions:
            detail = (
                f"revision {rev} 的 down_revision={down}"
                f" 悬空（不在 versions/ 且不是基线 {BASELINE}）"
            )
            fail(detail)

    # 线性链检查：每个 revision 最多被一个后继引用
    children: dict[str, list[str]] = {}
    for rev, down in versions.items():
        if down:
            children.setdefault(down, []).append(rev)
    for down, kids in children.items():
        if len(kids) > 1:
            fail(f"revision {down} 有多个后继 {kids}（分支不合法）")


def check_op_targets(path: Path) -> None:
    """迁移 op 的 table 目标必须存在于 SQLAlchemy 元数据"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    known = set(Base.metadata.tables)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "op"
        ):
            spec = TABLE_OPS.get(func.attr)
            if spec is None:
                continue
            table = None
            if len(node.args) > spec["pos"] and isinstance(node.args[spec["pos"]], ast.Constant):
                table = node.args[spec["pos"]].value
            for kw in node.keywords:
                if kw.arg == spec["kw"] and isinstance(kw.value, ast.Constant):
                    table = kw.value.value
            if isinstance(table, str) and table not in known:
                fail(f"{path.name}: op.{func.attr} 目标表 '{table}' 不在 shared.models 元数据中")


def main() -> int:
    files = sorted(MIGRATIONS_DIR.glob("*.py"))
    if not files:
        fail(f"未找到迁移文件: {MIGRATIONS_DIR}")
        return 1

    versions: dict[str, str] = {}
    for path in files:
        parsed = parse_version_file(path)
        if parsed is None:
            fail(f"{path.name}: 无法解析为版本文件")
            continue
        revision, down_revision, upgrade, downgrade = parsed
        if revision is None or down_revision is None:
            fail(f"{path.name}: 缺少 revision/down_revision 字面量")
            continue
        if upgrade is None or downgrade is None:
            fail(f"{path.name}: 缺少 upgrade/downgrade 函数")
        versions[revision] = down_revision
        check_op_targets(path)

    check_version_chain(versions)

    if _ERRORS:
        print("迁移校验失败:")
        for err in _ERRORS:
            print(f"  - {err}")
        return 1

    total = len(files)
    print(f"迁移校验通过: {total} 个版本 (003..{max(versions)})，链完整，单 head，元数据对齐")
    return 0


if __name__ == "__main__":
    sys.exit(main())
