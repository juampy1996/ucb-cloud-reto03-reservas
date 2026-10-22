import json
import os
import time
import uuid
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(os.environ.get("TABLA_RESERVAS", "ucb-reservas-jpm"))
ADMIN_KEY = os.environ.get("ADMIN_KEY", "ucb-admin-2026")

HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Admin-Key"
}

def respuesta(codigo, cuerpo):
    return {"statusCode": codigo, "headers": HEADERS, "body": json.dumps(cuerpo, ensure_ascii=False)}

def emitir_metrica(operacion, resultado):
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "UCB/Reservas",
                "Dimensions": [["Operacion", "Resultado"]],
                "Metrics": [{"Name": "Solicitudes", "Unit": "Count"}]
            }]
        },
        "Operacion": operacion,
        "Resultado": resultado,
        "Solicitudes": 1
    }))

def lambda_handler(event, context):
    metodo = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "GET")
    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "CORS OK"})

    params = event.get("queryStringParameters") or {}
    headers_req = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    clave_enviada = headers_req.get("x-admin-key") or params.get("admin_key")

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except ValueError:
            return respuesta(400, {"error": "JSON inválido"})

    if metodo == "GET":
        items = tabla.scan().get("Items", [])
        recurso_filtro = params.get("recurso")
        if recurso_filtro:
            items = [i for i in items if i.get("recurso") == recurso_filtro]
        items.sort(key=lambda x: x.get("slot_id", ""))
        emitir_metrica("CONSULTAR", "EXITO")
        return respuesta(200, {"total": len(items), "reservas": items})

    if metodo == "POST":
        recurso = body.get("recurso", "").strip()
        fecha = body.get("fecha", "").strip()
        hora = body.get("hora", "").strip()
        cliente = body.get("cliente", "").strip()
        servicio = body.get("servicio", "Consulta General").strip()

        if not (recurso and fecha and hora and cliente):
            emitir_metrica("CREAR", "ERROR_VALIDACION")
            return respuesta(400, {"error": "Faltan campos obligatorios: recurso, fecha, hora, cliente"})

        slot_id = f"{recurso}#{fecha}#{hora}"
        item = {
            "slot_id": slot_id,
            "reserva_id": str(uuid.uuid4())[:8],
            "recurso": recurso,
            "fecha": fecha,
            "hora": hora,
            "cliente": cliente,
            "servicio": servicio,
            "estado": "CONFIRMADA",
            "actualizado_utc": datetime.now(timezone.utc).isoformat()
        }
        try:
            tabla.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(slot_id) OR estado = :cancelada",
                ExpressionAttributeValues={":cancelada": "CANCELADA"}
            )
            emitir_metrica("CREAR", "CONFIRMADA")
            return respuesta(201, {"mensaje": "Reserva confirmada con éxito", "reserva": item})
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                emitir_metrica("CREAR", "CONFLICTO_DUPLICADO")
                return respuesta(409, {
                    "error": "CONFLICTO: El recurso ya está reservado en esa fecha y horario.",
                    "slot_id": slot_id
                })
            raise e

    if clave_enviada != ADMIN_KEY and body.get("admin_key") != ADMIN_KEY:
        emitir_metrica(metodo, "NO_AUTORIZADO")
        return respuesta(403, {"error": "Acceso denegado: Clave de administración inválida o ausente"})

    if metodo == "PUT":
        slot_id = body.get("slot_id")
        nuevo_cliente = body.get("cliente")
        nuevo_servicio = body.get("servicio")
        if not (slot_id and nuevo_cliente and nuevo_servicio):
            return respuesta(400, {"error": "Envía slot_id, cliente y servicio para modificar"})
        try:
            res = tabla.update_item(
                Key={"slot_id": slot_id},
                UpdateExpression="SET cliente = :c, servicio = :s, actualizado_utc = :u",
                ConditionExpression="attribute_exists(slot_id)",
                ExpressionAttributeValues={
                    ":c": nuevo_cliente,
                    ":s": nuevo_servicio,
                    ":u": datetime.now(timezone.utc).isoformat()
                },
                ReturnValues="ALL_NEW"
            )
            emitir_metrica("MODIFICAR", "EXITO")
            return respuesta(200, {"mensaje": "Reserva modificada", "reserva": res["Attributes"]})
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return respuesta(404, {"error": "La reserva indicada no existe"})
            raise e

    if metodo == "DELETE":
        slot_id = params.get("slot_id") or body.get("slot_id")
        if not slot_id:
            return respuesta(400, {"error": "Debes indicar el slot_id a cancelar"})
        try:
            res = tabla.update_item(
                Key={"slot_id": slot_id},
                UpdateExpression="SET estado = :est, actualizado_utc = :u",
                ConditionExpression="attribute_exists(slot_id)",
                ExpressionAttributeValues={
                    ":est": "CANCELADA",
                    ":u": datetime.now(timezone.utc).isoformat()
                },
                ReturnValues="ALL_NEW"
            )
            emitir_metrica("CANCELAR", "EXITO")
            return respuesta(200, {"mensaje": "Reserva cancelada; horario liberado", "reserva": res["Attributes"]})
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return respuesta(404, {"error": "La reserva no existe"})
            raise e

    return respuesta(405, {"error": "Método no permitido"})