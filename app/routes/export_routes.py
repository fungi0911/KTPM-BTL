import io
import os

from flask import Blueprint, jsonify, send_file, current_app
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from ..celery_app import celery
from ..extensions import limiter
from app.tasks import generate_barchart
from ..models.warehouse_item import WarehouseItem

export_bp = Blueprint("export", __name__, url_prefix="/report")

@export_bp.route("/<int:product_id>/v1", methods=["POST"])
@limiter.limit("10 per minute")
def barchart_export(product_id):
    """
        Generate PDF quantity report for an product
        ---
        tags:
          - Export
        summary: Generate PDF report
        parameters:
          - name: product_id
            in: path
            required: true
            schema:
              type: integer
        responses:
          200:
            description: PDF generated
            content:
              schema:
                task_id: string
                status: Queued
          404:
            description: Items not found
        security:
          - BearerAuth: []
        """
    items = WarehouseItem.query.with_entities(
        WarehouseItem.warehouse_id, WarehouseItem.quantity
    ).filter_by(product_id=product_id).all()

    if not items:
        return {"message": "No items found"}, 404

    warehouses, quantities = zip(*items) if items else ([], [])

    pdf_buffer = io.BytesIO()
    with PdfPages(pdf_buffer) as pdf:
        plt.figure(figsize=(10, 6))
        plt.bar(warehouses, quantities, color='skyblue')
        plt.xlabel("Warehouse")
        plt.ylabel("Quantity")
        plt.title(f"Product '{product_id}' Quantity per Warehouse")
        plt.xticks(rotation=45)
        plt.tight_layout()

        pdf.savefig()  # lưu trang vào PDF
        plt.close()

    pdf_buffer.seek(0)

    # --- Trả file cho client ---
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"product_{product_id}_report.pdf",
        mimetype="application/pdf"
    )

@export_bp.route("/<int:product_id>", methods=["POST"])
@limiter.limit("10 per minute")
def bar_chart(product_id):
    """
    Generate PDF quantity report for an product
    ---
    tags:
      - Export
    summary: Generate PDF report
    parameters:
      - name: product_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: PDF generated
        content:
          schema:
            task_id: string
            status: Queued
      404:
        description: Items not found
    security:
      - BearerAuth: []
    """
    task = generate_barchart.apply_async(args=[product_id])

    return {
        "task_id": task.id,
        "status": "Queued",
    }, 202


@export_bp.route("/result/<task_id>", methods=["GET"])
def download_barchart(task_id):
    """
    Download PDF quantity report for a product
    ---
    tags:
      - Export
    summary: Download PDF report by task_id
    parameters:
      - name: task_id
        in: path
        required: true
        schema:
          type: string
    responses:
      200:
        description: PDF generated
        content:
          application/pdf:
            schema:
              type: string
              format: binary
      202:
        description: Task still processing
      404:
        description: File not found
    security:
      - BearerAuth: []
    """
    result = celery.AsyncResult(task_id)

    # Nếu task chưa hoàn thành
    if not result.ready():
        return jsonify({"status": result.status}), 202

    # Lấy kết quả trong app context để an toàn với Flask globals
    with current_app.app_context():
        try:
            data = result.get(timeout=5)  # thêm timeout tránh treo request
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        if data.get("message") == "No items found":
            return jsonify({"message": "No items found"}), 404

        file_path = data.get("file_path")
        file_path = os.path.normpath(file_path)
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path),
            mimetype="application/pdf"
        )
