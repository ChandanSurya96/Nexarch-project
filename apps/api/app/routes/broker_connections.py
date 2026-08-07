"""Broker-connections blueprint.

Endpoints (all under /api/v1/broker-connections — prefix registered in
create_app), all requiring a valid access token:
    POST   /init           — { broker_name } -> { redirect_url }
    POST   /callback       — { broker_name, auth_code }
    GET    /                — list the caller's broker connections
    DELETE /:id             — disconnect (deletes the encrypted token)
    POST   /:id/sync        — manual "sync now", cooldown-limited

See docs/api.md "Broker Connections" and docs/broker-integrations.md "Auth Flow".
"""

import uuid

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app.schemas.broker_connection import (
    BrokerConnectionCallbackSchema,
    BrokerConnectionInitSchema,
    BrokerConnectionSchema,
)
from app.services.broker_connection_service import (
    BrokerConnectionError,
    disconnect,
    handle_callback,
    init_connection,
    list_connections,
    trigger_manual_sync,
)
from app.utils.responses import error, format_validation_error, success

broker_connections_bp = Blueprint("broker_connections", __name__)

_init_schema = BrokerConnectionInitSchema()
_callback_schema = BrokerConnectionCallbackSchema()
_connection_schema = BrokerConnectionSchema()


@broker_connections_bp.post("/init")
@jwt_required()
def init():
    try:
        data = _init_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", format_validation_error(exc.messages), 400)

    user_id = uuid.UUID(get_jwt_identity())
    try:
        redirect_url = init_connection(user_id, data["broker_name"])
    except BrokerConnectionError as exc:
        return error(exc.code, exc.message, exc.status)

    return success({"redirect_url": redirect_url})


@broker_connections_bp.post("/callback")
@jwt_required()
def callback():
    try:
        data = _callback_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return error("VALIDATION_ERROR", format_validation_error(exc.messages), 400)

    user_id = uuid.UUID(get_jwt_identity())
    try:
        connection = handle_callback(user_id, data["broker_name"], data["auth_code"], data["state"])
    except BrokerConnectionError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(_connection_schema.dump(connection), status=201)


@broker_connections_bp.get("")
@jwt_required()
def list_():
    user_id = uuid.UUID(get_jwt_identity())
    connections = list_connections(user_id)
    return success(_connection_schema.dump(connections, many=True))


@broker_connections_bp.delete("/<uuid:connection_id>")
@jwt_required()
def delete(connection_id: uuid.UUID):
    user_id = uuid.UUID(get_jwt_identity())
    try:
        disconnect(user_id, connection_id)
    except BrokerConnectionError as exc:
        return error(exc.code, exc.message, exc.status)

    return success(None)


@broker_connections_bp.post("/<uuid:connection_id>/sync")
@jwt_required()
def sync_now(connection_id: uuid.UUID):
    user_id = uuid.UUID(get_jwt_identity())
    try:
        trigger_manual_sync(user_id, connection_id)
    except BrokerConnectionError as exc:
        return error(exc.code, exc.message, exc.status)

    return success({"queued": True})
