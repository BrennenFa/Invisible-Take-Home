from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from decimal import Decimal
import io
import csv
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

from ..database import get_db
from ..models import Account, User, Transaction, TransactionDirection
from ..security import get_current_user, limiter


router = APIRouter(prefix="/statements", tags=["statements"])


@router.get("/account/{account_id}")
@limiter.limit("30/minute")
def generate_account_statement(
    request: Request,
    account_id: UUID,
    start_date: datetime = Query(..., description="Statement start date (ISO format)"),
    end_date: datetime = Query(..., description="Statement end date (ISO format)"),
    format: str = Query("json", description="Format: json, csv, or pdf"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate account statement in JSON, CSV, or PDF format."""

    # Validate account ownership
    account = db.execute(select(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Validate date range
    if start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before end date"
        )

    # Fetch transactions in date range
    transactions = db.execute(select(Transaction).filter(
        Transaction.account_id == account_id,
        Transaction.created_at >= start_date,
        Transaction.created_at <= end_date
    ).order_by(Transaction.created_at.asc())).scalars().all()

    # Calculate opening balance (all transactions before start_date)
    opening_transactions = db.execute(select(Transaction).filter(
        Transaction.account_id == account_id,
        Transaction.created_at < start_date
    )).scalars().all()

    opening_balance = Decimal("0.00")
    for txn in opening_transactions:
        if txn.type == TransactionDirection.CREDIT:
            opening_balance += txn.amount
        else:
            opening_balance -= txn.amount

    # Calculate totals
    total_credits = sum(
        txn.amount for txn in transactions if txn.type == TransactionDirection.CREDIT
    ) or Decimal("0.00")

    total_debits = sum(
        txn.amount for txn in transactions if txn.type == TransactionDirection.DEBIT
    ) or Decimal("0.00")

    closing_balance = opening_balance + total_credits - total_debits

    # Statement data
    statement_data = {
        "account_id": str(account.id),
        "account_type": account.type.value,
        "statement_period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "opening_balance": float(opening_balance),
        "closing_balance": float(closing_balance),
        "total_credits": float(total_credits),
        "total_debits": float(total_debits),
        "transaction_count": len(transactions),
        "transactions": [
            {
                "date": txn.created_at.isoformat(),
                "description": txn.description,
                "reference": txn.reference,
                "type": txn.type.value,
                "category": txn.category.value,
                "amount": float(txn.amount),
                "debit": float(txn.amount) if txn.type == TransactionDirection.DEBIT else 0.0,
                "credit": float(txn.amount) if txn.type == TransactionDirection.CREDIT else 0.0
            }
            for txn in transactions
        ]
    }

    # Return based on format
    if format.lower() == "json":
        return statement_data

    elif format.lower() == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header info
        writer.writerow(["Account Statement"])
        writer.writerow(["Account ID", str(account.id)])
        writer.writerow(["Account Type", account.type.value])
        writer.writerow(["Period", f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"])
        writer.writerow(["Opening Balance", f"{opening_balance:.2f}"])
        writer.writerow([])

        # Transaction headers
        writer.writerow(["Date", "Description", "Reference", "Category", "Debit", "Credit", "Balance"])

        # Transactions
        running_balance = opening_balance
        for txn in transactions:
            if txn.type == TransactionDirection.CREDIT:
                running_balance += txn.amount
                debit_amt = ""
                credit_amt = f"{txn.amount:.2f}"
            else:
                running_balance -= txn.amount
                debit_amt = f"{txn.amount:.2f}"
                credit_amt = ""

            writer.writerow([
                txn.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                txn.description or "",
                txn.reference or "",
                txn.category.value,
                debit_amt,
                credit_amt,
                f"{running_balance:.2f}"
            ])

        # Footer
        writer.writerow([])
        writer.writerow(["Closing Balance", "", "", "", "", "", f"{closing_balance:.2f}"])
        writer.writerow(["Total Debits", "", "", "", f"{total_debits:.2f}", "", ""])
        writer.writerow(["Total Credits", "", "", "", "", f"{total_credits:.2f}", ""])

        # Return CSV response
        csv_content = output.getvalue()
        output.close()

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=statement_{account.id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
            }
        )

    elif format.lower() == "pdf":
        # Generate PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph("<b>Account Statement</b>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 0.2 * inch))

        # Account info
        account_info = [
            ["Account ID:", str(account.id)],
            ["Account Type:", account.type.value],
            ["Statement Period:", f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"],
            ["Opening Balance:", f"${opening_balance:.2f}"]
        ]

        info_table = Table(account_info, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Transactions table
        if transactions:
            data = [["Date", "Description", "Category", "Debit", "Credit", "Balance"]]

            running_balance = opening_balance
            for txn in transactions:
                if txn.type == TransactionDirection.CREDIT:
                    running_balance += txn.amount
                    debit_amt = ""
                    credit_amt = f"${txn.amount:.2f}"
                else:
                    running_balance -= txn.amount
                    debit_amt = f"${txn.amount:.2f}"
                    credit_amt = ""

                data.append([
                    txn.created_at.strftime('%Y-%m-%d'),
                    (txn.description or "")[:30],
                    txn.category.value,
                    debit_amt,
                    credit_amt,
                    f"${running_balance:.2f}"
                ])

            # Summary row
            data.append(["", "", "", "", "", ""])
            data.append(["", "", "Total Debits:", f"${total_debits:.2f}", "", ""])
            data.append(["", "", "Total Credits:", "", f"${total_credits:.2f}", ""])
            data.append(["", "", "Closing Balance:", "", "", f"${closing_balance:.2f}"])

            table = Table(data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 1*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -5), 1, colors.black),
                ('FONTNAME', (0, -4), (-1, -1), 'Helvetica-Bold'),
                ('LINEABOVE', (0, -4), (-1, -4), 2, colors.black),
            ]))
            elements.append(table)
        else:
            no_txn_text = Paragraph("No transactions found in this period.", styles['Normal'])
            elements.append(no_txn_text)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=statement_{account.id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
            }
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Must be 'json', 'csv', or 'pdf'"
        )
