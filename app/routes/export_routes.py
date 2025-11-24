from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from flasgger import swag_from
from ..models.warehouse_item import WarehouseItem
from ..extensions import db
import matplotlib.pyplot as plt
from io import BytesIO

export_bp = Blueprint("export", __name__, url_prefix="/export")

@export_bp.route("/<int:item_id>", methods=["POST"])
def export_report(item_id):
    """Generates a PDF report
    ---
    tags:
      - Export
    parameters:
      - name: item_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: PDF report generated successfully
        schema:
          type: file
      404:
        description: Item not found
      429:
        description: Too many requests
    """
    item = WarehouseItem.query.get_or_404(item_id)

    warehouses = []
    quantities = []
    for w_item in item.warehouse_items:  # giả sử quan hệ one-to-many
        warehouses.append(w_item.warehouse_id)  # tên kho
        quantities.append(w_item.quantity)  # số lượng trong kho

    plt.figure(figsize=(10, 6))
    plt.bar(warehouses, quantities, color='skyblue')
    plt.xlabel("Warehouse")
    plt.ylabel("Quantity")
    plt.title(f"Item '{item.id}' Quantity per Warehouse")
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Xuất ra PDF
    pdf_buffer = BytesIO()
    plt.savefig(pdf_buffer, format='pdf')
    pdf_buffer.seek(0)
    plt.close()

    return send_file(pdf_buffer, as_attachment=True,
                     download_name=f"{item.name}_report.pdf",
                     mimetype='application/pdf')
