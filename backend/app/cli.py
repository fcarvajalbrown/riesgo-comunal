import argparse
import json
import logging
import secrets
import sys

from app.auth import ROLES, hash_password
from app.db import scalar, transaction
from app.ingest.runner import run_source
from app.sources.registry import ADAPTERS
from app.sources.senapred import LAYERS, SenapredAdapter
from app.tenants import create_municipality, refresh_analysis_cells


def cmd_migrate(_args) -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


def cmd_ingest(args) -> None:
    keys = args.sources or list(ADAPTERS)
    for key in keys:
        options = {"backfill": True} if key == "usgs" and args.backfill else {}
        print(json.dumps(run_source(key, **options), ensure_ascii=False))


def cmd_create_tenant(args) -> None:
    boundary_only = tuple(layer for layer in LAYERS if layer.dataset == "comuna_boundary")
    with transaction() as conn:
        present = scalar(conn, "select 1 from feature where dataset = 'comuna_boundary' and external_id = :c", c=args.cut)
    if not present:
        result = run_source("senapred", adapter=SenapredAdapter(layers=boundary_only))
        print(json.dumps(result, ensure_ascii=False))
        if result["status"] != "success":
            sys.exit("no se pudieron descargar los límites comunales")
    with transaction() as conn:
        municipality_id = create_municipality(conn, args.cut, args.slug, args.name)
        cells = refresh_analysis_cells(conn, municipality_id)
    print(json.dumps({"municipality_id": municipality_id, "analysis_cells": cells}))


def cmd_create_user(args) -> None:
    if args.role not in ROLES:
        sys.exit(f"rol inválido; use uno de {', '.join(ROLES)}")
    password = args.password or secrets.token_urlsafe(12)
    with transaction() as conn:
        municipality_id = None
        if args.tenant:
            municipality_id = scalar(conn, "select id from municipality where slug = :s", s=args.tenant)
            if municipality_id is None:
                sys.exit(f"comuna no encontrada: {args.tenant}")
        scalar(
            conn,
            """
            insert into app_user (municipality_id, email, name, password_hash, role)
            values (:m, :e, :n, :p, :r)
            on conflict (email) do update set password_hash = excluded.password_hash, role = excluded.role,
                municipality_id = excluded.municipality_id, name = excluded.name, active = true
            returning id
            """,
            m=municipality_id,
            e=args.email.lower(),
            n=args.name or args.email,
            p=hash_password(password),
            r=args.role,
        )
    print(json.dumps({"email": args.email.lower(), "role": args.role, "password": password if not args.password else "(provided)"}))


def cmd_seed_demo(args) -> None:
    from app.demo import seed_demo

    print(json.dumps(seed_demo(args.tenant), ensure_ascii=False))


def cmd_bootstrap(_args) -> None:
    import os

    cmd_migrate(_args)
    cut = os.environ.get("TENANT_CUT")
    slug = os.environ.get("TENANT_SLUG")
    if cut and slug:
        with transaction() as conn:
            exists = scalar(conn, "select 1 from municipality where cut_code = :c", c=cut)
        if not exists:
            cmd_create_tenant(argparse.Namespace(cut=cut, slug=slug, name=os.environ.get("TENANT_NAME")))
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if email and password:
        with transaction() as conn:
            exists = scalar(conn, "select 1 from app_user where email = :e", e=email.lower())
        if not exists:
            role = "MUNICIPAL_ADMIN" if slug else "SUPER_ADMIN"
            cmd_create_user(argparse.Namespace(email=email, role=role, tenant=slug, name="Administración", password=password))
    if slug and os.environ.get("SEED_DEMO", "").lower() in ("1", "true", "yes"):
        cmd_seed_demo(argparse.Namespace(tenant=slug))


def cmd_worker(_args) -> None:
    from app.worker import main

    main()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="riesgo")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate").set_defaults(func=cmd_migrate)

    p = sub.add_parser("ingest")
    p.add_argument("sources", nargs="*")
    p.add_argument("--backfill", action="store_true")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("create-tenant")
    p.add_argument("--cut", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--name")
    p.set_defaults(func=cmd_create_tenant)

    p = sub.add_parser("create-user")
    p.add_argument("--email", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--tenant")
    p.add_argument("--name")
    p.add_argument("--password")
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("seed-demo")
    p.add_argument("--tenant", required=True)
    p.set_defaults(func=cmd_seed_demo)

    sub.add_parser("bootstrap").set_defaults(func=cmd_bootstrap)

    sub.add_parser("worker").set_defaults(func=cmd_worker)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
