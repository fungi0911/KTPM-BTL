from flask import Blueprint, jsonify, request
import random
import time

vendor_mock_bp = Blueprint("vendor_mock", __name__, url_prefix="/vendor-mock")

@vendor_mock_bp.route("/prices/<int:product_id>", methods=["GET"])
def mock_price(product_id: int):
    """
    Fake external API that sometimes fails or delays.
    Query params:
      - mode=down|flaky|ok (default: flaky)
      - fail_rate=0..1 (default: 0.3 when flaky)
      - delay_ms=int (default: 0)
    
    ---
    tags:
      - Vendor
    responses:
      200:
        description: Mocked vendor price
    """
    mode = request.args.get("mode", "flaky")
    fail_rate = float(request.args.get("fail_rate", "0.3"))
    delay_ms = int(request.args.get("delay_ms", "0"))

    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    if mode == "down":
        return jsonify({"msg": "Vendor service unavailable"}), 503

    if mode == "flaky" and random.random() < fail_rate:
        return jsonify({"msg": "Transient upstream error"}), 502

    price = round(random.uniform(10, 100), 2)
    return jsonify({
        "product_id": product_id,
        "price": price,
        "currency": "USD",
        "vendor": "MockVendor"
    })