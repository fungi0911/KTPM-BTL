import os

from flask import Blueprint, jsonify, send_file, current_app

from ..celery_app import celery

from app.tasks import generate_report

export_bp = Blueprint("export", __name__, url_prefix="/export")


@export_bp.route("/<int:product_id>", methods=["POST"])
def export_report(product_id):
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
    task = generate_report.apply_async(args=[product_id])

    return {
        "task_id": task.id,
        "status": "Queued",
    }, 202


@export_bp.route("/download/<task_id>", methods=["GET"])
def download_report(task_id):
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
